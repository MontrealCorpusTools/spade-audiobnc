import sys
import os
import textgrid
import wave
from decimal import *
from classify_good import chunk_utterances
from output_dictionary import get_spelling

OUTPUT_DIR = "corpus_for_mfa"
WAV_DIR = "wavs"
NON_SPEECH = ["NS", "LG", "CG", "BR", "LS", "NS1Q"]
def crop_wav(wav, out, start, stop):
    with wave.open(wav, "rb") as wf:
        rate = wf.getframerate()
        with wave.open(out, "wb") as out_wav:
            out_wav.setparams(wf.getparams())
            start_pos = int(start*rate)
            stop_pos = int(stop*rate)
            wf.setpos(start_pos)
            frames = wf.readframes(stop_pos-start_pos)
            out_wav.writeframes(frames)

lexicon = {}
with open("pronunciation.txt", "r") as f:
    for l in f.readlines():
        l = l.strip().split(" ")
        word = l[0]
        spelling = " ".join(l[1:])
        lexicon[spelling] = word

def remap_words(word, phones):
    spelling = get_spelling(word, phones)
    if spelling in NON_SPEECH:
        return lexicon["spn"]
    return lexicon[spelling]


for i, arg in enumerate(sys.argv[1:]):
    print(f"{i/len(sys.argv)}%")
    if not os.path.isfile(arg):
        print("{} is not a valid file".format(arg))
        continue
    try:
        grid = textgrid.TextGrid(name=arg.split("/")[-1])
        grid.read(arg)
    except (AttributeError, ValueError):
        print(f"{arg.split('/')[-1]} can't load")
        continue
    utterances = chunk_utterances(grid)
    words = grid[grid.getNames().index("word")]
    phones = grid[grid.getNames().index("phone")]
    wav = grid.name.split('_')[0]
    name = grid.name.split('.TextGrid')[0]

    crop_wav(f"{WAV_DIR}/{wav}.wav", f"{OUTPUT_DIR}/{name}.wav", grid.minTime, grid.maxTime)
    out_grid = textgrid.TextGrid(name)
    speaker = textgrid.IntervalTier("speaker", 0, grid.maxTime-grid.minTime)
    for i, utterance in enumerate(utterances):
        utterance_text = ""
        maxTime = words[utterance.stop-1].maxTime-grid.minTime
        minTime = words[utterance.start].minTime-grid.minTime
        for word in words[utterance]:
            if word.mark != "sp":
                utterance_text += " " + remap_words(word, phones)
        speaker.add(minTime, maxTime, utterance_text.strip())

    out_grid.append(speaker)
    out_grid.write(f"{OUTPUT_DIR}/{grid.name}")

