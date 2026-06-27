import sys
sys.stdout.reconfigure(encoding='utf-8')

src = r"d:\DeepScribe\novel_translator\prompts\templates.py"
with open(src, "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
    for idx, line in enumerate(lines[55:180], 56):
        print(f"{idx:03d}: {line}", end="")
