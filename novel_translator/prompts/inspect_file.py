import sys
sys.stdout.reconfigure(encoding='utf-8')
with open(r"d:\DeepScribe\novel_translator\prompts\templates.py", "rb") as f:
    data = f.read()
print("File length:", len(data))
print("Null bytes count:", data.count(b'\x00'))
print("First 500 bytes:", repr(data[:500]))
