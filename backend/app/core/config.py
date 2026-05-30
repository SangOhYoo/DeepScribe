import os
import sys

# 디렉토리 기본 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT_DIR = os.path.dirname(BASE_DIR) # d:\DeepScribe 루트 경로 검출
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import shutil

ROOT_INPUT_DIR = os.path.join(BASE_DIR, "inputs")
ROOT_OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# 기본 프로젝트용 하위 호환 경로
INPUT_DIR = os.path.join(ROOT_INPUT_DIR, "default")
OUTPUT_DIR = os.path.join(ROOT_OUTPUT_DIR, "default")

# GGUF 모델 가중치 파일 경로 정의 (기본값 설정)
DEFAULT_MODEL_PATH = os.path.join(BASE_DIR, "models", "uncensored-model.gguf")

# 디렉토리 계층 자동 생성
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DEFAULT_MODEL_PATH), exist_ok=True)

# [하위 호환 마이그레이션] 루트 inputs/outputs에 들어있던 파일을 default/ 로 이관
VALID_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
try:
    if os.path.exists(ROOT_INPUT_DIR):
        for name in os.listdir(ROOT_INPUT_DIR):
            full_src = os.path.join(ROOT_INPUT_DIR, name)
            if os.path.isfile(full_src) and name.lower().endswith(VALID_EXTENSIONS):
                shutil.move(full_src, os.path.join(INPUT_DIR, name))
                
    if os.path.exists(ROOT_OUTPUT_DIR):
        for name in os.listdir(ROOT_OUTPUT_DIR):
            full_src = os.path.join(ROOT_OUTPUT_DIR, name)
            if os.path.isfile(full_src) and name.lower().endswith(".json"):
                shutil.move(full_src, os.path.join(OUTPUT_DIR, name))
except Exception as e:
    print(f"Error during default workspace file migration: {e}")

def get_project_dirs(project_name: str = "default"):
    """프로젝트명을 기반으로 격리된 입력/출력 디렉토리 경로를 반환하며 자동 생성합니다."""
    # 프로젝트명 특수문자 정제
    safe_name = "".join([c for c in project_name if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).strip()
    if not safe_name:
        safe_name = "default"
        
    p_input = os.path.join(ROOT_INPUT_DIR, safe_name)
    p_output = os.path.join(ROOT_OUTPUT_DIR, safe_name)
    
    os.makedirs(p_input, exist_ok=True)
    os.makedirs(p_output, exist_ok=True)
    return p_input, p_output
