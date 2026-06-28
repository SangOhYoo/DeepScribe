import re

with open("d:/DeepScribe/recovered_strings.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Let's search for "시어머니" or "친정어머니" and display their surrounding text to identify the exact character name.
print("--- Searching for mother-in-law / grandmother ---")
for m in re.finditer(r"(?:시어머니|친정어머니|할머니)", text):
    start = max(0, m.start() - 200)
    end = min(len(text), m.start() + 300)
    print(f"Offset {m.start()}:")
    print(text[start:end])
    print("-" * 50)
