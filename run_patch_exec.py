import shutil

# Copy dry_run_temp/abyss_writer/ui.py to abyss_writer/ui.py
src = "d:/DeepScribe/dry_run_temp/abyss_writer/ui.py"
dst = "d:/DeepScribe/abyss_writer/ui.py"
shutil.copyfile(src, dst)

# Read the patch script
patch_script_path = "C:/Users/SangO/.gemini/antigravity/brain/5b006b0f-3132-4a35-ba79-8ab5d444ff76/scratch/patch_ui.py"
with open(patch_script_path, "r", encoding="utf-8") as f:
    patch_code = f.read()

# Execute the patch
exec(patch_code, globals())

with open("patch_status.txt", "w", encoding="utf-8") as f:
    f.write("Execution complete\n")
