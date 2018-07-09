import sys
import os
import textgrid
OUTPUT_DIR = "cleaned_textgrids"
IGNORED_TIERS = ["word", "hnr", "quality", "mfa_found", "mfa-words", "mfa-phones", "classification"]

problematic_files = []

for i, arg in enumerate(sys.argv[1:]):
    try:
        if not os.path.isfile(arg):
            print("{} is not a valid file".format(arg))
        arg_grid = textgrid.TextGrid(name=arg.split("/")[-1])
        arg_grid.read(arg)
        tiers = [x for x in arg_grid.tiers if x.name not in IGNORED_TIERS]
        new_tiers = [[] for x in tiers]
        for utterance in arg_grid[arg_grid.getNames().index("classification")]:
            if utterance.mark == "good":
                for tier, new_tier in zip(tiers, new_tiers):
                    bounds = (tier.indexContaining(float(utterance.minTime) + 0.0001), \
                              tier.indexContaining(float(utterance.maxTime) - 0.0001) + 1)
                    for j in range(bounds[0], bounds[1]):
                        interval = tier.intervals[j]
                        if interval.minTime >= utterance.minTime and interval.maxTime <= utterance.maxTime:
                            new_tier.append(interval)

        out_grid = textgrid.TextGrid(name=arg.split("/")[-1], minTime=arg_grid.minTime, maxTime=arg_grid.maxTime)
        for tier, new_tier in zip(tiers, new_tiers):
            out_tier = textgrid.IntervalTier(tier.name, tier.minTime, tier.maxTime)
            out_tier.intervals = new_tier
            out_grid.append(out_tier)
        out_grid.write(f"{OUTPUT_DIR}/{arg_grid.name.split('.TextGrid')[0]}_cleaned.TextGrid")
        print(f"{i+1}/{len(sys.argv[1:])}")
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        print(f"problematic file, {arg}")
        problematic_files += [arg]

with open("bad_files.txt", "a+") as f:
    for x in problematic_files:
        f.write(f"{x}\n")
