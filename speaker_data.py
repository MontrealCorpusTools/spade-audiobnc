'''This parses a single conversation from an AudioBNC transcript'''
import os
import subprocess
import sys
from bs4 import BeautifulSoup
import textgrid
from classify_good import chunk_utterances

TRANSCRIPT_DIR = "transcripts"
OUTPUT_DIR = "speakered_textgrids_chunked"
AUDIO_BNC_DIR = "/media/share/corpora/BNC/Texts"
RETRIEVE_FROM_SERVER = False
IGNORED_WORDS = ["sp", "{OOV}", "{LG}", "{GAP_ANONYMIZATION_ADDRESS}", "{GAP_ANONYMIZATION_TELEPHONENUMBER}", "{GAP_ANONYMIZATION_NAME}", "{GAP_ANONYMIZATION}", "{CG}", "{XX}", "{GAP_NAME}"]
SPLIT_WORDS = ["'S", "N'T", "'VE", "'M", "'LL", "'D", "'D'VE", "'RE"]

class Speaker:
    speak_id = ""
    ageGroup = ""
    role = ""
    sex = ""
    soc = ""
    dialect = ""
    phoneInterval = None
    wordInterval = None

    def __init__(self, profile, bounds):
        self.speak_id = profile["xml:id"]
        self.ageGroup = profile["ageGroup"]
        self.role = profile["role"]
        self.sex = profile["sex"]
        self.soc = profile["soc"]
        self.dialect = profile["dialect"]
        self.phoneInterval = textgrid.IntervalTier("{} - phones".format(self.speak_id), bounds[0], bounds[1])
        self.wordInterval = textgrid.IntervalTier("{} - words".format(self.speak_id), bounds[0], bounds[1])

    def __str__(self):
        return "{}:{}:{}:{}:{}:{}".format(self.speak_id, self.ageGroup, self.role, self.sex, self.soc, self.dialect)

def fill_gaps(tier, mark):
    '''For a given tier, add an interval with a given mark to all unfilled intervals'''
    old_time = tier.minTime
    for interval in tier.intervals:
        if old_time < interval.minTime:
            tier.addInterval(textgrid.Interval(old_time, interval.minTime, mark))
        old_time = interval.maxTime
    if tier.maxTime is not None and old_time < tier.maxTime:
        tier.addInterval(textgrid.Interval(old_time, tier.maxTime, mark))

def get_interval_slice(interval, minTime, maxTime):
    '''Get the slice of intervals between two timepoints of an interval tier'''
    minTime = float(minTime) + 0.001
    maxTime = float(maxTime) - 0.001
    return slice(interval.indexContaining(minTime), interval.indexContaining(maxTime)+1)

def unwrap_utterance(s):
    '''Given a utterance, return a list of all w tagged text'''
    utterance = []
    for child in s.children:
        if child.name == "w":
            utterance += [child.string.strip()]
        elif child.name == "mw" or child.name == "trunc":
            utterance += unwrap_utterance(child)
    return utterance

def parse_utterance(u):
    '''Parse a given utterance and return the text from it'''
    utterance = []
    for s in u.find_all(["s"]):
        utterance += unwrap_utterance(s)
    utterance = [x.upper().strip('.') for x in utterance]
    utterance = join_split_words(utterance)
    utterance = break_hyphens(utterance)
    return utterance

def join_split_words(utterance):
    '''Joins split words such as I+'m to I'm '''
    indices = [i for i, x in enumerate(utterance) if x in SPLIT_WORDS]
    for i in indices:
        utterance[i-1] += utterance[i]
    #Enumerate since we'll progessively have a smaller list
    for j, i in enumerate(indices):
        del utterance[i-j]
    return utterance

def break_hyphens(utterance):
    '''Splits utterance by hyphens, and flattens the list'''
    utterance = [x.split('-') for x in utterance]
    return [x for y in utterance for x in y]

def add_time_slice_to_speaker(speakers, speaker, words, phones, bounds):
    for phone in phones[get_interval_slice(phones, bounds[0], bounds[1])]:
        try:
            speakers[speaker].phoneInterval.addInterval(phone)
        except ValueError as e:
            if phone not in speakers[speaker].phoneInterval.intervals:
                raise e
    for w in words[get_interval_slice(words, bounds[0], bounds[1])]:
        try:
            speakers[speaker].wordInterval.addInterval(w)
        except ValueError as e:
            if w not in speakers[speaker].wordInterval.intervals:
               raise e

def interval_in_grid(grid, interval):
    '''Check whether a given interval is in a grid'''
    time = interval.minTime + (interval.maxTime-interval.minTime)/2
    for tier in grid.tiers:
        test_inter = tier.intervalContaining(time)
        if test_inter == interval:
            return True
    return False

def check_neighbours(grid, interval):
    '''Given an interval, returns the names of who's speaking to the left and right'''
    offset = [0.001, 0.1, 1, 5, 10]
    left = []
    i = 0
    while not left:
        time = float(interval.minTime)+offset[i]
        i += 1
        for tier in grid.tiers:
            if tier.name.endswith(" - words"):
                speaker = tier.name.split(" - words")[0]
                speak_interval = tier.intervalContaining(time)
                if speak_interval is None:
                    break
                if speak_interval.maxTime > time and speak_interval.minTime < time \
                           and speak_interval.mark not in IGNORED_WORDS:
                    left += [speaker]
        if i >= len(offset):
            break
    right = []
    i = 0
    while not right:
        time = float(interval.maxTime)+offset[i]
        i += 1
        for tier in grid.tiers:
            if tier.name.endswith(" - words"):
                speaker = tier.name.split(" - words")[0]
                speak_interval = tier.intervalContaining(time)
                if speak_interval is None:
                    break
                if speak_interval.maxTime > time and speak_interval.minTime < time \
                           and speak_interval.mark not in IGNORED_WORDS:
                    left += [speaker]
        if i >= len(offset):
            break
    return (left, right)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Please provide a path to textgrids")
        sys.exit(2)

    recorders = [("".join("".join(s.split("/")[-1]).split(".")[0]).split("_")[2:4]) for s in sys.argv[1:]]
    recorders = [(x, int(y) - 1) for (x, y) in recorders]
    problematic_files = []
    bad_files = []

    for no_files, ((recorder, conversation), grid_file) in enumerate(zip(recorders, sys.argv[1:])):
        try: 
            print(f"{no_files+1}/{len(recorders)}")
            if not os.path.isfile(grid_file):
                print("{} is not a valid file".format(grid_file))
                continue
            grid = textgrid.TextGrid(name=grid_file)
            try:
                grid.read(grid_file)
            except AttributeError:
                continue
            except ValueError:
                continue
            #REMOVE IGNORED WORDS
            words = grid[grid.getNames().index("word")]
            phones = grid[grid.getNames().index("phone")]

            word_utterances = [(w.mark.strip(), w) for u in chunk_utterances(grid) for w in words[u] if w.mark not in IGNORED_WORDS]
            nonword_utterances = [(w.mark.strip(), w) for u in chunk_utterances(grid) for w in words[u] if w.mark in IGNORED_WORDS]
            transcript_file = "{}/{}/{}/{}.xml".format(AUDIO_BNC_DIR, recorder[0], recorder[:2], recorder)
            with open(transcript_file, 'r') as f:
                soup = BeautifulSoup(f, "lxml-xml")

                conv = soup.stext.find_all("div")
                if not conv:
                    #This is a single conversation recording
                    conv = soup.stext
                    tape = soup.teiHeader.profileDesc.settingDesc.setting["n"]
                else:
                    conv = conv[conversation]
                    tape = conv["n"]

                try:
                    profiles = soup.profileDesc.particDesc.find_all("person")
                    speakers = [Speaker(p, words.bounds()) for p in profiles]
                except AttributeError:
                    #No profile list for some reason, have to go through utterances 
                    profiles =  set(u["who"] for u in conv.find_all("u"))
                    profiles  = [{"xml:id": p,
                                "ageGroup":"x",
                                "role":"x",
                                "sex":"x",
                                "soc":"x",
                                "dialect":"x",
                                } for p in profiles]
                    speakers = [Speaker(p, words.bounds()) for p in profiles]

                speakers = {s.speak_id : s for s in speakers}


                conv_speakers = set()
                utterances = []
                for u in conv.find_all("u"):
                    utterance = parse_utterance(u)
                    conv_speakers.update(set([u["who"]]))
                    utterances += [(x.strip(), u["who"]) for x in utterance]

                #TODO, see if this does anything
                conv_speakers -= set(conv_speakers.difference(set(speakers.keys())))

                for u in utterances:
                    found_words = None
                    for i, (word, interval) in enumerate(word_utterances):
                        if u[0] == word:
                            add_time_slice_to_speaker(speakers, u[1], words, phones, (interval.minTime, interval.maxTime))
                            found_words = slice(i, i+1)
                            break
                        if u[0] == "".join([w[0] for w in word_utterances[i:i+2]]):
                            add_time_slice_to_speaker(speakers, u[1], words, phones, (interval.minTime, word_utterances[i+1][1].maxTime))
                            found_words = slice(i, i+2)
                            break
                    if found_words is not None:
                        del word_utterances[found_words]
                output_grid = textgrid.TextGrid(name= \
                        "{}/{}-speakered.TextGrid".format(OUTPUT_DIR, "".join(grid_file.split("/")[-1]).split(".TextGrid")[0]), \
                        minTime=words.minTime, \
                        maxTime=words.maxTime)
                for s in conv_speakers:
                    output_grid.append(speakers[s].wordInterval)
                    output_grid.append(speakers[s].phoneInterval)
                if word_utterances:
                    problematic_files += [(grid_file, len(word_utterances), word_utterances)]
                    #There are unaligned words
                    for word in word_utterances:
                        (left, right) = check_neighbours(output_grid, word[1])
                        matching = {l for l in left for r in right if l == r}
                        if matching:
                            add_time_slice_to_speaker(speakers, matching[0], words, phones, (word[1].minTime, word[1].maxTime))
                        elif left:
                            add_time_slice_to_speaker(speakers, left[0], words, phones, (word[1].minTime, word[1].maxTime))
                        elif right:
                            add_time_slice_to_speaker(speakers, right[0], words, phones, (word[1].minTime, word[1].maxTime))
                for word in nonword_utterances:
                    #Check if its already been added
                    if interval_in_grid(grid, word[1]):
                        continue

                    (left, right) = check_neighbours(output_grid, word[1])
                    matching = {l for l in left for r in right if l == r}
                    if matching:
                        add_time_slice_to_speaker(speakers, matching[0], words, phones, (word[1].minTime, word[1].maxTime))
                    elif left:
                        add_time_slice_to_speaker(speakers, left[0], words, phones, (word[1].minTime, word[1].maxTime))
                    elif right:
                        add_time_slice_to_speaker(speakers, right[0], words, phones, (word[1].minTime, word[1].maxTime))
                for s in conv_speakers:
                    #add silences
                    fill_gaps(speakers[s].phoneInterval, "sil")
                    fill_gaps(speakers[s].wordInterval, "sp")
                for tier in grid.tiers:
                    if tier.name not in ["phone", "word"]:
                        output_grid.append(tier)
                output_grid.write(output_grid.name)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            print(f"problematic file, {grid_file}")
            bad_files += [grid_file]

with open("bad_files.txt", "a+") as f:
    for x in bad_files:
        f.write(f"{x}\n")
