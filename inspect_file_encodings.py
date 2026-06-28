# Let's inspect raw bytes of recovered_strings.txt around occurrences of "스미래" or other names
with open("d:/DeepScribe/recovered_strings.txt", "rb") as f:
    data = f.read()

print(f"Total bytes in recovered_strings.txt: {len(data)}")

# Let's search for the byte patterns
# "스미래" in UTF-8: \xec\x8a\xa4\xeb\xaf\xb8\xeb\x9e\x98
# "스미래" in CP949: \xc1\xf6\xb9\xcc\xb7\xa1 (wait, let's check: 스=\xbd\xba, 미=\xb9\xcc, 래=\xb7\xa1)
# "히로시" in UTF-8: \xed\x9e\x88\xeb\xa1\x9c\xec\x8b\x9c
# "히로시" in CP949: 히=\xc8\xf0, 로=\xb1\xdb (wait, 로=\xb7\xce), 시=\xbd\xc3
utf8_smire = "스미래".encode("utf-8")
cp949_smire = "스미래".encode("cp949", errors="ignore")
utf8_hiroshi = "히로시".encode("utf-8")
cp949_hiroshi = "히로시".encode("cp949", errors="ignore")

print("UTF-8 스미래:", utf8_smire)
print("CP949 스미래:", cp949_smire)
print("UTF-8 히로시:", utf8_hiroshi)
print("CP949 히로시:", cp949_hiroshi)

# Find positions
pos_utf8_smire = [m for m in range(len(data)) if data[m:m+len(utf8_smire)] == utf8_smire]
pos_cp949_smire = [m for m in range(len(data)) if data[m:m+len(cp949_smire)] == cp949_smire]
print(f"Found UTF-8 스미래 at {len(pos_utf8_smire)} locations: {pos_utf8_smire[:5]}")
print(f"Found CP949 스미래 at {len(pos_cp949_smire)} locations: {pos_cp949_smire[:5]}")

# Let's print a sample snippet from a found location
if pos_utf8_smire:
    idx = pos_utf8_smire[0]
    sample = data[max(0, idx-50):min(len(data), idx+150)]
    print("\nUTF-8 Sample bytes:", sample)
    print("Decoded UTF-8 (ignore errors):", sample.decode("utf-8", errors="ignore"))
    print("Decoded CP949 (ignore errors):", sample.decode("cp949", errors="ignore"))

if pos_cp949_smire:
    idx = pos_cp949_smire[0]
    sample = data[max(0, idx-50):min(len(data), idx+150)]
    print("\nCP949 Sample bytes:", sample)
    print("Decoded UTF-8 (ignore errors):", sample.decode("utf-8", errors="ignore"))
    print("Decoded CP949 (ignore errors):", sample.decode("cp949", errors="ignore"))
