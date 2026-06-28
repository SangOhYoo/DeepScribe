import re

with open("d:/DeepScribe/recovered_strings.txt", "r", encoding="utf-8") as f:
    text = f.read()

out_lines = []

def log(msg):
    out_lines.append(msg + "\n")

log("=== SCENARIO NODES DETAILED SEARCH ===")

# Search for any block containing stage indicators and keywords like "스미래", "히로시", "후미애"
pattern = r"(?:기\s*\(起\s*-\s*도입\)|승\s*\(承\s*-\s*전개\)|전\s*\(轉\s*-\s*위기/절정\)|결\s*\(結\s*-\s*결말\))"

matches = list(re.finditer(pattern, text))
log(f"Found {len(matches)} matches of stage patterns.")

seen_contents = set()

for i, m in enumerate(matches):
    idx = m.start()
    # Grab a window around the match
    start = max(0, idx - 150)
    end = min(len(text), idx + 1500)
    window = text[start:end]
    
    # We want to identify if it is related to Project 8
    # Keywords: 스미래, 히로시, 후미애, 타카시, 할머니, 아유꼬, 금단의 갈증
    keywords = ["스미래", "히로시", "후미애", "타카시", "할머니", "아유꼬", "금단의 갈증", "하숙집", "미망인"]
    if any(k in window for k in keywords):
        # Clean up window for logging
        # To avoid logging the same text repeatedly if matches are close
        snippet = window[:1000]
        if snippet not in seen_contents:
            seen_contents.add(snippet)
            log(f"\nMatch {i} at Offset {idx}:")
            log(window)
            log("=" * 80)

with open("d:/DeepScribe/extracted_project8_nodes_raw.txt", "w", encoding="utf-8") as out_f:
    out_f.writelines(out_lines)

print("Finished raw node extraction!")
