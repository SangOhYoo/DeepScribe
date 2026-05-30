import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite 로컬 데이터베이스 파일 위치 정의
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"

# SQLite는 기본적으로 단일 스레드 접근을 강제하므로, 멀티스레드 비동기 요청 처리를 위해 connect_args 설정 적용
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI 엔드포인트에서 DB 세션 의존성 주입(Dependency Injection)을 위한 Helper
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
