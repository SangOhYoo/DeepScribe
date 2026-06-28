import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

# Let's search for occurrences of "동정-스미래" and print the bytes around it,
# particularly searching for any text blocks that look like the overall plot, positive prompt, negative prompt.
search_bytes = "동정-스미래".encode("utf-8")
idx = 0
while True:
    idx = data.find(search_bytes, idx)
    if idx == -1:
        break
    print(f"\n--- MATCH AT {idx} ---")
    start = max(0, idx - 500)
    end = min(len(data), idx + 8000)
    snippet = data[start:end]
    # To find structural fields, let's split by some control chars or null bytes or typical DB separator patterns.
    # In SQLite, table rows are stored consecutively.
    # Let's decode and show lines
    lines = snippet.decode("utf-8", errors="replace").split("\n")
    for line in lines[:40]:
        if any(keyword in line for keyword in ["줄거리", "프롬프트", "목차", "스미래", "히로시", "하숙", "Draft", "Positive", "Negative"]):
            print("  ", line.strip()[:200])
    idx += len(search_bytes)
