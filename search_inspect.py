import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/inspect_output.txt", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
count = 0
for idx, line in enumerate(lines):
    if "스미래" in line:
        print(f"Line {idx}: {line.strip()[:150]}")
        count += 1
        if count >= 30:
            print("Truncating...")
            break
