import json
import os

log_path = r"C:\Users\SangO\.gemini\antigravity\brain\35ec69d3-6ec2-42f8-8f8e-87d9c49e4e18\.system_generated\logs\overview.txt"
output_path = r"d:\DeepScribe\current_log_results.txt"

out_lines = []
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                if data.get('type') == 'PLANNER_RESPONSE' and 'tool_calls' in data:
                    for tc in data['tool_calls']:
                        func_name = tc.get('name')
                        args = tc.get('args', {})
                        target_file = args.get('TargetFile', args.get('AbsolutePath', ''))
                        if 'ui.py' in target_file or 'fix' in target_file:
                            out_lines.append(f"Line {i+1}: tool={func_name}")
                            # check if truncated
                            content = str(args.get('CodeContent', ''))
                            target = str(args.get('TargetContent', ''))
                            repl = str(args.get('ReplacementContent', ''))
                            is_t = '<truncated' in content or '<truncated' in target or '<truncated' in repl
                            out_lines.append(f"  Truncated: {is_t}")
                            out_lines.append(f"  Description: {args.get('Description')}")
                            out_lines.append(f"  Args keys: {list(args.keys())}")
            except Exception as e:
                pass
else:
    out_lines.append(f"Log path not found: {log_path}")

with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines))
print("Results written to current_log_results.txt")
