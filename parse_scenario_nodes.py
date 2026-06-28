import json
import re
import sys

def run_extraction():
    with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
        data = f.read()

    # Search for any JSON-like blocks containing scenario node fields
    # e.g., "stage": "기 (起 - 도입)", or "stage": "승 (承 - 전개)"
    # We will search for '"stage":' in the binary data.
    idx = 0
    parsed_nodes = []
    seen_nodes = set()

    while True:
        idx = data.find(b'"stage":', idx)
        if idx == -1:
            break
        # Find start brace
        start_brace = data.rfind(b'{', 0, idx)
        if start_brace != -1:
            # Match braces
            brace_count = 0
            end_brace = -1
            for i in range(start_brace, len(data)):
                if data[i] == ord('{'):
                    brace_count += 1
                elif data[i] == ord('}'):
                    brace_count -= 1
                    if brace_count == 0:
                        end_brace = i
                        break
            if end_brace != -1:
                block = data[start_brace:end_brace+1]
                try:
                    node_dict = json.loads(block.decode("utf-8"))
                    if isinstance(node_dict, dict) and "stage" in node_dict and "content" in node_dict:
                        # Check if it's related to Project 8
                        content = node_dict.get("content", "")
                        title = node_dict.get("title", "")
                        if any(kw in content or kw in title for kw in ["스미래", "히로시", "후미애", "타카시", "하숙집", "미망인"]):
                            # Create a unique key for the node
                            key = (node_dict.get("stage"), node_dict.get("node_index"), len(content))
                            if key not in seen_nodes:
                                seen_nodes.add(key)
                                parsed_nodes.append(node_dict)
                except Exception:
                    pass
        idx += 1

    # Also search for raw text scenario nodes if they are not in JSON
    # In search_extracted_clean.py output, we saw "도쿄 상경과 엄격한 질서의 집" and "자동 생성 시나리오"
    # Let's extract any blocks matching the stages from extracted_clean_project8.txt
    with open("d:/DeepScribe/extracted_clean_project8.txt", "r", encoding="utf-8") as f:
        clean_text = f.read()

    # Find stage headers and content
    # Let's save the extracted JSON nodes
    with open("d:/DeepScribe/recovered_scenario_nodes.json", "w", encoding="utf-8") as out_f:
        json.dump(parsed_nodes, out_f, indent=2, ensure_ascii=False)

    return f"Extracted {len(parsed_nodes)} scenario nodes."

if __name__ == "__main__":
    run_extraction()
