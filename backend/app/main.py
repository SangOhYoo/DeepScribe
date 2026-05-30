import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import ROOT_INPUT_DIR
from .core.database import engine, Base
from .api.router import api_router

# 1. SQLAlchemy 데이터베이스 모델 스키마 테이블 초기화
# 데이터베이스 파일이 없는 경우, 기동 시점에 스키마를 자동 생성합니다.
Base.metadata.create_all(bind=engine)

# SQLite 동적 마이그레이션: project_name 컬럼 부재 시 자동 ALTER 수행
try:
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(state_history)"))
        columns = [row[1] for row in result.fetchall()]
        if "project_name" not in columns:
            # SQLite에선 트랜잭션 수동 커밋 제어가 권장되므로 직접 실행
            conn.execute(text("ALTER TABLE state_history ADD COLUMN project_name VARCHAR(100) DEFAULT 'default' NOT NULL"))
            print("Successfully migrated SQLite database: added 'project_name' column to 'state_history' table.")
except Exception as e:
    print(f"Database migration warning: {e}")

app = FastAPI(
    title="DeepScribe Full-stack API Server",
    description="일본어 망가 컷을 한국어 성인 소설로 로컬 환경에서 변환해주는 아키텍처 코어 서버",
    version="1.0.0"
)

# 2. 크로스 오리진 리소스 공유(CORS) 미들웨어 등록
# React Vite 개발 서버 등과의 통신을 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 로컬 환경이므로 와일드카드 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. API 라우터 마운트
app.include_router(api_router, prefix="/api")

# 4. 프론트엔드 이미지 랜더링용 정적 미디어(망가 컷) 폴더 서빙
# /media/input/파일명.jpg 구조로 프론트엔드에서 직접 파일에 접근할 수 있게 마운트합니다.
if os.path.exists(ROOT_INPUT_DIR):
    app.mount("/media/input", StaticFiles(directory=ROOT_INPUT_DIR), name="manga_inputs")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "DeepScribe FastAPI Backend Engine"
    }
