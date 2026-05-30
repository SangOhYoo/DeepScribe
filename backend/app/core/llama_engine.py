import os
import logging
import json
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger("DeepScribe.LlamaEngine")

class MultiGPULlamaEngine:
    """
    llama-cpp-python을 이용하거나, 외부의 llama.cpp HTTP 서버와 API 통신하여
    추론을 처리하는 다형성(Polymorphic) 추론 엔진 클래스입니다.
    """
    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        tensor_split: Optional[List[float]] = None,
        main_gpu: int = 0,
        api_url: str = "http://127.0.0.1:8081/v1/chat/completions"
    ):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.tensor_split = tensor_split
        self.main_gpu = main_gpu
        self.api_url = api_url
        self.llm = None
        self.use_external_server = False
        self.api_key = None

        # settings.json 에서 api_key 로드
        try:
            settings_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                "settings.json"
            )
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self.api_key = settings.get("api_key")
        except Exception:
            pass

        if not self.api_key:
            self.api_key = "man-to-man-key-4501"

        # 모델 파일이 없거나 llama-cpp-python 로드가 실패하면 자동으로 외장 HTTP API 연동 모드로 전환합니다.
        try:
            from llama_cpp import Llama
            if os.path.exists(self.model_path) and os.path.isfile(self.model_path):
                self.use_external_server = False
            else:
                logger.info(f"로컬 GGUF 모델 가중치 파일이 존재하지 않아 외장 API 연동 모드로 작동합니다. 대상 URL: {self.api_url}")
                self.use_external_server = True
        except ImportError:
            logger.info(f"llama-cpp-python 라이브러리가 설치되지 않았으므로 자동으로 외장 API 연동 모드로 작동합니다. 대상 URL: {self.api_url}")
            self.use_external_server = True

    def load_model(self):
        """로컬 모드일 경우에만 모델을 기동합니다. API 모드일 경우 동작을 생략합니다."""
        if self.use_external_server:
            logger.info("외장 API 서버 모드로 구동하므로 로컬 가중치 로딩을 건너뜁니다.")
            return

        from llama_cpp import Llama
        logger.info(f"로컬 GGUF 모델 로드 중: {self.model_path}")
        try:
            self.llm = Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                tensor_split=self.tensor_split,
                main_gpu=self.main_gpu,
                verbose=False
            )
        except Exception as e:
            logger.error(f"로컬 GGUF 로드 중 실패하여 외장 API 연동 모드로 대체 복원합니다. 에러: {e}")
            self.use_external_server = True

    def extract_clean_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        추론 출력에서 JSON 문자열을 견고하게 파싱합니다.
        마크다운 코드 블록(```json) 및 앞뒤의 불필요한 텍스트를 제거하고 복원합니다.
        """
        if not text:
            return None
        
        text_stripped = text.strip()
        
        # 1. 즉각적인 json.loads 시도
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass
            
        # 2. 첫 '{'와 마지막 '}' 사이의 구간 추출
        first_brace = text_stripped.find('{')
        last_brace = text_stripped.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_candidate = text_stripped[first_brace:last_brace + 1]
            try:
                return json.loads(json_candidate)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 구조를 찾았으나 일차 파싱 실패: {e}. 복구를 시도합니다.")
                
                # 줄바꿈 복구 및 특수 이스케이프 문자 정제
                import re
                try:
                    # JSON 값 내부에 이스케이프되지 않은 개행 문자 처리
                    cleaned = re.sub(r'(?<!\\)\n', '\\n', json_candidate)
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass
        else:
            logger.error("응답 텍스트 내에서 중괄호 {} 형태의 JSON 구조를 발견하지 못했습니다.")
            
        return None

    def generate_json(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        image_b64: Optional[str] = None, 
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """지정 프롬프트를 바탕으로 추론을 요청하고 구조화된 JSON 결과를 반환합니다."""
        
        # 1. 외장 서버 연동 모드일 경우 (컴파일 없이 실행 가능)
        if self.use_external_server:
            user_content = [{"type": "text", "text": user_prompt}]
            if image_b64:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}"
                    }
                })

            payload = {
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": temperature,
                "response_format": {"type": "json_object"}
            }
            
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            try:
                logger.info(f"외장 API 서버 ({self.api_url})에 소설화 추론을 요청합니다...")
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=300
                )
                response.raise_for_status()
                res_data = response.json()
                raw_content = res_data["choices"][0]["message"]["content"]
                
                parsed = self.extract_clean_json(raw_content)
                if parsed is not None:
                    return parsed
                raise ValueError("추론 결과에서 유효한 JSON 구조를 추출하지 못했습니다.")
            except Exception as e:
                logger.error(f"외장 API 서버 호출 중 에러 발생: {e}")
                return {"error": "외장 API 서버 통신 실패", "details": str(e)}

        # 2. 로컬 모드일 경우 (llama-cpp-python 로드 완료)
        if self.llm is None:
            self.load_model()
            
        try:
            user_content = [{"type": "text", "text": user_prompt}]
            if image_b64:
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}"
                    }
                })

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
            response = self.llm.create_chat_completion(
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            raw_content = response["choices"][0]["message"]["content"]
            
            parsed = self.extract_clean_json(raw_content)
            if parsed is not None:
                return parsed
            raise ValueError("로컬 추론 결과에서 유효한 JSON 구조를 추출하지 못했습니다.")
        except Exception as e:
            logger.error(f"로컬 추론 중 오류 발생: {e}")
            return {"error": "로컬 추론 실패", "details": str(e)}

    def generate_text(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.5
    ) -> str:
        """지정 프롬프트를 바탕으로 추론을 요청하고 일반 텍스트 문자열 결과를 반환합니다."""
        if self.use_external_server:
            payload = {
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
                ],
                "temperature": temperature
            }
            
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            try:
                logger.info(f"외장 API 서버 ({self.api_url})에 텍스트 추론을 요청합니다...")
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=300
                )
                response.raise_for_status()
                res_data = response.json()
                return res_data["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"외장 API 서버 호출 중 에러 발생: {e}")
                return f"에러: 외장 API 서버 통신 실패. {str(e)}"

        if self.llm is None:
            self.load_model()
            
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
            ]
            response = self.llm.create_chat_completion(
                messages=messages,
                temperature=temperature
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"로컬 추론 중 오류 발생: {e}")
            return f"에러: 로컬 추론 실패. {str(e)}"
