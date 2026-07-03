"""
Relationship Corrector Service.
Adjusts character relationships in translated Korean text using LLM.
Remaps honorifics, speech patterns, and nuances while preserving plot integrity.
"""

import logging
import os
import time
import tempfile
import concurrent.futures
from typing import Optional, Callable

from .llm_client import TranslationClient

logger = logging.getLogger("NovelTranslator.RelationshipCorrector")


# ─── Preset Definitions ────────────────────────────────────────────────

RELATION_PRESETS = {
    "부모 → 숙부모": [
        {"source": "어머니", "target": "숙모", "note": "엄마→숙모, 아들/딸→조카"},
        {"source": "아버지", "target": "숙부", "note": "아빠→숙부, 아들/딸→조카"},
        {"source": "엄마", "target": "숙모", "note": ""},
        {"source": "아빠", "target": "숙부", "note": ""},
        {"source": "아들", "target": "조카", "note": ""},
        {"source": "딸", "target": "조카", "note": ""},
        {"source": "우리 아이", "target": "우리 조카", "note": ""},
    ],
    "연인 → 소꿉친구": [
        {"source": "여자친구", "target": "소꿉친구", "note": "연인→소꿉친구 (여)"},
        {"source": "남자친구", "target": "소꿉친구", "note": "연인→소꿉친구 (남)"},
        {"source": "자기야", "target": "이름 호칭", "note": "애칭→이름 또는 별명"},
        {"source": "여보", "target": "이름 호칭", "note": "부부 호칭→일반 호칭"},
        {"source": "오빠", "target": "이름+야/아", "note": "연인 오빠→이름 반말"},
    ],
    "선배 → 동기": [
        {"source": "선배", "target": "동기", "note": "상하 관계→대등 관계"},
        {"source": "선배님", "target": "이름+씨", "note": "존칭→일반 격식"},
        {"source": "후배", "target": "동기", "note": ""},
    ],
    "형제/자매 → 사촌": [
        {"source": "형", "target": "사촌형", "note": "형→사촌형"},
        {"source": "누나", "target": "사촌누나", "note": ""},
        {"source": "오빠", "target": "사촌오빠", "note": ""},
        {"source": "언니", "target": "사촌언니", "note": ""},
        {"source": "동생", "target": "사촌동생", "note": ""},
    ],
    "사용자 정의": [],
}

PRESET_CHOICES = list(RELATION_PRESETS.keys())


# ─── System Prompt Builder ──────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """[캐릭터 관계성 교정 전문가 / Character Relationship Corrector]

당신은 번역된 한국어 소설 텍스트의 '캐릭터 관계성(Entity Relationship)'을 재조정하는 전문 NLP 문맥 교정 엔진입니다.
당신의 목표는 아래 지정된 인물 간의 관계 변화에 맞추어, 원문의 플롯을 전혀 훼손하지 않고 호칭, 말투, 그리고 대화의 뉘앙스만 한국어 정서에 맞게 교정하는 것입니다.

═══════════════════════════════════════
핵심 규칙 (CORE RULES)
═══════════════════════════════════════

1. [플롯 보존의 원칙]
   - 원문에 명시된 사건의 순서, 시간적 배경, 인물들의 물리적 행동(Action)은 절대 수정하거나 삭제, 추가하지 마십시오.
   - 스토리 전개, 대화 내용의 의미, 감정의 흐름은 반드시 유지하십시오.

2. [호칭 및 대명사 매핑]
   - 아래 관계 매핑 테이블의 {source_relation}을 {target_relation}으로 정확히 치환하십시오.
   - 호칭이 바뀌면서 연쇄적으로 변해야 하는 화자(나)의 포지션도 함께 수정하십시오.
   - 예: 어머니→숙모이면, 화자의 자칭도 아들/딸→조카로 자연스럽게 변경

3. [한국어 화법 및 경어체 조정]
   - 변경된 사회적 거리(Social Distance)와 서열에 맞게 대화문의 종결 어미(존댓말/반말)와 어휘를 자연스럽게 조정하십시오.
   - 예: 어머니가 자식에게 하는 편한 반말 → 숙모가 조카에게 하는 약간의 거리가 있는 반말 또는 존댓말
   - 나레이션(서술부)의 어투도 관계 변화에 맞게 미세 조정하십시오.

4. [생물학적/논리적 모순 회피]
   - 관계 변경으로 인해 명백한 생물학적 모순이 발생할 경우, 물리적 행동의 의미를 훼손하지 않는 선에서 사회적으로 통용되는 표현으로 우회하여 번역하십시오.
   - 예: "숙모가 나를 배 속에 열 달 동안 품었다" → "숙모가 나를 친자식처럼 애지중지 키웠다"
   - 예: "우리 피가 같으니까" → "우리 가족이니까"

═══════════════════════════════════════
관계 매핑 테이블
═══════════════════════════════════════
{mapping_table}

═══════════════════════════════════════
출력 규칙
═══════════════════════════════════════
- 입력된 텍스트를 위 규칙에 따라 교정한 결과만 출력하십시오.
- 설명, 주석, 마크다운 기호 없이 교정된 소설 텍스트만 반환하십시오.
- 원문의 줄바꿈과 단락 구조를 그대로 유지하십시오.
"""


def build_system_prompt(mappings: list[dict]) -> str:
    """Build the system prompt with mapping table from user-defined relationships."""
    if not mappings:
        return SYSTEM_PROMPT_TEMPLATE.replace("{mapping_table}", "(매핑 규칙이 지정되지 않았습니다.)")

    table_lines = []
    for i, m in enumerate(mappings, 1):
        src = m.get("source", "").strip()
        tgt = m.get("target", "").strip()
        note = m.get("note", "").strip()
        if src and tgt:
            line = f"  {i}. {src} → {tgt}"
            if note:
                line += f"  ({note})"
            table_lines.append(line)

    table_str = "\n".join(table_lines) if table_lines else "(유효한 매핑 규칙이 없습니다.)"
    return SYSTEM_PROMPT_TEMPLATE.replace("{mapping_table}", table_str)


def build_user_prompt(text: str, context: str = "") -> str:
    """Build the user prompt for relationship correction."""
    parts = []
    if context:
        parts.append(f"[이전 맥락 참고 (교정 연속성 유지)]\n{context}\n\n---\n")
    parts.append(f"아래 한국어 번역 텍스트의 캐릭터 관계성을 위 매핑 규칙에 따라 교정해 주세요:\n\n{text}")
    return "".join(parts)


# ─── Main Corrector Class ───────────────────────────────────────────────

class RelationshipCorrector:
    """Corrects character relationships in translated Korean text using LLM."""

    def __init__(self):
        self.client: Optional[TranslationClient] = None
        self._cancel = False

    def cancel(self):
        """Signal cancellation."""
        self._cancel = True

    def correct_text(
        self,
        text: str,
        mappings: list[dict],
        api_url: str = "",
        api_key: str = "",
        chunk_size: int = 4000,
        max_workers: int = 4,
    ):
        """
        Correct character relationships in the given text as a generator.
        Yields: (current_chunk, total_chunks, status_msg, current_corrected_text, download_path_or_none)
        """
        self._cancel = False

        if not text or not text.strip():
            yield 0, 0, "❌ 입력 텍스트가 비어 있습니다.", "", None
            return

        # Validate mappings
        valid_mappings = [
            m for m in mappings
            if m.get("source", "").strip() and m.get("target", "").strip()
        ]
        if not valid_mappings:
            yield 1, 1, "⚠️ 매핑 규칙이 없습니다.", text, None
            return

        # Initialize client
        client_kwargs = {}
        if api_url:
            client_kwargs["api_url"] = api_url
        if api_key:
            client_kwargs["api_key"] = api_key
        self.client = TranslationClient(**client_kwargs)

        # Build system prompt
        system_prompt = build_system_prompt(valid_mappings)

        # Split text into chunks by paragraphs
        chunks = self._split_into_chunks(text, chunk_size)
        total_chunks = len(chunks)

        yield 0, total_chunks, f"⏳ 교정 시작 (총 {total_chunks}개 청크)...", "", None

        corrected_parts = [None] * total_chunks

        def process_chunk(index, chunk_text):
            if self._cancel:
                return index, chunk_text
                
            prev_ctx = chunks[index - 1][-300:].strip() if index > 0 else ""
            user_prompt = build_user_prompt(chunk_text, prev_ctx)
            
            try:
                result = self.client.translate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.2,
                    frequency_penalty=0.05,
                    presence_penalty=0.05,
                )
                if result:
                    cleaned = self._clean_thinking_tags(result)
                    return index, cleaned
                else:
                    logger.warning(f"LLM returned empty for chunk {index + 1}, keeping original")
                    return index, chunk_text
            except Exception as e:
                logger.error(f"Error correcting chunk {index + 1}: {e}")
                return index, chunk_text

        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_chunk, i, chunk): i for i, chunk in enumerate(chunks)}
            
            for future in concurrent.futures.as_completed(futures):
                if self._cancel:
                    break
                index, result_text = future.result()
                corrected_parts[index] = result_text
                completed += 1
                
                # 실시간 프리뷰를 위해 미완료 청크는 원본으로 채워 전체 줄 수 일치 유지
                current_text = "\n\n".join([p if p is not None else chunks[idx] for idx, p in enumerate(corrected_parts)])
                yield completed, total_chunks, f"청크 {completed}/{total_chunks} 교정 중...", current_text, None

        if self._cancel:
            corrected_text = "\n\n".join([p if p is not None else chunks[idx] for idx, p in enumerate(corrected_parts)])
            yield completed, total_chunks, "⚠️ 사용자에 의해 취소됨", corrected_text, None
            return

        corrected_text = "\n\n".join(corrected_parts)

        # Save to file
        download_path = self._save_to_file(corrected_text)

        yield total_chunks, total_chunks, "✅ 교정 완료!", corrected_text, download_path

    def _split_into_chunks(self, text: str, max_chars: int) -> list[str]:
        """Split text into chunks respecting paragraph boundaries."""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)

            # If single paragraph exceeds max, split by lines
            if para_len > max_chars:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_len = 0

                lines = para.split("\n")
                line_chunk = []
                line_len = 0
                for line in lines:
                    if line_len + len(line) + 1 > max_chars and line_chunk:
                        chunks.append("\n".join(line_chunk))
                        line_chunk = []
                        line_len = 0
                    line_chunk.append(line)
                    line_len += len(line) + 1
                if line_chunk:
                    chunks.append("\n".join(line_chunk))
                continue

            if current_len + para_len + 2 > max_chars and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_len = 0

            current_chunk.append(para)
            current_len += para_len + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [text]

    def _clean_thinking_tags(self, text: str) -> str:
        """Remove any thinking/reasoning tags that might leak into output."""
        import re
        # Remove <think>...</think> blocks
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # Remove <|channel|>thought ... <channel|> blocks
        text = re.sub(r'<\|channel\|>thought.*?<channel\|>', '', text, flags=re.DOTALL)
        return text.strip()

    def _save_to_file(self, text: str) -> str:
        """Save corrected text to a download file."""
        try:
            output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
            os.makedirs(output_dir, exist_ok=True)
            filename = f"relationship_corrected_{int(time.time())}.txt"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"Saved corrected text to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save corrected text: {e}")
            return ""
