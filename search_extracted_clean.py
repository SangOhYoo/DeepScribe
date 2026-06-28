import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/extracted_clean_project8.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Let's search for "Searching for 타카시" or "Searching for Ÿī" or similar
# Wait, in inspect_project8_data.py it printed: "--- Searching for Ÿī ---"
# Let's find index of "Searching for" and extract that part
idx = 0
while True:
    idx = content.find("Searching for", idx)
    if idx == -1:
        break
    # Get 1000 characters
    print(f"\n--- MATCH AT {idx} ---")
    print(content[idx:idx+1500])
    idx += len("Searching for")
    if idx > 100000: # just see first few
        break
