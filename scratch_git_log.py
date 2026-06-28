import subprocess

def run():
    res = subprocess.run(["git", "log", "-n", "20", "--oneline", "--", "novel_translator/app.py"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    print(res.stdout)
    with open("git_log_app.txt", "w", encoding="utf-8") as f:
        f.write(res.stdout)

if __name__ == "__main__":
    run()
