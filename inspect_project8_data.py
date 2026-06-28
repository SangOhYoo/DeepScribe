import re
import json

with open("d:/DeepScribe/extracted_clean_project8.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
# Let's search for characters and scenario nodes in the text
content = "".join(lines)

# Print unique name listings
names_found = set(re.findall(r'([가-힣\w\s]+)\s*/\s*\d+세', content))
print("Names with age pattern:", names_found)

# Let's inspect the file structure
# Look at headers or specific markers
sections = []
for idx, line in enumerate(lines):
    if line.startswith("===") or line.startswith("---"):
        sections.append((idx, line.strip()))

print("Headers found in extracted_clean_project8.txt:")
for sec in sections[:30]:
    print(sec)
