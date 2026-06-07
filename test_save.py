import sys
sys.path.append(r'D:\DeepScribe\abyss_writer')
from models import init_db, Project
from ui import save_project_only, parse_project_id

try:
    print("Testing saving project...")
    db_session = init_db()
    # Find a project
    proj = db_session.query(Project).first()
    if proj:
        project_str = f"[{proj.id}] {proj.title}"
        print(f"Target project: {project_str}")
        save_project_only(
            project_str,
            "dummy_name", "dummy_role", "dummy_personality", "dummy_relations",
            "dummy_other_name", "dummy_other_profile",
            "test_system_prompt", "test_overall_plot", "test_positive_prompt", "test_negative_prompt"
        )
        print("SUCCESS")
    else:
        print("No project found.")
except Exception as e:
    import traceback
    traceback.print_exc()
