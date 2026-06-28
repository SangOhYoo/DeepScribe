import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    raw_data = f.read()

# Titles we want to extract
titles = [
    "도쿄 상경과 엄격한 질서의 집",
    "도쿄의 낯선 안식처",
    "미망인 스미래와의 정적인 조우",
    "첫사랑 아유꼬라는 도덕적 거울",
    "순결한 기억과 현재의 유혹",
    "순결한 기억과 현재의 갈등",
    "은밀한 호의의 시작",
    "억눌린 본능의 각성",
    "만원 전철의 무언의 약속",
    "이성의 끈을 놓아버린 방과 후",
    "이성의 끈을 놓아버린 외출",
    "신사의 숲, 첫 격정의 폭발",
    "신사의 숲, 첫 번째 폭발",
    "신사 아래, 폭발하는 첫 격정",
    "중독되는 쾌락과 심화되는 갈등",
    "중독되는 쾌락의 굴레",
    "분열되는 자아와 도덕적 자책",
    "분열되는 히로시의 자아",
    "여름밤의 금지된 문",
    "결핍의 고백과 탐욕의 끝",
    "사춘기 후미애의 위험한 동경",
    "사춘기 소녀의 위험한 동경",
    "초겨울의 재회와 상실",
    "잔혹한 상처의 여운",
    "폭우 속의 정사와 운명의 발자국 소리",
    "폭풍 전야의 평온"
]

extracted_nodes = []

# Search method: find the title in the bytes.
# Typically, around the title, there are fields like stage, node_index, content, etc.
# Since SQLite stores fields sequentially:
# stage (text) -> node_index (integer) -> title (text) -> parent_id (integer) -> content (text) -> regen_prompt (text) -> commit_message (text) -> created_at (text/DateTime)
# Let's inspect bytes around each title.
for title in titles:
    title_bytes = title.encode("utf-8")
    offset = 0
    while True:
        offset = raw_data.find(title_bytes, offset)
        if offset == -1:
            break
        
        # Grab a chunk around the offset to analyze
        # Let's say 200 bytes before and 4000 bytes after
        start = max(0, offset - 300)
        end = min(len(raw_data), offset + 4000)
        chunk = raw_data[start:end]
        
        # Decode and try to find structural patterns
        # For example, look for stage names: "기 (起 - 도입)", "승 (承 - 전개)", "전 (轉 - 위기/절정)", "결 (結 - 결말)"
        chunk_str = chunk.decode("utf-8", errors="replace")
        
        # Let's find if there's a timestamp like '2026-06-13' or '2026-06-09' or '2026-06-10'
        timestamps = re.findall(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+", chunk_str)
        
        # Let's look for content
        # Content usually follows the title or is preceding it.
        # Let's write out chunks containing the title to see how they are structured
        extracted_nodes.append({
            "title": title,
            "offset": offset,
            "chunk_snippet": chunk_str[:2000],
            "timestamps": timestamps
        })
        
        offset += len(title_bytes)

with open("d:/DeepScribe/extracted_nodes_raw.json", "w", encoding="utf-8") as out_f:
    json.dump(extracted_nodes, out_f, indent=2, ensure_ascii=False)

print(f"Extracted {len(extracted_nodes)} raw nodes.")
