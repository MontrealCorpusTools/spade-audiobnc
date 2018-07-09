import textgrid
import os
from scipy.io.wavfile import read
from Signal_Analysis.features.signal import get_HNR
from classify_good import get_frames, chunked_vad

MFA_OUTPUT = "/home/linguistics/mgooda2/pipeline/output"
BNC_INPUT =  "/home/linguistics/mgooda2/pipeline/corpus_for_mfa"
BNC_TEXTGRIDS =  "/home/linguistics/mgooda2/pipeline/input"
CHUNKED_DIR = "classify_grids"
textgrids = [f for f in os.listdir(BNC_INPUT) if f.endswith(".TextGrid")]
orig_textgrids = os.listdir(BNC_TEXTGRIDS)

def calculate_difference(x, y):
    '''Given two lists of intervals of equal length, calculate the difference in mapping'''
    assert len(x) == len(y)
    diff = 0
    for a, b in zip(x,y):
        diff += abs(a.maxTime - b.maxTime)
    return diff/len(x)

def calculate_hnr(wav, utterances):
    rate, frames = read(f"{BNC_INPUT}/{wav}")
    harmonicity = textgrid.IntervalTier("hnr", utterances.minTime, utterances.maxTime)
    for utterance in utterances:
        if utterance.mark == "":
            continue
        bounds = utterance.bounds()
        idx = slice(int(rate*(bounds[0]-utterances.minTime)), \
                    int(rate*(bounds[1]-utterances.minTime))  )
        hnr = get_HNR(frames[idx], rate)
        harmonicity.add(bounds[0], bounds[1], str(hnr))
    return harmonicity
problematic_files = []
for i, grid_name in enumerate(textgrids):
    print(f"{i+1}/{len(textgrids)}")
    try:
        for x in orig_textgrids:
            if grid_name.split('.')[0] in x:
                orig_name = x
                break
        bnc_grid = textgrid.TextGrid()
        ut_grid = textgrid.TextGrid()
        mfa_grid = textgrid.TextGrid()
        bnc_grid.read(f"{BNC_TEXTGRIDS}/{orig_name}")
        ut_grid.read(f"{BNC_INPUT}/{grid_name}")
        mfa_grid.read(f"{MFA_OUTPUT}/{grid_name}")

        utterances = ut_grid[ut_grid.getNames().index("speaker")]
        bnc_words = bnc_grid[bnc_grid.getNames().index("word")]
        mfa_words = mfa_grid[mfa_grid.getNames().index("speaker - words")]
        bnc_phones = bnc_grid[bnc_grid.getNames().index("phone")]
        mfa_phones = mfa_grid[mfa_grid.getNames().index("speaker - phones")]
        quality = textgrid.IntervalTier("quality", bnc_grid.minTime, bnc_grid.maxTime)
        mfa_found = textgrid.IntervalTier("mfa_found", bnc_grid.minTime, bnc_grid.maxTime)
        for utterance in utterances:
            if utterance.mark  == "":
                continue
            bnc_slice = slice(bnc_phones.indexContaining(float(utterance.minTime+bnc_grid.minTime)+0.001), \
                              bnc_phones.indexContaining(float(utterance.maxTime+bnc_grid.minTime)-0.001) + 1)
            mfa_slice = slice(mfa_phones.indexContaining(float(utterance.minTime)+0.001), \
                              mfa_phones.indexContaining(float(utterance.maxTime)-0.001) + 1)
            bnc_utterance = [x for x in bnc_phones[bnc_slice] if x.mark not in ["sp", "sil"]]
            stop = bnc_utterance[-1].maxTime
            start = bnc_utterance[0].minTime
            bnc_utterance = [textgrid.Interval(x.minTime-bnc_grid.minTime, x.maxTime-bnc_grid.minTime, x.mark) for x in bnc_utterance]
            mfa_utterance = [x for x in mfa_phones[mfa_slice] if x.mark not in ["sp", "", "sil"]]
            if len(bnc_utterance) != len(mfa_utterance):
                quality.add(start, stop, "0")
                mfa_found.add(start, stop, "0")
            else:
                quality.add(start, stop, str(float(calculate_difference(bnc_utterance, mfa_utterance))))
                mfa_found.add(start, stop, "1")

        wav = "{}.wav".format(orig_name.split('.TextGrid')[0])
        out_grid_name = "{}/{}_chunked.TextGrid".format(CHUNKED_DIR, orig_name.split('.')[0])
        out_grid = textgrid.TextGrid(name=out_grid_name, minTime=bnc_grid.minTime, maxTime=bnc_grid.maxTime)
        new_words = textgrid.IntervalTier( "mfa-words", bnc_grid.minTime, bnc_grid.maxTime)
        new_words.intervals = [textgrid.Interval(x.minTime+bnc_grid.minTime, x.maxTime+bnc_grid.minTime, x.mark) for x in mfa_words]
        new_phones = textgrid.IntervalTier( "mfa-phones", bnc_grid.minTime, bnc_grid.maxTime)
        new_phones.intervals = [textgrid.Interval(x.minTime+bnc_grid.minTime, x.maxTime+bnc_grid.minTime, x.mark) for x in mfa_phones]

        out_grid.append(calculate_hnr(wav, quality))
        out_grid.append(bnc_words)
        out_grid.append(bnc_phones)
        out_grid.append(new_words)
        out_grid.append(new_phones)
        out_grid.append(quality)
        out_grid.append(mfa_found)
        out_grid.write(out_grid_name)
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        print(f"problematic file, {grid_name}")
        problematic_files += [grid_name]

with open("bad_files.txt", "a+") as f:
    for x in problematic_files:
        f.write(f"{x}\n")
