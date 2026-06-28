import re
import json

with open("d:/DeepScribe/recovered_strings.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Let's search for characters and any json blocks containing personality or background
results = []

# Search for JSON blocks
# JSON blocks usually start with { or [ and contain keys like "personality", "background", "secret_taboo"
matches = re.finditer(r'\{[^{}]*?"personality"[^{}]*?\}', text)
for m in matches:
    results.append(f"--- JSON Match at {m.start()} ---\n" + m.group(0) + "\n\n")

# Search for name / age patterns
for name in ["스미래", "히로시", "후미애", "타카시", "시어머니"]:
    matches = re.finditer(name + r"\s*/\s*\d+세", text)
    for m in matches:
        start = max(0, m.start() - 100)
        end = min(len(text), m.start() + 2000)
        results.append(f"--- TEXT Match for {name} at {m.start()} ---\n" + text[start:end] + "\n\n")

with open("d:/DeepScribe/character_matches.txt", "w", encoding="utf-8") as out_f:
    out_f.writelines(results)

print("Character matches written to character_matches.txt")
