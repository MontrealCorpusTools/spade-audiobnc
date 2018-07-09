'''Provided a list of args with TextGrid files from AudioBNC, classifies them
as good or bad depenending on the proportion of silence and speech that are
correctly labeled by a voice activity detector'''
import sys
import os
import subprocess
import wave
import webrtcvad
import textgrid

CHUNKED_FILES = True
OUTPUT_FINE = True
OUTPUT_UTTERANCES = True
OUTPUT_DIR = "alt_chunked"
WAV_DIRECTORY = "roquefort:/media/share/corpora/AudioBNC/wavs/"
BAD_PHONE_BUFFER = 3
VAD = [webrtcvad.Vad(i) for i in range(4)]
SAMPLE_SIZE = 20
MAX_GAP = 150/1000

def get_frames(wav, grid):
    '''Gets frames corresponding to the length of the TextGrid'''
    with wave.open(f"wavs/{wav}", "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        assert rate in (8000, 16000, 32000)
        start = int(grid.minTime*rate)
        stop = int(grid.maxTime*rate)
        wf.setpos(start)
        frames = wf.readframes(stop-start)
        return (rate, frames)

def second_to_frame(time, rate):
    '''Given time in seconds, return the index in the frames object'''
    return int(rate*(time)*2)

def print_utterances(utterances, words):
    '''Given the utterances, print what was said in that section'''
    print(utterances)
    print([[w.mark for w in words[u]] for u in utterances])


def chunk_utterances(grid, print_utt=False):
    '''Given the grid and rate, returns a list with
       slices of each utterance'''
    words = grid[grid.getNames().index("word")]
    utterances = []

    start_index = 0
    gapTime = 0
    for i, word in enumerate(words):
        if word.mark != "sp":
            gapTime = 0
        else:
            gapTime += word.duration()
        if gapTime >= MAX_GAP:
            if not utterances:
                utterances += [slice(0, i+1)]
            else:
                utterances += [slice(start_index, i)]
            start_index = i+1
    if print_utt:
        print_utterances(utterances, words)
    return utterances

def overwrite_interval(int_tier, start, stop, mark):
    '''Given an interval, add it to the interval
       overwriting anything within that time span '''
    min_ind = int_tier.indexContaining(start)
    max_ind = int_tier.indexContaining(stop)
    #Get rid of anything in between
    del int_tier.intervals[min_ind+1:max_ind]

    min_ind = int_tier.indexContaining(start)
    max_ind = int_tier.indexContaining(stop)
    minOverlap = int_tier[min_ind]
    maxOverlap = int_tier[max_ind]

    if minOverlap == maxOverlap:
        if stop != minOverlap.maxTime:
            newOver = textgrid.Interval(stop, minOverlap.maxTime, minOverlap.mark)
            minOverlap.maxTime = start
            int_tier.addInterval(newOver)
        else:
            minOverlap.maxTime = sp.minTime
    else:
        minOverlap.maxTime = start
        maxOverlap.minTime = stop

    int_tier.add(start, stop, mark)


def examine_phonemes(grid):
    '''Iterates over the phones and flags unrealistic ones'''
    phones = grid[grid.getNames().index("phone")]
    bad_phones = textgrid.IntervalTier(name="bad_phones",\
                                       minTime=phones.minTime,\
                                       maxTime=phones.maxTime)
    bad_phones.add(phones.minTime, phones.maxTime, "good")
    for phone in phones:
        if phone.mark not in ["{LG}", "sil", "ns", "sp"] and phone.duration() > 2:
            overwrite_interval(bad_phones, phone.minTime-BAD_PHONE_BUFFER, phone.maxTime+BAD_PHONE_BUFFER, "bad")
            #This phoneme is not realistic
    grid.append(bad_phones)
    return grid

def get_section_vad(frames, word, duration, rate, offset=0, utterance=None):
    '''Find the VAD ratio of a given section of frames'''
    frame_width = second_to_frame(SAMPLE_SIZE/1000, rate)
    count = 0
    total = 0
    count_uv = 0
    total_uv = 0
    for t in range(0+offset, duration+offset, frame_width):
        inter = word.indexContaining(t/rate/2+float(word.minTime))
        if inter is not None:
            if utterance is not None:
                if utterance > 2:
                    speech = VAD[1].is_speech(frames[t:t+frame_width], rate)
                elif utterance > 1:
                    speech = VAD[2].is_speech(frames[t:t+frame_width], rate)
                else:
                    speech = VAD[3].is_speech(frames[t:t+frame_width], rate)
            else:
                speech = VAD[2].is_speech(frames[t:t+frame_width], rate)
            if word[inter].mark != "sp":
                total += 1
                if speech:
                    count += 1
            if word[inter].mark == "sp":
                total_uv += 1
                if not speech:
                    count_uv += 1

    if total == 0:
        total = 1
    if total_uv == 0:
        total_uv = 1
    return (count/total, count_uv/total_uv)

def get_fine_detail(frames, word, rate):
    '''Print exactly where the VAD detected speech'''
    frame_width = second_to_frame(SAMPLE_SIZE/1000, rate)
    minTime = float(word.minTime)
    maxTime = float(word.maxTime-word.minTime)
    fine_detail = textgrid.IntervalTier(name="fine_detail",\
                                    minTime=word.minTime,\
                                    maxTime=word.maxTime)
    last_mark = VAD[2].is_speech(frames[0:frame_width], rate)
    start = word.minTime
    duration = second_to_frame(maxTime, rate)
    for t in range(0, duration, frame_width):
        inter = word.indexContaining(t/rate/2+minTime)
        if inter is not None:
            speech = VAD[2].is_speech(frames[t:t+frame_width], rate)
            if last_mark != speech and start != t/rate/2+minTime:
                fine_detail.add(start, min(t/rate/2+minTime, word.maxTime), str(last_mark))
                start = t/rate/2+minTime
                last_mark = speech
    return fine_detail

def unchunked_vad(grid, rate, frames):
    '''VAD of full files'''
    word = grid[grid.getNames().index("word")]
    dur = second_to_frame(grid.maxTime-grid.minTime, rate)
    return get_section_vad(frames, word, dur, rate)

def chunked_vad(grid, rate, frames, wav, get_extra=True, return_qual=False):
    '''VAD of just utterances'''
    utterances = chunk_utterances(grid)
    word = grid[grid.getNames().index("word")]
    phones = grid[grid.getNames().index("phone")]
    ratio_list = []


    if OUTPUT_UTTERANCES:
        quality = textgrid.IntervalTier(name="quality",\
                                        minTime=word.minTime,\
                                        maxTime=word.maxTime)
    for u in utterances:
        u_words = word[u]
        u_duration = u_words[-1].maxTime - u_words[0].minTime
        dur = second_to_frame(u_duration, rate)
        offset = second_to_frame(u_words[0].minTime-word.minTime, rate)
        ratio = get_section_vad(frames, word, dur, rate, offset=offset, utterance=u_duration) 
        ratio_list += [((u_words[0].minTime, u_words[-1].maxTime), ratio)]
        if OUTPUT_UTTERANCES:
            quality.add(u_words[0].minTime, u_words[-1].maxTime, "{:.2f}".format(ratio[0]))

    if get_extra:
        swipe_feat = get_custom_features(wav, quality, phones)
        for i in range(len(swipe_feat[0][1])):
            swipe_features = textgrid.IntervalTier(name="swipe_features_{}".format(i),\
                                           minTime=grid.minTime,\
                                           maxTime=grid.maxTime)
            for phone in phones:
                for (feat_phone, feature) in swipe_feat:
                    if phone == feat_phone:
                        swipe_features.add(phone.minTime, phone.maxTime, str(feature[i]))
                        break
            grid.append(swipe_features)

    if return_qual:
        return quality

    if OUTPUT_UTTERANCES:
        grid.append(quality)
        if OUTPUT_FINE:
            grid.append(get_fine_detail(frames, word, rate))
        grid.write(f"{OUTPUT_DIR}/{grid.name.split('.TextGrid')[0]}_chunked.TextGrid")
    return ratio_list

def get_vad_ratio(grid):
    '''For a given textgrid, find what proportion of it is speech'''
    wav = f"{grid.name.split('_')[0]}.wav"
    if os.path.isfile(f"wavs/{wav}"):
        (rate, frames) = get_frames(wav, grid)
        grid = examine_phonemes(grid)

        if CHUNKED_FILES:
            return chunked_vad(grid, rate, frames, wav)
        else:
            return unchunked_vad(grid, rate, frames)
    print(f"{wav} is not a file")
    return None

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Please provide a path to textgrids")
        sys.exit(2)

    #Get any wavs that aren't already stored locally
    WAVS = list(filter(lambda x: not os.path.isfile(f"wavs/{x}"), \
            [f"{x.split('/')[-1].split('_')[0]}.wav" for x in sys.argv[1:]]))
    if WAVS:
        print("Couldn't find associated wav, retrieving...")
        SCP_ARGS = ["scp"] + ["{}{}".format(WAV_DIRECTORY, x) for x in WAVS] + ["wavs/"]
        print(" ".join(SCP_ARGS))
        subprocess.run(SCP_ARGS)

    #Iterate through arguments and find their VAD percentages
    values = []
    for i, arg in enumerate(sys.argv[1:]):
        try:
            print(f"{i/len(sys.argv)}%")
            if not os.path.isfile(arg):
                print("{} is not a valid file".format(arg))
            arg_grid = textgrid.TextGrid(name=arg.split("/")[-1])
            arg_grid.read(arg)
            if CHUNKED_FILES:
                values += [(arg_grid.name, get_vad_ratio(arg_grid))]
            else:
                ratio = get_vad_ratio(arg_grid)
                values += [(arg_grid.name, ratio[0], ratio[1], arg_grid.maxTime-arg_grid.minTime)]
        except (ValueError, AttributeError) as e:
            print(f"{arg_grid.name} can't load")
            raise e

    if not CHUNKED_FILES:
        values.sort(key=lambda x: x[1], reverse=True)

    #Print output
    if CHUNKED_FILES:
        with open('good_and_bad_files_chunked', 'w') as f:
            f.write("file, utterance, VADinSpeech, VADinSilence\n")
            for ratio in values:
                for x in ratio[1]:
                    f.write(f"{ratio[0]}, {x[0][0]}:{x[0][1]}, {x[1][0]}, {x[1][1]}\n")
    else:
        with open('good_and_bad_files', 'w') as f:
            f.write("file, duration, VADinSpeech, VADinSilence\n")
            for x in values:
                f.write(f"{x[0]}, {x[3]}, {x[1]}, {x[2]}\n")
