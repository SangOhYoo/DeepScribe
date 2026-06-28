import marshal
import dis

pyc_path = r"d:\DeepScribe\abyss_writer\__pycache__\ui.cpython-313.pyc"

with open(pyc_path, 'rb') as f:
    # Python 3.7+ pyc header is 16 bytes
    header = f.read(16)
    code_obj = marshal.load(f)

print("Successfully loaded code object!")

# Scan co_consts for string constants
strings = []
def scan_code(co):
    for const in co.co_consts:
        if isinstance(const, str) and len(const) > 100:
            strings.append(const)
        elif hasattr(const, 'co_consts'):
            scan_code(const)

scan_code(code_obj)
print(f"Found {len(strings)} long string constants.")

# Write all long strings to a restore file for manual picking
with open("recovered_strings.txt", "w", encoding="utf-8") as out:
    for i, s in enumerate(strings):
        out.write(f"\n\n--- STRING CONSTANT {i} (Length: {len(s)}) ---\n")
        out.write(s)

print("Dumped long strings to recovered_strings.txt")
