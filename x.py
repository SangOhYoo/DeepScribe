import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    raw_data = f.read()

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

for title in titles:
    title_bytes = title.encode("utf-8")
    offset = 0
    while True:
        offset = raw_data.find(title_bytes, offset)
        if offset == -1:
            break
        
        start = max(0, offset - 300)
        end = min(len(raw_data), offset + 4000)
        chunk = raw_data[start:end]
        
        chunk_str = chunk.decode("utf-8", errors="replace")
        timestamps = re.findall(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+", chunk_str)
        
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
