import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

# Let's search for "동정-스미래" as bytes
title_bytes = "동정-스미래".encode("utf-8")
idx = 0
while True:
    idx = data.find(title_bytes, idx)
    if idx == -1:
        break
    print(f"\n--- Found '동정-스미래' at offset {idx} ---")
    # Let's grab 1000 bytes before and 2000 bytes after
    snippet = data[max(0, idx-1000):min(len(data), idx+3000)]
    # Decode with errors='replace'
    text = snippet.decode("utf-8", errors="replace")
    print(text[:1500])
    print("="*40)
    idx += len(title_bytes)
