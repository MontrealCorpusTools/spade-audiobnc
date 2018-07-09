
phones = set()
with open("phones", "r") as f:
    for x in f:
         x = x.strip().split(" ")
         phones.update(x)
print(phones)
