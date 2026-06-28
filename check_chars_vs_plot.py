import sys, json
sys.path.append('d:/DeepScribe/abyss_writer')
from models import init_db, Project, Character, ScenarioNode

session = init_db()

proj = session.query(Project).filter(Project.id == 8).first()
if not proj:
    print("Project 8 not found!")
    sys.exit(1)

result = []
result.append("=== PROJECT 8 INFO ===")
result.append(f"Title: {proj.title}")
result.append(f"Genre: {proj.genre}")
result.append(f"Overall Plot:\n{proj.overall_plot}\n")
result.append(f"System Prompt:\n{proj.system_prompt}\n")

result.append("=== CHARACTERS ===")
chars = session.query(Character).filter(Character.project_id == 8).all()
for c in chars:
    result.append(f"\n--- [{c.id}] {c.name} ({c.relations}) ---")
    result.append(f"  personality: {c.personality}")
    result.append(f"  background: {c.background}")
    result.append(f"  character_relations: {c.character_relations}")
    result.append(f"  speech_style: {c.speech_style}")
    result.append(f"  physical_signature: {c.physical_signature}")
    result.append(f"  psychological_trigger: {c.psychological_trigger}")
    result.append(f"  behavioral_quirks: {c.behavioral_quirks}")
    result.append(f"  secret_taboo: {c.secret_taboo}")
    result.append(f"  signature_quotes: {c.signature_quotes}")

result.append("\n=== SCENARIO NODES ===")
nodes = session.query(ScenarioNode).filter(ScenarioNode.project_id == 8).order_by(ScenarioNode.node_index).all()
for n in nodes:
    result.append(f"[{n.node_index}] {n.stage}: {n.title}")
    result.append(f"  Content: {n.content[:200]}...")

with open("d:/DeepScribe/char_vs_plot_check.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(result))
print("Done! Check char_vs_plot_check.txt")
