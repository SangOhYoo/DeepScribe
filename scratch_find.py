import os
import glob
import sys

sys.stdout.reconfigure(encoding='utf-8')

search_dir = "d:/DeepScribe/novel_translator/outputs"
output_file = "d:/DeepScribe/scratch_check_result.txt"

results = []
for file_path in glob.glob(os.path.join(search_dir, "*.txt")):
    try:
        # Try different encodings
        content = None
        for encoding in ["utf-8", "cp949", "shift_jis", "utf-16"]:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.readlines()
                break
            except Exception:
                continue
        
        if content:
            for idx, line in enumerate(content):
                if "仁美" in line or "마유미" in line or "히토미" in line:
                    results.append(f"{os.path.basename(file_path)}:{idx+1}: {line.strip()}")
    except Exception as e:
        results.append(f"Error reading {file_path}: {e}")

with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print(f"Done. Found {len(results)} matches.")
