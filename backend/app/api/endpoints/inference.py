import os
import base64
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from ...core.database import get_db
from ...core.config import get_project_dirs, DEFAULT_MODEL_PATH
from ...core.llama_engine import MultiGPULlamaEngine
from ...models.db_models import StateHistory
from ...schemas.state_schemas import StateUpdateSchema
from .assets import parse_cut_number, VALID_EXTENSIONS

router = APIRouter(prefix="/inference", tags=["AI 추론 및 변환 파이프라인"])
logger = logging.getLogger("DeepScribe.InferenceRouter")

# 전역 엔진 싱글톤 홀더 (VRAM 중복 할당 방지)
_engine_instance: Optional[MultiGPULlamaEngine] = None

def get_llama_engine() -> MultiGPULlamaEngine:
    """추론 엔진 인스턴스를 반환하는 팩토리 싱글톤 헬퍼입니다."""
    global _engine_instance
    if _engine_instance is None:
        # settings.json 파일에서 사용자가 지정한 외부 API URL 동적 로딩
        api_url = "http://127.0.0.1:8081/v1/chat/completions"
        try:
            import json
            settings_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                "settings.json"
            )
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    api_url = settings.get("api_url", api_url)
        except Exception:
            pass

        # 기본값은 단일 GPU(-1) 및 레이어 전체 오프로드 설정입니다.
        _engine_instance = MultiGPULlamaEngine(
            model_path=DEFAULT_MODEL_PATH,
            n_ctx=4096,
            n_gpu_layers=-1,
            tensor_split=None, # 다중 GPU 사용 시 여기에 [0.6, 0.4] 등 실수 비율 설정 가능
            main_gpu=0,
            api_url=api_url
        )
    return _engine_instance


class ExtensibleExtractor:
    """
    향후 OCR 모듈 추가 등 확장성(Extensibility)을 고려하여 설계된 이미지 텍스트 추출 어댑터 클래스입니다.
    현시점에는 VRAM 제한으로 별도 모델 없이 Vision LLM에 원본 이미지를 함께 전달하여 OCR을 수행합니다.
    """
    @staticmethod
    def encode_image_base64(image_path: str) -> str:
        """
        이미지를 Base64 문자열로 변환합니다.
        llama.cpp의 stb_image 디코더 호환성과 OOM 방지를 위해 표준 RGB JPEG 포맷 변환 및 리사이징을 거칩니다.
        """
        from PIL import Image
        from io import BytesIO
        import base64

        with Image.open(image_path) as img:
            # 투명 채널이 있을 경우 흰색 배경 바탕에 붙여 흰색 배경으로 병합
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    background.paste(img, mask=img.split()[3])
                elif img.mode == "LA":
                    background.paste(img, mask=img.split()[1])
                else:
                    background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            # 고해상도 이미지는 VRAM 초과(OOM) 방지를 위해 최대 2048px 크기로 다운스케일
            max_dim = 2048
            if max(img.size) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=90, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def extract_scene_data(
        self, 
        image_path: str, 
        engine: MultiGPULlamaEngine,
        context_prompt: str,
        user_instruction: str
    ) -> dict:
        """
        망가 이미지에서 텍스트 및 상황 묘사를 추출합니다.
        향후 manga-ocr 등이 추가될 경우 이 메소드 상단에서 OCR을 선처리하도록 구조를 분리하였습니다.
        """
        # [확장 포인트]: 만약 로컬 OCR엔진을 붙이고자 할 경우 여기에 통합 코드를 추가합니다.
        # text_ocr_result = local_manga_ocr.predict(image_path)
        
        # 기본 처리: Vision API가 이미지 base64를 직접 수신
        try:
            img_b64 = self.encode_image_base64(image_path)
        except Exception as e:
            logger.error(f"이미지 인코딩 실패: {e}")
            return {"error": "이미지 파일을 읽을 수 없습니다."}

        # llama.cpp 서버용 이미지 입력을 위한 프롬프트 가공 및 전송
        # deepscribe/config.py 공통 설정에 정의된 MASTER PROMPT 적용
        from deepscribe.config import SYSTEM_PROMPT_STEP1
        
        system_prompt = SYSTEM_PROMPT_STEP1
        
        # 세계관 및 캐릭터 정보를 컨텍스트 프롬프트에 병합
        combined_user_prompt = (
            f"Please process this manga cut.\n\n"
            f"Prior Context History:\n{context_prompt}\n\n"
            f"Additional User Instructions/Comments:\n{user_instruction}\n\n"
            f"Analyze the attached image data and prior context, and generate the required JSON output."
        )
        
        # LLM에 JSON 형태 데이터 생성 지시 (이미지 base64 데이터를 멀티모달 규격으로 개별 전달)
        return engine.generate_json(system_prompt, combined_user_prompt, image_b64=img_b64)


@router.post("/run", response_model=dict)
def run_pipeline(
    payload: dict,
    db: Session = Depends(get_db),
    engine: MultiGPULlamaEngine = Depends(get_llama_engine)
):
    """
    선택된 컷 번호 목록에 대해 비전-텍스트 소설화 파이프라인을 실행합니다.
    추출된 최종 JSON 결과물은 지정된 프로젝트 범위 안에서 SQLite DB에 새 리비전으로 저장됩니다.
    """
    cut_numbers = payload.get("cut_numbers", [])
    user_instruction = payload.get("user_prompt", "소설 문체를 극도로 유려하고 자연스러운 성인 소설로 묘사해줘.")
    project_name = payload.get("project_name", "default")
    
    if not cut_numbers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="추론을 수행할 대상 컷 번호가 선택되지 않았습니다."
        )

    p_input, p_output = get_project_dirs(project_name)

    # 1. DB에서 모델 지시문에 연동할 지정 프로젝트의 최신 캐릭터 프로필 및 세계관 정보 조회
    theme_history = db.query(StateHistory).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == "theme_background"
    ).order_by(StateHistory.revision.desc()).first()
    
    char_history = db.query(StateHistory).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == "character_profiles"
    ).order_by(StateHistory.revision.desc()).first()
    
    context_str = ""
    if theme_history:
      context_str += f"[세계관 설정]\n{theme_history.data}\n\n"
    if char_history:
      context_str += f"[캐릭터 프로필]\n{char_history.data}\n\n"

    # 2. 이미지 파일 탐색 준비
    processed_count = 0
    extractor = ExtensibleExtractor()

    for cut_num in cut_numbers:
        # 입력 디렉토리에서 매칭되는 이미지 찾기
        target_image_path = None
        for entry in os.scandir(p_input):
            if entry.is_file() and entry.name.lower().endswith(VALID_EXTENSIONS):
                if parse_cut_number(entry.name) == cut_num:
                    target_image_path = entry.path
                    break

        if not target_image_path:
            logger.warning(f"컷 #{cut_num} 에 해당하는 이미지 파일을 찾을 수 없습니다. 건너뜁니다.")
            continue

        logger.info(f"파이프라인 실행 시작: {target_image_path} (컷 #{cut_num})")

        # 2.1. 일관성을 위해 이전 컷들의 최신 분석 데이터 및 소설 렌더링 결과 조회 (최대 2개 전 컷까지 조회)
        prior_cuts_context = ""
        for prev_offset in [2, 1]:  # 시간 순서대로 2대 전 -> 1대 전 순서로 구성
            prev_num = cut_num - prev_offset
            if prev_num > 0:
                prev_record = db.query(StateHistory).filter(
                    StateHistory.project_name == project_name,
                    StateHistory.file_type == "image_plot",
                    StateHistory.cut_number == prev_num
                ).order_by(StateHistory.revision.desc()).first()
                if prev_record and prev_record.data:
                    prev_scene = prev_record.data.get("scene_description", "N/A")
                    prev_manga = prev_record.data.get("manga_effects", "N/A")
                    prev_novel = prev_record.data.get("novel_paragraph", "N/A")
                    prior_cuts_context += (
                        f"--- [이전 컷 #{prev_num} 시각 분석 & 소설 문장] ---\n"
                        f"- 장면 분석: {prev_scene}\n"
                        f"- 체위/물리적 상호작용: {prev_manga}\n"
                        f"- 소설 렌더링:\n{prev_novel}\n\n"
                    )

        # 기본 세계관 설정과 이전 컷 문맥 통합
        current_context = context_str
        if prior_cuts_context:
            current_context += "[직전 컷 흐름 및 서사 일관성 정보 (Prior Story Flow)]\n" + prior_cuts_context

        # 3. 비전 분석 및 소설화 실행
        existing_context = payload.get("existing_context", "").strip() if payload else ""
        user_instruction_current = user_instruction
        if existing_context:
            user_instruction_current += (
                "\n\n[CRITICAL INSTRUCTION - Existing Cut Context to reference/expand/incorporate]:\n"
                "Here is the user's existing text for this cut. You MUST respect, reference, and expand upon "
                "this text, integrating it seamlessly into your vision-analyzed output. Do NOT discard or conflict with it:\n"
                f"{existing_context}"
            )

        step1_result = extractor.extract_scene_data(
            image_path=target_image_path,
            engine=engine,
            context_prompt=current_context,
            user_instruction=user_instruction_current
        )

        if "error" in step1_result:
            logger.error(f"컷 #{cut_num} 처리 중 에러 발생: {step1_result['error']}")
            continue

        # 4. DB에 결과 데이터의 신규 버전(Revision) 추가 저장
        # 중복 방지를 위한 최신 리비전 찾기
        latest_rev = db.query(StateHistory).filter(
            StateHistory.project_name == project_name,
            StateHistory.file_type == "image_plot",
            StateHistory.cut_number == cut_num
        ).order_by(StateHistory.revision.desc()).first()
        next_rev = (latest_rev.revision + 1) if latest_rev else 1

        new_history = StateHistory(
            project_name=project_name,
            file_type="image_plot",
            cut_number=cut_num,
            revision=next_rev,
            data=step1_result,
            author="ai",
            change_description=f"AI 자동 추론 파이프라인 변환 적용"
        )
        db.add(new_history)
        
        # 호환성을 위해 프로젝트별 outputs 디렉토리에 json 파일로 백업 저장
        output_file_path = os.path.join(p_output, f"{cut_num}.json")
        try:
            import json
            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(step1_result, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error(f"결과 파일 백업 중 디렉토리 저장 오류: {e}")

        processed_count += 1

    db.commit()
    return {
        "status": "success",
        "processed_cuts_count": processed_count
    }


@router.post("/analyze/theme", response_model=dict)
def analyze_theme_draft(
    payload: dict = {},
    project_name: str = "default",
    db: Session = Depends(get_db),
    engine: MultiGPULlamaEngine = Depends(get_llama_engine)
):
    """
    지정 프로젝트 디렉토리의 첫 대표 이미지를 분석하여 
    세계관 배경(theme_background) 스냅샷 초안을 LLM으로 자동 추출하고 DB에 신규 리비전으로 저장합니다.
    """
    p_input, _ = get_project_dirs(project_name)
    
    # 1. inputs 디렉토리에서 대표 이미지 탐색 (가장 알파벳 순서가 빠르거나 컷 번호가 빠른 파일)
    target_image_path = None
    if os.path.exists(p_input):
        entries = sorted([entry for entry in os.scandir(p_input) if entry.is_file() and entry.name.lower().endswith(VALID_EXTENSIONS)], key=lambda x: x.name)
        if entries:
            target_image_path = entries[0].path

    if not target_image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="선택된 작업 입력 디렉토리에 분석할 망가 이미지 파일이 존재하지 않습니다."
        )

    logger.info(f"[{project_name}] 세계관 분석을 위한 대표 이미지 로드: {target_image_path}")

    # 2. 이미지 Base64 인코딩
    extractor = ExtensibleExtractor()
    try:
        img_b64 = extractor.encode_image_base64(target_image_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대표 이미지 인코딩 실패: {str(e)}"
        )

    # 3. LLM 분석 요청
    from deepscribe.config import SYSTEM_PROMPT_THEME
    user_prompt = payload.get("user_prompt", "").strip() if payload else ""
    existing_context = payload.get("existing_context", "").strip() if payload else ""
    
    if not user_prompt:
        user_prompt = "Analyze the manga visual settings and establish a comprehensive background guide in Korean."
    
    if existing_context:
        user_prompt += (
            "\n\n[CRITICAL INSTRUCTION - Existing Setting Context to reference/expand/incorporate]:\n"
            "Here is the user's existing background setting. You MUST respect, reference, and expand upon "
            "this text, integrating it seamlessly into your vision-analyzed output. Do NOT discard or conflict with it:\n"
            f"{existing_context}"
        )
    
    try:
        result = engine.generate_json(SYSTEM_PROMPT_THEME, user_prompt, image_b64=img_b64)
    except Exception as e:
        logger.error(f"세계관 LLM 분석 추론 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM 비전 분석 실패: {str(e)}"
        )

    # 4. DB 저장 (theme_background 유형의 새 리비전 생성)
    latest_rev = db.query(StateHistory).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == "theme_background"
    ).order_by(StateHistory.revision.desc()).first()
    next_rev = (latest_rev.revision + 1) if latest_rev else 1

    new_history = StateHistory(
        project_name=project_name,
        file_type="theme_background",
        cut_number=None,
        revision=next_rev,
        data=result,
        author="ai",
        change_description="AI 자동 세계관 분석 초안 생성"
    )
    db.add(new_history)
    db.commit()
    db.refresh(new_history)

    return {
        "status": "success",
        "revision": next_rev,
        "data": result
    }


@router.post("/analyze/characters", response_model=dict)
def analyze_characters_draft(
    payload: dict = {},
    project_name: str = "default",
    db: Session = Depends(get_db),
    engine: MultiGPULlamaEngine = Depends(get_llama_engine)
):
    """
    지정 프로젝트 디렉토리의 첫 대표 이미지를 분석하여 
    등장인물 성향 및 관계 정보(character_profiles) 초안을 LLM으로 자동 추출하고 DB에 신규 리비전으로 저장합니다.
    """
    p_input, _ = get_project_dirs(project_name)

    # 1. inputs 디렉토리에서 대표 이미지 탐색
    target_image_path = None
    if os.path.exists(p_input):
        entries = sorted([entry for entry in os.scandir(p_input) if entry.is_file() and entry.name.lower().endswith(VALID_EXTENSIONS)], key=lambda x: x.name)
        if entries:
            target_image_path = entries[0].path

    if not target_image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="선택된 작업 입력 디렉토리에 분석할 망가 이미지 파일이 존재하지 않습니다."
        )

    logger.info(f"[{project_name}] 등장인물 분석을 위한 대표 이미지 로드: {target_image_path}")

    # 2. 이미지 Base64 인코딩
    extractor = ExtensibleExtractor()
    try:
        img_b64 = extractor.encode_image_base64(target_image_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대표 이미지 인코딩 실패: {str(e)}"
        )

    # 3. LLM 분석 요청
    from deepscribe.config import SYSTEM_PROMPT_CHARACTERS
    user_prompt = payload.get("user_prompt", "").strip() if payload else ""
    existing_context = payload.get("existing_context", "").strip() if payload else ""
    
    if not user_prompt:
        user_prompt = "Identify characters and reconstruct their relationship profile in Korean based on visual cues."
    
    if existing_context:
        user_prompt += (
            "\n\n[CRITICAL INSTRUCTION - Existing Profiles Context to reference/expand/incorporate]:\n"
            "Here is the user's existing character profile settings. You MUST respect, reference, and expand upon "
            "this text, integrating it seamlessly into your vision-analyzed output. Do NOT discard or conflict with it:\n"
            f"{existing_context}"
        )
    
    try:
        result = engine.generate_json(SYSTEM_PROMPT_CHARACTERS, user_prompt, image_b64=img_b64)
    except Exception as e:
        logger.error(f"캐릭터 LLM 분석 추론 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM 비전 분석 실패: {str(e)}"
        )

    # 4. DB 저장 (character_profiles 유형의 새 리비전 생성)
    latest_rev = db.query(StateHistory).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == "character_profiles"
    ).order_by(StateHistory.revision.desc()).first()
    next_rev = (latest_rev.revision + 1) if latest_rev else 1

    new_history = StateHistory(
        project_name=project_name,
        file_type="character_profiles",
        cut_number=None,
        revision=next_rev,
        data=result,
        author="ai",
        change_description="AI 자동 캐릭터 프로필 및 관계 분석 초안 생성"
    )
    db.add(new_history)
    db.commit()
    db.refresh(new_history)

    return {
        "status": "success",
        "revision": next_rev,
        "data": result
    }


@router.post("/analyze/plot", response_model=dict)
def analyze_plot_draft(
    payload: dict = {},
    project_name: str = "default",
    db: Session = Depends(get_db),
    engine: MultiGPULlamaEngine = Depends(get_llama_engine)
):
    """
    지정 프로젝트 디렉토리의 첫 대표 이미지를 분석하여 
    전체 줄거리(overall_plot) 시나리오 초안을 LLM으로 자동 추출하고 DB에 신규 리비전으로 저장합니다.
    """
    p_input, _ = get_project_dirs(project_name)

    # 1. inputs 디렉토리에서 대표 이미지 탐색
    target_image_path = None
    if os.path.exists(p_input):
        entries = sorted([entry for entry in os.scandir(p_input) if entry.is_file() and entry.name.lower().endswith(VALID_EXTENSIONS)], key=lambda x: x.name)
        if entries:
            target_image_path = entries[0].path

    if not target_image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="선택된 작업 입력 디렉토리에 분석할 망가 이미지 파일이 존재하지 않습니다."
        )

    logger.info(f"[{project_name}] 전체 줄거리 분석을 위한 대표 이미지 로드: {target_image_path}")

    # 2. 이미지 Base64 인코딩
    extractor = ExtensibleExtractor()
    try:
        img_b64 = extractor.encode_image_base64(target_image_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"대표 이미지 인코딩 실패: {str(e)}"
        )

    # 3. LLM 분석 요청
    system_prompt = (
        "You are an expert manga story visual analyzer. "
        "Analyze the provided representative visual cues, panels, art styles, characters, and atmosphere, "
        "and generate a cohesive, structured overall story plot (overall_plot) draft in Korean. "
        "Your response MUST be in JSON format matching the schema:\n"
        "{\n"
        "  \"overall_plot\": \"A rich and descriptive paragraph outlining the entire story arc, narrative structure, conflict, and potential climax.\"\n"
        "}"
    )
    
    user_prompt = payload.get("user_prompt", "").strip() if payload else ""
    existing_context = payload.get("existing_context", "").strip() if payload else ""
    
    if not user_prompt:
        user_prompt = "Establish a detailed overall novel plot outline in Korean based on visual cues from the manga first chapter cover or panel."
    
    if existing_context:
        user_prompt += (
            "\n\n[CRITICAL INSTRUCTION - Existing Plot Context to reference/expand/incorporate]:\n"
            "Here is the user's existing overall plot. You MUST respect, reference, and expand upon "
            "this text, integrating it seamlessly into your vision-analyzed output. Do NOT discard or conflict with it:\n"
            f"{existing_context}"
        )

    try:
        result = engine.generate_json(system_prompt, user_prompt, image_b64=img_b64)
    except Exception as e:
        logger.error(f"전체 줄거리 LLM 분석 추론 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM 비전 분석 실패: {str(e)}"
        )

    # 4. DB 저장 (overall_plot 유형의 새 리비전 생성)
    latest_rev = db.query(StateHistory).filter(
        StateHistory.project_name == project_name,
        StateHistory.file_type == "overall_plot"
    ).order_by(StateHistory.revision.desc()).first()
    next_rev = (latest_rev.revision + 1) if latest_rev else 1

    new_history = StateHistory(
        project_name=project_name,
        file_type="overall_plot",
        cut_number=None,
        revision=next_rev,
        data=result,
        author="ai",
        change_description="AI 자동 전체 줄거리 분석 초안 생성"
    )
    db.add(new_history)
    db.commit()
    db.refresh(new_history)

    return {
        "status": "success",
        "revision": next_rev,
        "data": result
    }


@router.post("/refine/novel", response_model=dict)
def refine_novel(
    payload: dict,
    db: Session = Depends(get_db),
    engine: MultiGPULlamaEngine = Depends(get_llama_engine)
):
    """
    사용자가 입력한 프롬프트를 바탕으로 전체 생성된 소설 원고를 재교열/윤문(Polishing)합니다.
    """
    project_name = payload.get("project_name", "default")
    user_prompt = payload.get("user_prompt", "소설 문맥을 매끄럽고 자연스럽게 다듬어주세요.").strip()
    full_text = payload.get("full_novel", "").strip()
    
    if not full_text or full_text.startswith("아직 변환 완료"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="교열할 소설 원고 내용이 없습니다."
        )
        
    system_prompt = (
        "You are an expert novel editor and proofreader. "
        "Your task is to refine, polish, and improve the provided novel manuscript in Korean "
        "according to the user's instructions. Keep the core narrative identical, but make the "
        "flow, tone, and transitions exceptionally smooth and natural. Output ONLY the polished novel text."
    )
    
    refined_text = engine.generate_text(system_prompt, f"User Instruction: {user_prompt}\n\nOriginal Manuscript:\n{full_text}")
    
    return {"refined_novel": refined_text}

