import re

path = "d:/DeepScribe/dry_run_temp/abyss_writer/ui.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's find all function definitions
matches = re.finditer(r"def\s+(\w+)\s*\(", content)
funcs = []
for m in matches:
    funcs.append((m.group(1), m.start()))

with open("ui_functions.txt", "w", encoding="utf-8") as out:
    for i in range(len(funcs)):
        name, start = funcs[i]
        end = funcs[i+1][1] if i + 1 < len(funcs) else len(content)
        func_code = content[start:end]
        # Check if it contains erotic keywords
        keywords = ["case", "erotic", "관능", "psychological", "autofill"]
        if any(kw in func_code.lower() for kw in keywords):
            out.write(f"Function: {name}\n")
            out.write(f"Start char: {start}, End char: {end}\n")
            # count lines
            lines = func_code.strip().split("\n")
            out.write(f"Lines count: {len(lines)}\n")
            out.write(f"First line: {lines[0]}\n")
            out.write(f"Last line: {lines[-1]}\n")
            out.write("-" * 40 + "\n")
