import difflib

file_active = "d:/DeepScribe/abyss_writer/ui.py"
file_dry = "d:/DeepScribe/dry_run_temp/abyss_writer/ui.py"

with open(file_active, "r", encoding="utf-8") as f:
    active_lines = f.readlines()
    
with open(file_dry, "r", encoding="utf-8") as f:
    dry_lines = f.readlines()

# No print statements here


# Let's see if there are diffs in parts of the file that exist in both.
# We will do a line-by-line diff or check differences.
with open("ui_diff_summary.txt", "w", encoding="utf-8") as out:
    out.write(f"Active UI lines: {len(active_lines)}\n")
    out.write(f"Dry Run UI lines: {len(dry_lines)}\n\n")
    
    # Check if get_project_list is the same
    # We will write the first 100 lines diff
    diff = list(difflib.unified_diff(active_lines[:2000], dry_lines[:2000], fromfile="active", tofile="dry"))
    out.write("=== FIRST 2000 LINES DIFF ===\n")
    out.write("".join(diff[:500]) + "\n")
