import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

# Let's search for "타카시" in the binary data
search_bytes = "타카시".encode("utf-8")
idx = 0
while True:
    idx = data.find(search_bytes, idx)
    if idx == -1:
        break
    print(f"\n--- Found '타카시' at offset {idx} ---")
    start = max(0, idx - 200)
    end = min(len(data), idx + 1500)
    snippet = data[start:end]
    print(snippet.decode("utf-8", errors="replace"))
    idx += len(search_bytes)
