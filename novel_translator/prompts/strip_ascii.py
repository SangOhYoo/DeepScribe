import os

src = r"d:\DeepScribe\novel_translator\prompts\templates.py"
dst = r"d:\DeepScribe\novel_translator\prompts\templates_clean.txt"

if os.path.exists(src):
    try:
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        # Keep only ASCII chars
        clean_content = "".join(c if ord(c) < 128 else "?" for c in content)
        
        with open(dst, "w", encoding="utf-8") as f:
            f.write(clean_content)
        print("Success: Wrote templates_clean.txt")
    except Exception as e:
        print(f"Error: {e}")
else:
    print("Source not found")
