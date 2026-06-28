import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

pattern = "### **[제1장: 서사 및 표현에 관한 절대 규율]**".encode("utf-8")
idx = 0
match_count = 0
while True:
    idx = data.find(pattern, idx)
    if idx == -1:
        break
    match_count += 1
    print(f"\n--- Occurrence {match_count} at offset {idx} ---")
    snippet = data[idx:idx+6000].decode("utf-8", errors="replace")
    print(snippet[:1500])
    print("..." * 20)
    idx += len(pattern)
