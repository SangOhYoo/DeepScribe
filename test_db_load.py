import sys
sys.path.append("d:/DeepScribe/abyss_writer")
sys.path.append("d:/DeepScribe")

# Initialize DB session
from models import init_db, Project, Character
db_session = init_db()

# Test fetch projects
projects = db_session.query(Project).all()
print("Found projects:", [p.title for p in projects])

# Test character query
chars = db_session.query(Character).all()
print(f"Total characters in database: {len(chars)}")

from ui import load_project_details, on_character_select_change

project_str = f"[{projects[0].id}] {projects[0].title}" if projects else None
if project_str:
    print(f"\n--- Testing load_project_details on: {project_str} ---")
    try:
        res = load_project_details(project_str)
        print("Success! Return length:", len(res))
        print("Character details:")
        print(" - Name:", res[0])
        print(" - Role:", res[1])
        print(" - Personality (truncated):", res[2][:50] if res[2] else "")
        print(" - Background (truncated):", res[3][:50] if res[3] else "")
        print(" - Physical (truncated):", res[6][:50] if res[6] else "")
    except Exception as e:
        import traceback
        print("CRITICAL ERROR in load_project_details:")
        traceback.print_exc()
else:
    print("No projects to test.")
