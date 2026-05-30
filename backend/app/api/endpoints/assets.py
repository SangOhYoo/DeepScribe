import os
import re
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from typing import List
from ...core.config import get_project_dirs

router = APIRouter(prefix="/assets", tags=["에셋 & 업로드 관리"])

# 지원하는 이미지 파일 확장자 지정
VALID_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")

def parse_cut_number(filename: str) -> int:
    """
    파일명에서 실제 컷 번호를 정확히 추출합니다.
    1. 파일명 중 괄호로 감싸진 숫자 시퀀스 (예: フトシ1(20).webp -> 20)를 우선 추출합니다.
    2. 괄호가 없을 경우, 파일명 전체에서 가장 마지막에 위치하는 숫자 시퀀스 (예: cut_15.png -> 15)를 추출합니다.
    """
    # 1. 괄호로 둘러싸인 숫자 매칭 시도
    paren_match = re.search(r"\((\d+)\)", filename)
    if paren_match:
        return int(paren_match.group(1))
        
    # 2. 괄호 매칭 실패 시 파일명 내 모든 숫자 중 가장 마지막 숫자 그룹 추출
    all_numbers = re.findall(r"\d+", filename)
    if all_numbers:
        return int(all_numbers[-1])
        
    # 숫자가 없는 파일은 정렬 순위 최하위를 위해 9999로 가상 설정
    return 9999

@router.get("", response_model=List[dict])
def list_assets(project_name: str = "default"):
    """로컬 입력 폴더 내의 망가 컷 이미지 리스트와 분석 완료 상태 코드를 반환합니다."""
    assets_list = []
    p_input, p_output = get_project_dirs(project_name)

    if not os.path.exists(p_input):
        return []

    for entry in os.scandir(p_input):
        if entry.is_file() and entry.name.lower().endswith(VALID_EXTENSIONS):
            cut_num = parse_cut_number(entry.name)
            # 결과물 디렉토리에 {cut_num}.json 데이터가 존재하면 완료(completed) 상태로 판정
            output_file = os.path.join(p_output, f"{cut_num}.json")
            status_flag = "completed" if os.path.exists(output_file) else "pending"
            
            assets_list.append({
                "cut_number": cut_num,
                "filename": entry.name,
                "status": status_flag,
                "file_path": f"/media/input/{project_name}/{entry.name}"  # 프로젝트 격리 정적 미디어 경로 매핑
            })
            
    # 컷 번호 기준 순차 정렬
    assets_list.sort(key=lambda x: x["cut_number"])
    return assets_list


@router.post("/upload", response_model=dict)
async def upload_assets(project_name: str = "default", files: List[UploadFile] = File(...)):
    """여러 장의 망가 이미지 파일들을 일괄 수신하여 프로젝트 격리된 입력 폴더에 저장합니다."""
    p_input, _ = get_project_dirs(project_name)
    saved_files = []
    
    for file in files:
        if not file.filename:
            continue
        
        # 파일 경로 인젝션 방지를 위한 기초 파일명 분리 정제
        filename = os.path.basename(file.filename)
        # 특수문자 제거
        filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
        
        file_path = os.path.join(p_input, filename)
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(filename)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"파일 {filename} 저장 중 오류 발생: {str(e)}"
            )
            
    return {"status": "success", "saved_files": saved_files}


@router.post("/batch-delete", response_model=dict)
def batch_delete_assets(payload: dict):
    """체크박스로 선택된 컷 번호 목록을 받아 원본 이미지와 매칭되는 JSON 결과를 삭제합니다."""
    cut_numbers = payload.get("cut_numbers", [])
    project_name = payload.get("project_name", "default")
    
    if not cut_numbers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="삭제할 컷 번호 목록이 비어 있습니다."
        )

    p_input, p_output = get_project_dirs(project_name)
    deleted_images_count = 0
    deleted_results_count = 0

    # 1. 원본 이미지 탐색 및 삭제
    for entry in os.scandir(p_input):
        if entry.is_file() and entry.name.lower().endswith(VALID_EXTENSIONS):
            if parse_cut_number(entry.name) in cut_numbers:
                try:
                    os.remove(entry.path)
                    deleted_images_count += 1
                except OSError:
                    pass

    # 2. 파이프라인 분석 완료 JSON 결과물 제거
    for cut_num in cut_numbers:
        output_file = os.path.join(p_output, f"{cut_num}.json")
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
                deleted_results_count += 1
            except OSError:
                pass

    return {
        "status": "success",
        "deleted_images": deleted_images_count,
        "deleted_results": deleted_results_count
    }
