import subprocess

def run():
    # Show diff of f004144
    res = subprocess.run(["git", "show", "f004144"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
    with open("git_diff_f004144.txt", "w", encoding="utf-8") as f:
        f.write(res.stdout)
    print("Done")

if __name__ == "__main__":
    run()
