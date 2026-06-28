import json
import re

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

# Let's search for JSON patterns that represent characters
# Example: {"name": "...", "relations": "...", ...}
# We can search for the byte sequence '"name":' or similar.
# Since JSON might be raw text, let's search for '"personality":' and find matching braces
idx = 0
chars = []
while True:
    idx = data.find(b'"personality":', idx)
    if idx == -1:
        break
    # Find start brace before it
    start_brace = data.rfind(b'{', 0, idx)
    if start_brace != -1:
        # Find matching end brace
        brace_count = 0
        end_brace = -1
        for i in range(start_brace, len(data)):
            if data[i] == ord('{'):
                brace_count += 1
            elif data[i] == ord('}'):
                brace_count -= 1
                if brace_count == 0:
                    end_brace = i
                    break
        if end_brace != -1:
            block = data[start_brace:end_brace+1]
            try:
                # Let's decode block as UTF-8
                char_json = json.loads(block.decode("utf-8"))
                if char_json not in chars:
                    chars.append(char_json)
            except Exception:
                pass
    idx += 1

print(f"Found {len(chars)} unique characters:")
for i, c in enumerate(chars):
    print(f"\nCharacter {i}:")
    for k, v in c.items():
        print(f"  {k}: {v}")
