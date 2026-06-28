import sys
import re
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

idx = 0
while True:
    idx = data.find(b'"personality":', idx)
    if idx == -1:
        break
    start_brace = data.rfind(b'{', 0, idx)
    if start_brace != -1:
        end_brace = -1
        brace_count = 0
        for i in range(start_brace, len(data)):
            if data[i] == ord('{'):
                brace_count += 1
            elif data[i] == ord('}'):
                brace_count -= 1
                if brace_count == 0:
                    end_brace = i
                    break
        if end_brace != -1:
            block = data[start_brace:end_brace+1]
            print(f"\n--- Block at {start_brace} ---")
            name_match = re.search(br'"name"\s*:\s*"([^"]+)"', block)
            if name_match:
                name_bytes = name_match.group(1)
                print("Name bytes (hex):", name_bytes.hex())
                print("Name decoded UTF-8 (replace):", name_bytes.decode("utf-8", errors="replace"))
            else:
                print("No name match")
    idx += 1
    if idx > 1500000:
        break
