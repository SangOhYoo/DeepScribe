from datetime import datetime
from sqlalchemy import Column, Integer, String, JSON, DateTime
from ..core.database import Base

class StateHistory(Base):
    """
    망가 소설 변환 과정의 4가지 주요 상태 JSON 파일의 버전(Revision) 히스토리를 저장합니다.
    - overall_plot: 전체 줄거리
    - image_plot: 컷별 이미지 분석 데이터
    - theme_background: 세계관 및 배경 설정
    - character_profiles: 캐릭터 프로필
    """
    __tablename__ = "state_history"

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(100), default="default", index=True, nullable=False) # 다중 프로젝트 격리 필드
    file_type = Column(String(50), nullable=False, index=True)  # overall_plot, image_plot 등
    cut_number = Column(Integer, nullable=True, index=True)      # 컷별 세부 정보일 경우 컷 번호 기록
    revision = Column(Integer, nullable=False)                  # 동일 문서 유형 내의 순차 리비전 번호
    data = Column(JSON, nullable=False)                         # JSON 데이터 본문 스냅샷
    author = Column(String(50), default="user")                 # 변경 주체 ('user' 또는 'ai')
    change_description = Column(String(255), nullable=True)     # 변경 사항에 대한 간략한 요약 설명
    created_at = Column(DateTime, default=datetime.utcnow)       # 리비전 생성 시각
