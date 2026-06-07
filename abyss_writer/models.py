import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    genre = Column(String(100))
    status = Column(String(50), default="Draft")
    target_audience = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    system_prompt = Column(Text)
    overall_plot = Column(Text)
    positive_prompt = Column(Text)
    negative_prompt = Column(Text)

    characters = relationship("Character", back_populates="project", cascade="all, delete-orphan")
    plots = relationship("Plot", back_populates="project", cascade="all, delete-orphan")
    scenario_nodes = relationship("ScenarioNode", back_populates="project", cascade="all, delete-orphan")
    prompt_versions = relationship("PromptVersion", back_populates="project", cascade="all, delete-orphan")

class Character(Base):
    __tablename__ = 'characters'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    name = Column(String(100), nullable=False)
    personality = Column(Text)
    background = Column(Text)
    speech_style = Column(Text)
    key_quotes = Column(Text)
    relations = Column(Text)
    character_relations = Column(Text)

    project = relationship("Project", back_populates="characters")
    versions = relationship("CharacterVersion", back_populates="character", cascade="all, delete-orphan")

class CharacterVersion(Base):
    __tablename__ = 'character_versions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    character_id = Column(Integer, ForeignKey('characters.id', ondelete="CASCADE"))
    version_name = Column(String(100), nullable=False)
    name = Column(String(100), nullable=False)
    personality = Column(Text)
    background = Column(Text)
    speech_style = Column(Text)
    key_quotes = Column(Text)
    relations = Column(Text)
    character_relations = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    character = relationship("Character", back_populates="versions")

class Plot(Base):
    __tablename__ = 'plots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    title = Column(String(200))
    description = Column(Text)
    
    project = relationship("Project", back_populates="plots")

class ScenarioNode(Base):
    """
    Git-like Version Control for Scenarios
    """
    __tablename__ = 'scenario_nodes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    stage = Column(String(50)) # Introduction, Development, Turn, Conclusion (기, 승, 전, 결)
    node_index = Column(Integer, nullable=True)
    title = Column(String(200), nullable=True)
    parent_id = Column(Integer, ForeignKey('scenario_nodes.id'), nullable=True) # For tree structure
    content = Column(Text, nullable=False)
    regen_prompt = Column(Text, nullable=True)
    commit_message = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="scenario_nodes")
    children = relationship("ScenarioNode", backref="parent", remote_side=[id])
    history_logs = relationship("HistoryLog", back_populates="scenario_node", cascade="all, delete-orphan")

class PromptTemplate(Base):
    __tablename__ = 'prompt_templates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100)) # Situation, Character, Emotion
    name = Column(String(100))
    content_template = Column(Text) # Uses {{variables}}

class HistoryLog(Base):
    """
    Tracks granular changes for all edits (Requirement 10).
    Allows before/after diffing.
    """
    __tablename__ = 'history_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_node_id = Column(Integer, ForeignKey('scenario_nodes.id'))
    action_type = Column(String(50)) # e.g., 'CREATE', 'EDIT', 'FILTER_APPLIED'
    before_content = Column(Text, nullable=True)
    after_content = Column(Text, nullable=False)
    tracker_result = Column(Text, nullable=True)
    fact_result = Column(Text, nullable=True)
    user_prompt = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    scenario_node = relationship("ScenarioNode", back_populates="history_logs")


class PromptVersion(Base):
    __tablename__ = 'prompt_versions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    version_name = Column(String(100), nullable=False)
    system_prompt = Column(Text)
    overall_plot = Column(Text)
    positive_prompt = Column(Text)
    negative_prompt = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="prompt_versions")


# Database Initialization
def init_db(db_path="sqlite:///d:/DeepScribe/abyss_writer/abyss_writer.db"):
    os.makedirs("d:/DeepScribe/abyss_writer", exist_ok=True)
    from sqlalchemy.pool import NullPool
    engine = create_engine(db_path, connect_args={"check_same_thread": False, "timeout": 30.0}, poolclass=NullPool)
    
    import sqlalchemy as sa
    # Enable WAL mode for concurrent read/write support
    with engine.begin() as conn:
        conn.execute(sa.text("PRAGMA journal_mode=WAL;"))
        
    inspector = sa.inspect(engine)
    if "projects" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("projects")]
        with engine.begin() as conn:
            if "system_prompt" not in columns:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN system_prompt TEXT"))
            if "overall_plot" not in columns:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN overall_plot TEXT"))
            if "positive_prompt" not in columns:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN positive_prompt TEXT"))
            if "negative_prompt" not in columns:
                conn.execute(sa.text("ALTER TABLE projects ADD COLUMN negative_prompt TEXT"))
                
    if "scenario_nodes" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("scenario_nodes")]
        with engine.begin() as conn:
            if "node_index" not in columns:
                conn.execute(sa.text("ALTER TABLE scenario_nodes ADD COLUMN node_index INTEGER"))
            if "title" not in columns:
                conn.execute(sa.text("ALTER TABLE scenario_nodes ADD COLUMN title VARCHAR(200)"))
            if "regen_prompt" not in columns:
                conn.execute(sa.text("ALTER TABLE scenario_nodes ADD COLUMN regen_prompt TEXT"))

    if "history_logs" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("history_logs")]
        with engine.begin() as conn:
            if "tracker_result" not in columns:
                conn.execute(sa.text("ALTER TABLE history_logs ADD COLUMN tracker_result TEXT"))
            if "fact_result" not in columns:
                conn.execute(sa.text("ALTER TABLE history_logs ADD COLUMN fact_result TEXT"))
            if "user_prompt" not in columns:
                conn.execute(sa.text("ALTER TABLE history_logs ADD COLUMN user_prompt TEXT"))
                
    if "characters" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("characters")]
        with engine.begin() as conn:
            if "character_relations" not in columns:
                conn.execute(sa.text("ALTER TABLE characters ADD COLUMN character_relations TEXT"))

    Base.metadata.create_all(engine)
    from sqlalchemy.orm import scoped_session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return scoped_session(SessionLocal)
