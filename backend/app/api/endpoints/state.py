from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ...core.database import get_db
from ...models.db_models import StateHistory
from ...schemas.state_schemas import StateUpdateSchema, StateHistoryResponseSchema

router = APIRouter(prefix="/state", tags=["JSON 상태 & 버전 관리"])

@router.get("/novel/full", response_model=dict)
def get_full_novel(project_name: str = "default", db: Session = Depends(get_db)):
    """
    지정된 프로젝트(project_name)의 모든 이미지 컷들에서 최신 리비전의 novel_paragraph를 수집하여 
    순서대로 정렬된 전체 소설 원고를 생성합니다.
    """
    from sqlalchemy import func
    
    # 각 cut_number별 최신 revision 조회 서브쿼리
    subquery = db.query(
        StateHistory.cut_number,
        func.max(StateHistory.revision).label("max_rev")
    ).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == "image_plot"
    ).group_by(StateHistory.cut_number).subquery()
    
    # 서브쿼리와 조인하여 최신 레코드만 가져오기
    latest_records = db.query(StateHistory).join(
        subquery,
        (StateHistory.cut_number == subquery.c.cut_number) & 
        (StateHistory.revision == subquery.c.max_rev)
    ).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == "image_plot"
    ).order_by(StateHistory.cut_number.asc()).all()
    
    novel_cuts = []
    full_text_list = []
    
    for record in latest_records:
        novel_paragraph = record.data.get("novel_paragraph", "")
        if novel_paragraph:
            novel_cuts.append({
                "cut_number": record.cut_number,
                "novel_paragraph": novel_paragraph
            })
            full_text_list.append(f"[Cut #{record.cut_number}]\n{novel_paragraph}")
            
    return {
        "full_novel": "\n\n".join(full_text_list),
        "cuts": novel_cuts
    }


@router.get("/projects", response_model=List[str])
def list_projects(db: Session = Depends(get_db)):
    """현재 데이터베이스에 존재하는 고유한 프로젝트명 목록을 반환합니다."""
    results = db.query(StateHistory.project_name).distinct().all()
    project_list = [row[0] for row in results if row[0]]
    if "default" not in project_list:
        project_list.insert(0, "default")
    return project_list


@router.post("/project/new", response_model=dict)
def create_new_project(payload: dict, db: Session = Depends(get_db)):
    """
    새로운 소설 프로젝트(작업)를 활성화하며, 디렉토리 생성 및 
    UI 초기화를 방지하기 위해 빈 초기 리비전 상태(overall_plot, character_profiles, theme_background)를 빌드합니다.
    """
    new_project_name = payload.get("new_project_name", "").strip()
    if not new_project_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="새 작업명 이름이 비어 있습니다."
        )

    # 1. 디렉토리 물리적 격리 생성 및 안전한 이름 추출
    import os
    from ...core.config import get_project_dirs
    p_input, p_output = get_project_dirs(new_project_name)
    safe_project_name = os.path.basename(p_input)

    # 2. 이미 존재하는 프로젝트인지 검증
    exists = db.query(StateHistory).filter(StateHistory.project_name == safe_project_name).first()
    if exists:
        return {"status": "success", "message": "이미 존재하는 작업명입니다. 해당 세션으로 스위칭합니다.", "project_name": safe_project_name}

    # 3. 빈 에디터 기본 리비전 템플릿 적재
    editor_types = {
        "overall_plot": {"overall_plot": ""},
        "theme_background": {"theme_background": ""},
        "character_profiles": {"character_profiles": ""},
        "master_novel": {"master_novel": "아직 변환 완료되어 생성된 소설 단락이 없습니다. 에셋 매니저에서 컷 변환을 먼저 수행해 주십시오."}
    }

    for f_type, base_data in editor_types.items():
        new_rev = StateHistory(
            project_name=safe_project_name,
            file_type=f_type,
            cut_number=None,
            revision=1,
            data=base_data,
            author="ai",
            change_description="새 프로젝트 시나리오 초기화"
        )
        db.add(new_rev)
    
    db.commit()
    return {"status": "success", "message": "새로운 작업 세션이 초기화되었습니다.", "project_name": safe_project_name}


@router.delete("/project/{project_name}", response_model=dict)
def delete_project(project_name: str, db: Session = Depends(get_db)):
    """
    지정된 프로젝트를 데이터베이스 및 디렉토리에서 영구 삭제합니다.
    """
    import os
    import shutil
    import logging
    from ...core.config import get_project_dirs
    
    logger = logging.getLogger("uvicorn.error")
    
    # 1. 안전한 프로젝트명 추출
    p_input, p_output = get_project_dirs(project_name)
    safe_project_name = os.path.basename(p_input)
    
    # 2. 데이터베이스에서 레코드 삭제
    db.query(StateHistory).filter(StateHistory.project_name == safe_project_name).delete(synchronize_session=False)
    db.commit()
    
    # 3. 물리적 폴더 및 파일 삭제
    try:
        if os.path.exists(p_input):
            shutil.rmtree(p_input)
        if os.path.exists(p_output):
            shutil.rmtree(p_output)
            
        # 디렉토리를 빈 상태로 다시 생성 (구조 유지)
        os.makedirs(p_input, exist_ok=True)
        os.makedirs(p_output, exist_ok=True)
    except Exception as e:
        logger.error(f"프로젝트 폴더 삭제 중 오류 발생: {e}")
        
    # 4. 만약 삭제한 프로젝트가 'default'인 경우 기본 템플릿 적재
    if safe_project_name == "default":
        editor_types = {
            "overall_plot": {"overall_plot": ""},
            "theme_background": {"theme_background": ""},
            "character_profiles": {"character_profiles": ""},
            "master_novel": {"master_novel": "아직 변환 완료되어 생성된 소설 단락이 없습니다. 에셋 매니저에서 컷 변환을 먼저 수행해 주십시오."}
        }

        for f_type, base_data in editor_types.items():
            new_rev = StateHistory(
                project_name="default",
                file_type=f_type,
                cut_number=None,
                revision=1,
                data=base_data,
                author="ai",
                change_description="default 프로젝트 시나리오 초기화"
            )
            db.add(new_rev)
        db.commit()
        
    return {"status": "success", "message": f"프로젝트 [{safe_project_name}] 가 완전히 삭제되었습니다."}


@router.get("/{file_type}", response_model=dict)
def get_latest_state(
    file_type: str, 
    project_name: str = "default",
    cut_number: Optional[int] = None, 
    db: Session = Depends(get_db)
):
    """지정된 프로젝트 및 파일 타입의 가장 최신 활성화된 JSON 데이터를 반환합니다."""
    query = db.query(StateHistory).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == file_type
    )
    if cut_number is not None:
        query = query.filter(StateHistory.cut_number == cut_number)
    
    latest = query.order_by(StateHistory.revision.desc()).first()
    if not latest:
        return {}
    return latest.data


@router.post("/{file_type}", response_model=StateHistoryResponseSchema)
def create_state_revision(
    file_type: str, 
    payload: StateUpdateSchema, 
    db: Session = Depends(get_db)
):
    """
    텍스트 에디터에서의 수정이나 AI 변환 실행 시 호출되어 새로운 리비전 버전 데이터를 추가합니다.
    """
    query = db.query(StateHistory).filter(
        StateHistory.project_name == payload.project_name,
        StateHistory.file_type == file_type
    )
    if payload.cut_number is not None:
        query = query.filter(StateHistory.cut_number == payload.cut_number)
        
    latest = query.order_by(StateHistory.revision.desc()).first()
    next_revision = (latest.revision + 1) if latest else 1

    new_revision = StateHistory(
        project_name=payload.project_name,
        file_type=file_type,
        cut_number=payload.cut_number,
        revision=next_revision,
        data=payload.data,
        author=payload.author,
        change_description=payload.change_description,
    )
    db.add(new_revision)
    db.commit()
    db.refresh(new_revision)
    return new_revision


@router.get("/{file_type}/history", response_model=List[StateHistoryResponseSchema])
def get_revision_history(
    file_type: str, 
    project_name: str = "default",
    cut_number: Optional[int] = None, 
    db: Session = Depends(get_db)
):
    """지정 문서에 대해 생성된 변경 리비전 목록 전체를 최신순으로 조회합니다."""
    query = db.query(StateHistory).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == file_type
    )
    if cut_number is not None:
        query = query.filter(StateHistory.cut_number == cut_number)
        
    return query.order_by(StateHistory.revision.desc()).all()


@router.post("/{file_type}/rollback/{revision}", response_model=dict)
def rollback_state(
    file_type: str, 
    revision: int, 
    project_name: str = "default",
    cut_number: Optional[int] = None, 
    db: Session = Depends(get_db)
):
    """특정 과거 리비전 데이터를 기반으로 새로운 롤백 복사본 리비전을 생성하고 데이터를 반환합니다."""
    target_record = db.query(StateHistory).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == file_type,
        StateHistory.revision == revision
    )
    if cut_number is not None:
        target_record = target_record.filter(StateHistory.cut_number == cut_number)
        
    target = target_record.first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"해당 문서의 {revision} 리비전을 찾을 수 없습니다."
        )
        
    # 새로운 최신 리비전을 작성하여 롤백 상태 보존
    query = db.query(StateHistory).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == file_type
    )
    if cut_number is not None:
        query = query.filter(StateHistory.cut_number == cut_number)
    
    latest = query.order_by(StateHistory.revision.desc()).first()
    next_revision = (latest.revision + 1) if latest else 1
    
    rollback_record = StateHistory(
        project_name=project_name,
        file_type=file_type,
        cut_number=cut_number,
        revision=next_revision,
        data=target.data,
        author="user",
        change_description=f"리비전 #{revision} 버전으로 롤백 복원"
    )
    db.add(rollback_record)
    db.commit()
    return rollback_record.data
