import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

# Let's search for "### **[제1장: 서사 및 표현에 관한 절대 규율]**"
pattern = "### **[제1장: 서사 및 표현에 관한 절대 규율]**".encode("utf-8")
idx = 0
while True:
    idx = data.find(pattern, idx)
    if idx == -1:
        break
    print(f"Found system prompt candidate at {idx}:")
    # Grab 4000 bytes starting from idx
    snippet = data[idx:idx+4000]
    text = snippet.decode("utf-8", errors="replace")
    print(text[:1500])
    print("..." * 10)
    idx += len(pattern)
