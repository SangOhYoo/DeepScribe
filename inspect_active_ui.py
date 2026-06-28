import re

path = "d:/DeepScribe/abyss_writer/ui.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's find all function definitions
matches = re.finditer(r"def\s+(\w+)\s*\(", content)
funcs = [m.group(1) for m in matches]

target_funcs = [
    "autofill_characters_from_project",
    "parse_scenario_cases",
    "generate_psychological_scenarios_stream",
    "load_selected_case_details",
    "insert_case_to_scenario_node",
    "on_case_stage_change",
    "on_case_node_change",
    "on_case_ver_change",
    "on_case_save_ver",
    "on_case_delete_ver",
    "on_case_commit_ver",
    "update_erotic_char_dropdowns",
    "ai_generate_erotic_settings",
    "on_female_char_select",
    "on_male_char_select"
]

with open("active_ui_check.txt", "w", encoding="utf-8") as out:
    for tf in target_funcs:
        exists = tf in funcs
        out.write(f"Function: {tf} -> {'EXISTS' if exists else 'MISSING'}\n")
