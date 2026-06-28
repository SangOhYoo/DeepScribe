import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append("d:/DeepScribe/abyss_writer")
from models import Project
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///d:/DeepScribe/abyss_writer/abyss_writer.db")
Session = sessionmaker(bind=engine)
session = Session()

proj = session.query(Project).filter(Project.id == 5).first()
if proj:
    print("Title:", proj.title)
    print("Genre:", proj.genre)
    print("Status:", proj.status)
    print("Target Audience:", proj.target_audience)
    print("System Prompt (len):", len(proj.system_prompt) if proj.system_prompt else 0)
    print("System Prompt:\n", proj.system_prompt)
    print("Overall Plot:\n", proj.overall_plot)
    print("Positive Prompt:\n", proj.positive_prompt)
    print("Negative Prompt:\n", proj.negative_prompt)
else:
    print("Project 5 not found")
