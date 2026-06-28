import sys
sys.path.append('d:/DeepScribe/abyss_writer')
from models import init_db, ScenarioNode

session = init_db()
nodes = session.query(ScenarioNode).filter(ScenarioNode.project_id == 8).all()
with open("d:/DeepScribe/output.txt", "w", encoding="utf-8") as f:
    f.write(f"Total nodes for project 8: {len(nodes)}\n")
    if len(nodes) > 0:
        for n in nodes:
            f.write(f"Node: {n.stage} - {n.node_index} - {n.title}\n")
