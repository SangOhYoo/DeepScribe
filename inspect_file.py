# -*- coding: utf-8 -*-
with open("abyss_writer/ui.py", "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

with open("output_inspect.txt", "w", encoding="utf-8") as out:
    for idx in range(1640, 1815):
        if idx < len(lines):
            out.write(f"Line {idx+1}: {lines[idx]}")
