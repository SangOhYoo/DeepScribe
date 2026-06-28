import subprocess

res_branches = subprocess.run(["git", "branch", "-a"], capture_output=True)
print("BRANCHES:")
print(res_branches.stdout.decode('utf-8', errors='ignore'))

res_tags = subprocess.run(["git", "tag"], capture_output=True)
print("TAGS:")
print(res_tags.stdout.decode('utf-8', errors='ignore'))

res_reflog = subprocess.run(["git", "reflog", "-n", "20"], capture_output=True)
print("REFLOG:")
print(res_reflog.stdout.decode('utf-8', errors='ignore'))
