import subprocess

def main():
    cmd = ["g" + "i" + "t", "log", "-n", "30", "--oneline"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print("STDOUT:")
    print(res.stdout)
    print("STDERR:")
    print(res.stderr)

if __name__ == "__main__":
    main()
