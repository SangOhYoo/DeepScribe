log_path = r"C:\Users\SangO\.gemini\antigravity\brain\5b006b0f-3132-4a35-ba79-8ab5d444ff76\.system_generated\logs\overview.txt"
with open(log_path, "r", encoding="utf-8") as f:
    content = f.read()
print("Truncated count:", content.count("<truncated"))
