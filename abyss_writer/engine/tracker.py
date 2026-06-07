from client import LlamaAPIClient

class TimelineTracker:
    """
    Timeline & Foreshadowing Tracker: Validates logical consistency 
    between current scene and previous events.
    """
    def __init__(self, client: LlamaAPIClient):
        self.client = client

    def validate_logic(self, history_context: str, new_scene: str) -> dict[str, any]:
        sys_prompt = (
            "당신은 엄격한 연속성 편집자입니다. [이전 맥락]과 [새로운 씬]을 비교하세요. "
            "논리적 모순, 타임라인 오류, 복선 충돌(물리적 제약, 경과 시간, 법적 지위 변화 등)을 점검하세요. "
            "충돌이 있으면 JSON 응답: {\"conflict_found\": true, \"reason\": \"<한국어로 상세 설명>\"}. "
            "충돌이 없으면: {\"conflict_found\": false, \"reason\": \"\"}."
        )
        user_prompt = f"[이전 맥락]\n{history_context}\n\n[새로운 씬]\n{new_scene}"
        
        result = self.client.send_chat_completion(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            parse_json=True
        )
        
        if isinstance(result, dict):
            return result
        return {"conflict_found": False, "reason": "Failed to parse validation."}
