import textgrid
import sys

NON_SPEECH = ["NS", "LG", "CG", "BR", "LS", "NS1Q"]
lexicon = {}
REMAP = {**{"OH{}".format(i): "AO{}".format(i) for i in range(3)}, **{"SP":"SIL"}}
dups = {}

def remap_phones(phone):
    if phone in REMAP:
        return REMAP[phone]
    return phone

def get_spelling(word, phones):
    bounds = slice(phones.indexContaining(float(word.minTime)+0.001), \
                   phones.indexContaining(float(word.maxTime)-0.001) + 1)
    spelling = ""
    for phone in phones[bounds]:
        spelling += " "+remap_phones(phone.mark.upper())
    return spelling.strip()

if __name__ == "__main__":
    problematic_files = []
    for i, filename in enumerate(sys.argv[1:]):
        try:
            grid = textgrid.TextGrid(name=filename)
            grid.read(filename)
        except (AttributeError, ValueError):
            print(f"{filename} can't load")
            problematic_files.append(filename)
            continue
        phones = grid[grid.getNames().index("phone")]
        words = grid[grid.getNames().index("word")]
        for word in words:
            spelling = get_spelling(word, phones)
            word = word.mark.strip().upper().replace("{", "").replace("}", "")
            if word in lexicon:
                if spelling != lexicon[word]:
                    if word not in dups:
                        dups[word] = 0
                        lexicon[f"{word}0"] = spelling
                    else:
                        alt_spellings = [lexicon[f"{word}{i}"] for i in range(dups[word]+1)]
                        if spelling not in alt_spellings:
                            dups[word] += 1
                            lexicon[f"{word}{dups[word]}"] = spelling
            else:
                lexicon[word] = spelling
        print(f"{i+1}/{len(sys.argv[1:])}")
    with open("pronunciation.txt", 'w') as f:
        for k, v in lexicon.items():
            if v in NON_SPEECH:
                f.write(f"{k} spn\n")
            else:
                f.write(f"{k} {v}\n")
    with open("bad_files.txt", "w") as f:
        for x in problematic_files:
            f.write(f"{x}\n")
