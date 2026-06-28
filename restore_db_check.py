import subprocess

print("Checking if abyss_writer.db is tracked in git...")
res = subprocess.run(["git", "status", "--porcelain", "abyss_writer/abyss_writer.db"], capture_output=True, text=True)
print("Git status of db:", res.stdout.strip())

res_diff = subprocess.run(["git", "diff", "abyss_writer/abyss_writer.db"], capture_output=True)
print("Has diff:", len(res_diff.stdout) > 0)

# Let's restore the db file from git
res_checkout = subprocess.run(["git", "checkout", "HEAD", "--", "abyss_writer/abyss_writer.db"], capture_output=True, text=True)
print("Checkout stdout:", res_checkout.stdout.strip())
print("Checkout stderr:", res_checkout.stderr.strip())
