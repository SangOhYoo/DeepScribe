import json
import os

log_path = r"C:\Users\SangO\.gemini\antigravity\brain\95221eaf-33b6-4474-a4d6-3084be1a2db2\.system_generated\logs\overview.txt"
with open(log_path, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        try:
            data = json.loads(line)
            if data.get('type') == 'PLANNER_RESPONSE' and 'tool_calls' in data:
                for tc in data['tool_calls']:
                    func_name = tc.get('name')
                    args = tc.get('args', {})
                    target_file = args.get('TargetFile', args.get('AbsolutePath', ''))
                    if 'main.py' in target_file:
                        print(f"Line {i+1}: tool={func_name}")
                        print(f"Target: {repr(args.get('TargetContent'))}")
                        print(f"Replacement: {repr(args.get('ReplacementContent'))}")
                        print("-" * 50)
        except Exception as e:
            pass
