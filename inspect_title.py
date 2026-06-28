with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

# Let's look at the first match of "동정-스미래"
utf8_title = "동정-스미래".encode("utf-8")
idx = data.find(utf8_title)
if idx != -1:
    print(f"Found title at offset {idx}")
    sample = data[max(0, idx-100):min(len(data), idx+300)]
    print("Raw bytes:", sample)
    print("Decoded UTF-8 (replace):", sample.decode("utf-8", errors="replace"))
    print("Decoded CP949 (replace):", sample.decode("cp949", errors="replace"))
else:
    print("Title not found")
