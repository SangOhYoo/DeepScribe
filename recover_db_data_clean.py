import sys
import re

with open("d:/DeepScribe/recovered_strings.txt", "r", encoding="utf-8") as f:
    text = f.read()

out_lines = []

def log(msg):
    out_lines.append(msg + "\n")

# Find occurrences of 스미래, 후미애, 히로시, 타카시
log("=== CHARACTERS FOR PROJECT 8 ===")

# Try to find all character profile patterns
# In database.db/models.py, characters have attributes:
# name, personality, background, speech_style, key_quotes, relations, character_relations, physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes
# Let's search for the pattern "스미래 /" or similar
for char_name in ["스미래", "히로시", "후미애", "타카시"]:
    log(f"\n--- Searching for {char_name} ---")
    pattern = char_name + r"\s*/\s*\d+세"
    for m in re.finditer(pattern, text):
        idx = m.start()
        start = max(0, idx - 100)
        end = min(len(text), idx + 2000)
        log(f"Offset {idx}:")
        log(text[start:end])
        log("-" * 80)

# Let's search for "시어머니" or "친정어머니" profiles
log("\n--- Searching for mother-in-law ---")
for m in re.finditer(r"시어머니\(혹은 친정어머니\)", text):
    idx = m.start()
    start = max(0, idx - 400)
    end = min(len(text), idx + 1000)
    log(f"Offset {idx}:")
    log(text[start:end])
    log("-" * 80)

log("\n=== SCENARIO NODES FOR PROJECT 8 ===")
# Search for scenario nodes containing "스미래", "히로시", "후미애"
# Let's search for "기 (起 - 도입)", "승 (承 - 전개)", "전 (轉 - 위기/절정)", "결 (結 - 결말)" in the text
for m in re.finditer(r"(?:기 \(起 - 도입\)|승 \(承 - 전개\)|전 \(轉 - 위기/절정\)|결 \(結 - 결말\))", text):
    # check if this page has 스미래 or 히로시 within 1000 chars
    idx = m.start()
    snippet = text[max(0, idx - 200):min(len(text), idx + 1200)]
    if "스미래" in snippet or "히로시" in snippet or "후미애" in snippet:
        log(f"Offset {idx}:")
        log(snippet)
        log("-" * 80)

with open("d:/DeepScribe/extracted_clean_project8.txt", "w", encoding="utf-8") as out_f:
    out_f.writelines(out_lines)

print("Extraction completed successfully!")
