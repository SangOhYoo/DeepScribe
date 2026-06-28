import re
import sys

# Reconfigure stdout to support utf-8 in case we want to print
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

with open("d:/DeepScribe/extracted_clean_project8.txt", "r", encoding="utf-8") as f:
    text = f.read()

out_lines = []
def log(msg):
    out_lines.append(msg + "\n")

# Let's search for character profiles (looks like JSON format in some offsets!)
log("=== CHARACTER PROFILES (JSON OR TEXT) ===")
# Search for JSON character properties
for m in re.finditer(r'"personality"|스미래 /', text):
    start = max(0, m.start() - 100)
    end = min(len(text), m.start() + 1500)
    log(f"Offset {m.start()}:")
    log(text[start:end])
    log("-" * 80)

# Let's search for nodes
log("\n=== SCENARIO NODES ===")
for m in re.finditer(r"(?:기 \(起 - 도입\)|승 \(承 - 전개\)|전 \(轉 - 위기/절정\)|결 \(結 - 결말\))", text):
    start = max(0, m.start() - 50)
    end = min(len(text), m.start() + 1000)
    log(f"Node Match at {m.start()}:")
    log(text[start:end])
    log("-" * 80)

with open("d:/DeepScribe/inspect_output.txt", "w", encoding="utf-8") as out_f:
    out_f.writelines(out_lines)

print("Finished! Output written to inspect_output.txt")

