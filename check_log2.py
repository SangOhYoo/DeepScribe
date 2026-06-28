log_path = r"C:\Users\SangO\.gemini\antigravity\brain\95221eaf-33b6-4474-a4d6-3084be1a2db2\.system_generated\logs\overview.txt"
with open(log_path, "r", encoding="utf-8") as f:
    content = f.read()
print("Truncated count in Log 2:", content.count("<truncated"))
