import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Load raw database strings
with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

# We will search for all JSON blocks in the raw data
# and check if they represent our target characters.
# Target names: 히로시, 스미래, 후미애, 타카시, 할머니, 시어머니
target_names = ["히로시", "스미래", "후미애", "타카시", "시어머니", "할머니", "하숙집"]

def is_target_char(char_dict):
    name = char_dict.get("name", "")
    # Check if name contains any of target names
    if any(tn in name for tn in target_names):
        return True
    # Check if personality/background contains "히로시" or "스미래"
    pers = char_dict.get("personality", "")
    bg = char_dict.get("background", "")
    if "스미래" in pers or "스미래" in bg or "히로시" in pers or "히로시" in bg:
        return True
    return False

# Find JSON objects
idx = 0
parsed_chars = []
seen_signatures = set() # To avoid duplicates

while True:
    idx = data.find(b'"personality":', idx)
    if idx == -1:
        break
    start_brace = data.rfind(b'{', 0, idx)
    if start_brace != -1:
        # Match braces
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
                char_dict = json.loads(block.decode("utf-8"))
                if is_target_char(char_dict):
                    # Create a unique signature based on name and relations
                    sig = (char_dict.get("name"), char_dict.get("relations"), len(char_dict.get("personality", "")))
                    if sig not in seen_signatures:
                        seen_signatures.add(sig)
                        parsed_chars.append(char_dict)
            except Exception:
                pass
    idx += 1

# Let's clean up and choose the best version of each character
# (the one with the most filled details)
best_chars = {}
for c in parsed_chars:
    name = c.get("name", "").strip()
    # Normalize name (e.g. remove age info or extra spaces)
    # Names are: "히로시", "스미래", "후미애", "타카시", "하숙집 할머니" (or "시어머니")
    norm_name = None
    if "스미래" in name:
        norm_name = "스미래"
    elif "히로시" in name:
        norm_name = "히로시"
    elif "후미애" in name:
        norm_name = "후미애"
    elif "타카시" in name:
        norm_name = "타카시"
    elif "할머니" in name or "시어머니" in name:
        norm_name = "하숙집 할머니"
    
    if not norm_name:
        continue
        
    # We want the one with the maximum total detail length
    detail_len = sum(len(str(v)) for v in c.values() if v is not None)
    if norm_name not in best_chars or detail_len > best_chars[norm_name]["length"]:
        best_chars[norm_name] = {
            "data": c,
            "length": detail_len
        }

output_chars = {name: item["data"] for name, item in best_chars.items()}

# Let's save to file
with open("d:/DeepScribe/recovered_project8_characters.json", "w", encoding="utf-8") as out_f:
    json.dump(output_chars, out_f, indent=2, ensure_ascii=False)

print(f"Extraction complete. Found target characters: {list(output_chars.keys())}")
for name, c in output_chars.items():
    print(f"Character: {name}")
    print(f"  Keys present: {list(c.keys())}")
    print(f"  Personality len: {len(c.get('personality') or '')}")
