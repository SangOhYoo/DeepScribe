import re

class FactChecker:
    """
    Fact vs. Fiction Separator: Detects legal/technical keywords and separates
    facts from fiction using external APIs (currently mocked).
    """
    def __init__(self):
        # Example keywords that trigger a fact check
        self.trigger_keywords = ["사후인지", "공시송달", "집행유예", "친권상실", "형사합의"]

    def _mock_search_api(self, keyword: str) -> str:
        """Mock external API for fetching 2025-2026 legal facts."""
        mock_db = {
            "공시송달": "2025년 기준 민사소송법 개정에 따라 공시송달 요건이 더욱 엄격해짐 (전자공시 확대).",
            "사후인지": "가족관계등록법 상 혼인외 출생자의 사후인지 청구 소송 절차 (최신 판례 기준 적용)."
        }
        return mock_db.get(keyword, f"{keyword}에 대한 2026년 기준 법리/기술적 팩트 확인 필요.")

    def check_facts(self, text: str) -> dict[str, any]:
        found_keywords = []
        for keyword in self.trigger_keywords:
            if keyword in text:
                found_keywords.append(keyword)
                
        facts = {}
        for kw in found_keywords:
            facts[kw] = self._mock_search_api(kw)
            
        return {
            "has_warnings": len(facts) > 0,
            "facts": facts
        }
