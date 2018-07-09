import sys
import os
import textgrid
import numpy as np

def linear_classifier(X):
    return X["word-number"] > 1 and X["duration"] > 1 and X["mfa_found"] == 1 and X["hnr"] > 5.4 and X["alignment-diff"] < 0.03

OUTPUT_DIR = "out_with_labels"
uts = 0
good_uts = 0

for i, arg in enumerate(sys.argv[1:]):
    if not os.path.isfile(arg):
        print("{} is not a valid file".format(arg))
    arg_grid = textgrid.TextGrid(name=arg.split("/")[-1])
    arg_grid.read(arg)
    classification = textgrid.IntervalTier(name="classification", minTime=arg_grid.minTime, maxTime=arg_grid.maxTime)
    word = arg_grid[arg_grid.getNames().index("word")]
    hnr_quality = arg_grid[arg_grid.getNames().index("hnr")]
    mfa_found =  arg_grid[arg_grid.getNames().index("mfa_found")]
    for utterance in arg_grid[arg_grid.getNames().index("quality")]:
        bounds = slice(word.indexContaining(float(utterance.minTime)+0.001), \
                         word.indexContaining(float(utterance.maxTime)-0.001) + 1)
        hnr_index = hnr_quality.indexContaining(utterance.minTime + utterance.duration()/2)
        mfa_index = mfa_found.indexContaining(utterance.minTime + utterance.duration()/2)
        if utterance.mark != "":
            X = {"duration": float(utterance.duration()),
                 "alignment-diff": float(utterance.mark),
                 "hnr": float(hnr_quality[hnr_index].mark),
                 "mfa_found": float(mfa_found[mfa_index].mark),
                 "word-number": len(word[bounds])}
            if X["duration"] > 1 and X["word-number"] > 1:
                uts += 1 
            try:
                if linear_classifier(X):
                    good_uts += 1
                    y = "good"
                else:
                    y = "bad"
            except ValueError:
                y = "bad"
            classification.add(utterance.minTime, utterance.maxTime, y)
    arg_grid.append(classification)
    arg_grid.write(f"{OUTPUT_DIR}/{arg_grid.name.split('.TextGrid')[0]}_labeled.TextGrid")
print(f"Good utterances over total {good_uts}/{uts}")
