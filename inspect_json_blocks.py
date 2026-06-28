import re
import json

with open("d:/DeepScribe/character_matches.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Let's find JSON blocks
# A JSON block might be enclosed between { and }
# We can search for { and } with regex or a simple stack parser

json_blocks = []
start_idx = 0
while True:
    idx = content.find('{', start_idx)
    if idx == -1:
        break
    # parse bracket match
    brace_count = 0
    end_idx = -1
    for i in range(idx, len(content)):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i
                break
    if end_idx != -1:
        block = content[idx:end_idx+1]
        try:
            parsed = json.loads(block)
            json_blocks.append(parsed)
        except Exception as e:
            pass
        start_idx = end_idx + 1
    else:
        start_idx = idx + 1

print(f"Found {len(json_blocks)} valid JSON blocks.")
for idx, b in enumerate(json_blocks[:10]):
    print(f"\nBlock {idx}: keys = {list(b.keys())}")
    if "name" in b:
        print(f"Name: {b.get('name')}")
    else:
        print("Name not in keys")
    # print snippet
    print(str(b)[:200])
