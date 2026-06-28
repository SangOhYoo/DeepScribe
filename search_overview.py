import os
import re

def main():
    brain_dir = r"C:\Users\SangO\.gemini\antigravity\brain"
    if not os.path.exists(brain_dir):
        print(f"Directory {brain_dir} does not exist.")
        return
        
    print(f"Searching for '등록' or 'trs' or 'register' in {brain_dir}...")
    for root, dirs, files in os.walk(brain_dir):
        for f in files:
            if f == "overview.txt":
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8") as file:
                        content = file.read()
                    matches = []
                    for line_num, line in enumerate(content.split("\n"), 1):
                        if "trs" in line or "등록" in line or "register" in line:
                            matches.append((line_num, line))
                    if matches:
                        print(f"\nMatch in: {path}")
                        for ln, line in matches[:10]: # Print first 10 matches
                            print(f"  Line {ln}: {line[:120]}")
                        if len(matches) > 10:
                            print(f"  ... and {len(matches)-10} more matches")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    main()
