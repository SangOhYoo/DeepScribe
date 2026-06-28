import re

with open("d:/DeepScribe/recovered_strings.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Let's search for characters, prompts, scenario nodes for project 8.
# Project 8 characters include "스미래", "히로시", "후미애", and the grandmother/mother-in-law character.
# We will search for all blocks containing these names and print them out.

print("Scanning for characters...")
char_keywords = ["스미래", "히로시", "후미애", "시어머니", "하숙생과 미망인"]
for kw in char_keywords:
    matches = [m.start() for m in re.finditer(kw, text)]
    print(f"Keyword '{kw}' found {len(matches)} times.")

# Let's dump all sections around "하숙생과 미망인"
with open("d:/DeepScribe/extracted_project8_blocks.txt", "w", encoding="utf-8") as out:
    # Find all occurrences of "하숙생과 미망인"
    for m in re.finditer("하숙생과 미망인", text):
        idx = m.start()
        start = max(0, idx - 500)
        end = min(len(text), idx + 2000)
        out.write(f"\n================ OFFSET {idx} (하숙생과 미망인) ================\n")
        out.write(text[start:end])
        out.write("\n")
        
    # Find all occurrences of "스미래"
    # We want to find character profiles, so let's look for "스미래 /" or "히로시 /" or "후미애 /"
    for pattern in ["스미래 /", "히로시 /", "후미애 /"]:
        for m in re.finditer(pattern, text):
            idx = m.start()
            start = max(0, idx - 100)
            end = min(len(text), idx + 1500)
            out.write(f"\n================ CHARACTER PROFILE OFFSET {idx} ({pattern}) ================\n")
            out.write(text[start:end])
            out.write("\n")

print("Finished extracting blocks.")
