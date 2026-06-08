import json
import random

chunks = json.loads(open("chunks.json", encoding="utf-8").read())
print("Total chunks:", len(chunks))
print()

random.seed(42)
picks = random.sample(chunks, 5)

for i, c in enumerate(picks, 1):
    print("=" * 72)
    print("[{}] id={} | property={} | source={} | words={}".format(
        i, c["id"], c["property_name"], c["source"], c["word_count"]))
    print("-" * 72)
    print(c["text"].encode("ascii", errors="replace").decode("ascii"))
    print()
