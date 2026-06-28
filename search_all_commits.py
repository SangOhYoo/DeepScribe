import subprocess

res = subprocess.run(["git", "log", "--all", "-S", "인간의 은밀한 욕망", "--oneline"], capture_output=True)
output = res.stdout.decode('utf-8', errors='ignore')

with open("search_results.txt", "w", encoding="utf-8") as f:
    f.write("=== SEARCH FOR '인간의 은밀한 욕망' ===\n")
    f.write(output + "\n")
    
    res2 = subprocess.run(["git", "log", "--all", "-S", "심층 소설", "--oneline"], capture_output=True)
    output2 = res2.stdout.decode('utf-8', errors='ignore')
    f.write("=== SEARCH FOR '심층 소설' ===\n")
    f.write(output2 + "\n")

    res3 = subprocess.run(["git", "log", "--all", "--oneline", "-n", "100"], capture_output=True)
    output3 = res3.stdout.decode('utf-8', errors='ignore')
    f.write("=== RECENT COMMITS ===\n")
    f.write(output3 + "\n")
