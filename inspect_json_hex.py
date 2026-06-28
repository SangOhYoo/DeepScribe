import json

with open("d:/DeepScribe/character_matches.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Let's extract and parse the first few valid JSON blocks
json_blocks = []
start_idx = 0
while True:
    idx = content.find('{', start_idx)
    if idx == -1:
        break
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

print(f"Parsed {len(json_blocks)} JSON blocks.")
for i, block in enumerate(json_blocks[:5]):
    print(f"\n--- BLOCK {i} ---")
    for k, v in block.items():
        # print the key and representation of the value (showing unicode escapes if not ascii)
        print(f"  {k}: {repr(v)}")
