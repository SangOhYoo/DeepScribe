from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class StateUpdateSchema(BaseModel):
    """상태 업데이트 및 새로운 리비전 생성을 위한 요청 스키마"""
    project_name: str = "default"
    data: Dict[str, Any]
    cut_number: Optional[int] = None
    author: str = "user"
    change_description: Optional[str] = None

    class Config:
        from_attributes = True

class StateHistoryResponseSchema(BaseModel):
    """버전 히스토리 조회를 위한 응답 스키마"""
    id: int
    project_name: str
    file_type: str
    cut_number: Optional[int] = None
    revision: int
    data: Dict[str, Any]
    author: str
    change_description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
