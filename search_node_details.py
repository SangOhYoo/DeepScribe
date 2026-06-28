import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

titles = [
    "도쿄 상경과 엄격한 질서의 집",
    "결핍의 고백과 탐욕의 끝",
    "분열되는 자아와 도덕적 자책",
    "신사 아래, 폭발하는 첫 격정",
    "금단의 갈증, 무너지는 경계"
]

for t in titles:
    pattern = t.encode("utf-8")
    idx = 0
    match_count = 0
    while True:
        idx = data.find(pattern, idx)
        if idx == -1:
            break
        match_count += 1
        print(f"\n=================== Match for '{t}' #{match_count} at offset {idx} ===================")
        # Grab a window around the match
        start = max(0, idx - 200)
        end = min(len(data), idx + 2000)
        snippet = data[start:end].decode("utf-8", errors="replace")
        print(snippet[:1800])
        idx += len(pattern)
