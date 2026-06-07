import re
from client import LlamaAPIClient

class StyleRhythmFilter:
    """
    Style & Rhythm Filter: Detects translated style (번역투) and passive voice.
    Suggests omitting subjects and enforcing Korean rhythm.
    """
    def __init__(self, client: LlamaAPIClient):
        self.client = client
        # Simple regex for passive voice or translated style
        self.patterns = [
            (r'\b(\w+)에 의해\b', '번역투 (~에 의해) 발견'),
            (r'\b(\w+)되어지다\b', '이중 피동 (~되어지다) 발견'),
            (r'\b가짐을 당하다\b', '부자연스러운 피동 발견')
        ]

    def rule_based_check(self, text: str) -> list[str]:
        warnings = []
        for pattern, msg in self.patterns:
            if re.search(pattern, text):
                warnings.append(msg)
        return warnings

    def apply_llm_filter(self, text: str) -> str:
        """Uses LLM to rewrite the text into natural Korean novel style."""
        sys_prompt = (
            "You are an expert Korean novel editor. Your task is to rewrite the given text "
            "to remove translated styles (번역투), unnecessary passive voices (피동형), "
            "and omit obvious subjects to enhance the unique rhythm of the Korean language. "
            "Return ONLY the corrected text."
        )
        result = self.client.send_chat_completion(
            system_prompt=sys_prompt,
            user_prompt=text,
            temperature=0.3
        )
        return result if isinstance(result, str) else text

    def process(self, text: str) -> dict[str, any]:
        warnings = self.rule_based_check(text)
        corrected_text = text
        if warnings:
            corrected_text = self.apply_llm_filter(text)
            
        return {
            "original": text,
            "corrected": corrected_text,
            "warnings": warnings,
            "is_modified": text != corrected_text
        }
