import json
import os

log_path = r"C:\Users\SangO\.gemini\antigravity\brain\5b006b0f-3132-4a35-ba79-8ab5d444ff76\.system_generated\logs\overview.txt"
with open(log_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i == 280:
            data = json.loads(line)
            tc = data['tool_calls'][0]
            val = tc['args']['TargetContent']
            print("Starts with quote:", val.startswith('"'))
            print("Ends with quote:", val.endswith('"'))
            print("Length of val:", len(val))
            print("Last 20 chars of val:", repr(val[-20:]))
