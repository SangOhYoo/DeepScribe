db_path = "d:/DeepScribe/abyss_writer/abyss_writer.db"
with open(db_path, "rb") as f:
    data = f.read()

target = "스미래".encode("utf-8")
import re
indices = [m.start() for m in re.finditer(re.escape(target), data)]
print(f"Found '스미래' {len(indices)} times.")

with open("d:/DeepScribe/recovered_strings.txt", "w", encoding="utf-8") as out:
    for idx in indices:
        start = max(0, idx - 400)
        end = min(len(data), idx + 2000)
        chunk = data[start:end]
        decoded = chunk.decode("utf-8", errors="ignore")
        out.write(f"\n================ OFFSET {idx} ================\n")
        out.write(decoded)
        out.write("\n")

print("Written all recovered content to recovered_strings.txt")
