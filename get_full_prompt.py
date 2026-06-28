import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

# Let's find "### **[제1장: 서사 및 표현에 관한 절대 규율]**"
pattern = "### **[제1장: 서사 및 표현에 관한 절대 규율]**".encode("utf-8")
idx = data.find(pattern)
if idx != -1:
    print(f"Found at index {idx}")
    # Let's find where the next major section starts (e.g. character names or JSON blocks)
    # The next section in the dump might start with something else.
    # Let's find how long it is by searching for some known keywords, or look at next 8000 bytes.
    snippet = data[idx:idx+8000].decode("utf-8", errors="replace")
    
    # We want to find the exact ending of the prompt.
    # Typically, the system prompt contains section headers and ends with something like "작성할 것" or similar.
    # Let's write the snippet to a text file so we can view it.
    with open("d:/DeepScribe/extracted_prompt_raw.txt", "w", encoding="utf-8") as out_f:
        out_f.write(snippet)
    print("Saved raw prompt snippet of size", len(snippet))
else:
    print("Pattern not found!")
