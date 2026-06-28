import sys
sys.path.append('d:/DeepScribe/abyss_writer')
from models import init_db, Project, Character, ScenarioNode

session = init_db()
projects = session.query(Project).all()
print("=== PROJECTS ===")
for p in projects:
    print(f"[{p.id}] {p.title} ({p.genre}) - prompt: {bool(p.system_prompt)}")

print("=== CHARACTERS ===")
chars = session.query(Character).all()
for c in chars:
    print(f"[{c.id}] Project {c.project_id}: {c.name} ({c.relations})")

print("=== SCENARIO NODES ===")
nodes = session.query(ScenarioNode).all()
print(f"Total scenario nodes in DB: {len(nodes)}")
from collections import Counter
print("Nodes per project:", Counter(n.project_id for n in nodes))
