import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append("d:/DeepScribe/abyss_writer")
from models import Project, Character, ScenarioNode, HistoryLog, PromptVersion, EroticScenarioVersion
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///d:/DeepScribe/abyss_writer/abyss_writer.db")
Session = sessionmaker(bind=engine)
session = Session()

print("--- PROJECTS ---")
for p in session.query(Project).all():
    print(f"ID: {p.id}, Title: {p.title}, Genre: {p.genre}")

print("\n--- CHARACTERS ---")
for c in session.query(Character).all():
    print(f"ID: {c.id}, Project ID: {c.project_id}, Name: {c.name}")

print("\n--- SCENARIO NODES ---")
for s in session.query(ScenarioNode).all():
    print(f"ID: {s.id}, Project ID: {s.project_id}, Stage: {s.stage}, Title: {s.title}")
