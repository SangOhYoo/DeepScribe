import re

with open("d:/DeepScribe/recovered_strings.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Find character definitions by matching fields like "히로시", "스미래", "후미애"
# Let's search for character profiles.
# Usually character fields are serialized next to each other.
# We will search for occurrences of "히로시" and print the surrounding lines.
matches = [m.start() for m in re.finditer("히로시", text)]
print(f"Found '히로시' {len(matches)} times.")

with open("d:/DeepScribe/character_matches.txt", "w", encoding="utf-8") as out:
    for idx in matches[:50]: # First 50 occurrences
        start = max(0, idx - 300)
        end = min(len(text), idx + 1000)
        out.write(f"\n================ MATCH AT {idx} ================\n")
        out.write(text[start:end])
        out.write("\n")

print("Written character matches to character_matches.txt")
