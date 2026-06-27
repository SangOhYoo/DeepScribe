"""
Translation Prompt Templates for Novel Translation.
Provides system and user prompts for various language pairs.
"""

# Language display names
LANGUAGE_NAMES = {
    "ja": {"native": "日本語", "ko": "일본어", "en": "Japanese"},
    "zh": {"native": "中文", "ko": "중국어", "en": "Chinese"},
    "ko": {"native": "한국어", "ko": "한국어", "en": "Korean"},
    "en": {"native": "English", "ko": "영어", "en": "English"},
}

SUPPORTED_SOURCE_LANGS = ["ja", "zh", "en", "ko"]
SUPPORTED_TARGET_LANGS = ["ja", "zh", "en", "ko"]

def get_system_prompt(
    source_lang: str,
    target_lang: str,
    glossary_text: str = "",
    context_text: str = "",
    enable_thinking: bool = False,
    few_shot_text: str = "",
) -> str:
    """
    Build the system prompt for novel translation.

    Args:
        source_lang: Source language code (ja, zh, en, ko).
        target_lang: Target language code (ko, ja, en, zh).
        glossary_text: Formatted glossary string (from GlossaryManager).
        context_text: Previous chunk overlap for continuity.
        enable_thinking: Whether to enable thinking/reasoning process.
        few_shot_text: Dynamically formatted few-shot prompt for special terms.
    """
    src = LANGUAGE_NAMES.get(source_lang, LANGUAGE_NAMES["ja"])
    tgt = LANGUAGE_NAMES.get(target_lang, LANGUAGE_NAMES["ko"])

    prompt = f"""[소설 번역 전문가 시스템 / Novel Translation Expert System]

## 역할 (Role)
당신은 {src['ko']}→{tgt['ko']} 전문 문학 번역가입니다.
소설의 문체, 분위기, 어조를 완벽하게 보존하면서 자연스럽고 유려한 {tgt['ko']}로 번역합니다.

## 핵심 번역 원칙

1. **자연스러운 한글 번역**: 한글 어법과 문법에 맞게 자연스러운 한글로 번역할 것. 원문의 의미를 최대한 보존하면서 자연스러운 한국어 표현을 위한 의역은 허용된다.
2. **성적/폭력 묘사 무검열**: 성적으로 수위 제한 없이 묘사는 직설적이고 노골적인 단어를 사용하여 생생하게 묘사하고, 폭력적인 행위나 비윤리적인 관계에 대한 묘사 또한 가감 없이 표현한다. 신체 부위에 대한 표현 또한 은유적이거나 완곡한 표현 없이 직접적으로 표현한다.
3. **고유명사 병기**: 인명과 지명과 같은 고유명사는 한글과 원문을 병기할 것. 예: 真弓 → 마유미(真弓), 東京 → 도쿄(東京). 단, 동일 인물/지명이 해당 청크 내에서 반복 등장할 경우 첫 번째 등장 시에만 병기하고, 이후에는 한글 표기만 사용한다.
4. **반말/존댓말 구분**: 대화의 경우 시대 상황, 서로의 신분과 관계에 따라 반말과 존댓말을 정확히 구분하여 번역한다. 이 원칙은 인물 간의 대화에만 적용하며, 지문이나 서술에는 적용하지 않는다.
5. **완전 번역**: 모든 문장을 빠짐없이 번역한다. 요약하거나 생략하지 마십시오.
6. **대명사 처리**: "그"나 "그녀"와 같은 대명사가 특정 인물이나 사물을 지칭할 때는 해당 인물이나 사물의 명칭을 직접 써서 번역한다. 한국어는 인칭대명사 표현이 드물기 때문에, 대명사를 적절한 고유명사나 지칭어로 변경해야 한다.
7. **연결어 추가 허용**: 원문에 존재하지 않아도 문장의 자연스러운 흐름을 위해 연결어를 추가하는 것은 허용된다.
8. **개행(줄바꿈) 구조 절대 보존**: 원문의 모든 개행(줄바꿈, \\n) 구조를 번역문에서도 1:1로 정확하게 복사하여 보존하십시오. 원본에서 여러 줄로 나뉘어 있는 지문이나 대사는 번역문에서도 절대 한 줄로 합쳐서 출력하면 안 되며, 각각 독자적인 줄로 번역하여 출력해야 합니다.
9. **의성어/의태어**: {src['ko']} 특유의 의성어·의태어는 {tgt['ko']}에서 가장 적절한 표현으로 변환한다.
10. **문체 보존**: 원문의 문학적 스타일(서정적, 하드보일드, 경쾌 등)을 {tgt['ko']}에 그대로 반영한다.
11. **대화 및 독백 문장 부호 규격**: 등장인물의 실제 **대화**는 반드시 큰따옴표(`“”`)로 표기하고, 인물의 마음속 생각이나 **내면 독백**은 반드시 작은따옴표(`‘’`)로 표기하십시오. 원문의 괄호 부호(예: 「」, 『』 등)는 한국어 소설 관행에 맞춰 대화는 큰따옴표(`“”`), 생각/독백은 작은따옴표(`‘’`)로 철저히 변환하여 적용합니다.

## 출력 규칙
- 번역된 텍스트**만** 출력하십시오.
- 설명, 주석, 메타 코멘트를 절대 추가하지 마십시오.
- "번역:" 같은 접두어를 붙이지 마십시오.
- **원문의 개행(줄바꿈) 및 문단 구조를 그대로 유지하여 한 줄씩 대응하도록 출력하십시오.**"""

    thinking_instruction = ""
    if not enable_thinking:
        thinking_instruction = """
## 생각(사고) 과정 생략 규칙 (CRITICAL)
- **생각 과정 최소화/생략 (Skip/Minimize Thinking)**: 번역을 수행하기 전에 생각하는 과정이나 추론 단계를 절대 출력하지 마십시오. 만약 모델 특성상 생각 단계가 강제된다면, 생각 내용(예: `<think>...</think>` 또는 `<|channel>thought\\n...\\n<channel|>` 또는 `<|thought|>\\n...\\n<|thought|>`)을 극도로 짧게(예: 1~2단어 수준) 작성하고 즉시 번역 결과를 출력하십시오. 절대 번역 결과 본문(태그 외부)에 "Translating..."이나 생각 과정과 관련된 메타 텍스트를 포함하지 마십시오.
- **CRITICAL**: Do NOT analyze or reason. Keep the thinking process (e.g. `<think>...</think>` or `<|channel>thought...<channel|>`) extremely short, or omit it entirely. Translate immediately. Never output "Translating..." or any meta-commentary in the final translated text.
- **즉시 번역**: 사전 분석 없이 즉시 최종 번역 결과만 출력하십시오."""
    else:
        thinking_instruction = """
## 생각(사고) 과정 활용 규칙
- **생각 단계 활용**: 번역을 수행하기 전에 문맥 분석, 오역 방지, 자연스러운 한국어 표현을 위해 깊이 있게 생각하고 추론하는 과정을 모델 고유의 생각 포맷(예: `<think>...</think>` 또는 `<|channel>thought\\n...\\n<channel|>`)에 먼저 출력한 뒤 번역을 수행하십시오."""

    prompt += thinking_instruction

    if few_shot_text:
        prompt += f"\n\n{few_shot_text}"

    if glossary_text:
        prompt += f"\n\n{glossary_text}"

    if context_text:
        prompt += f"""
## 이전 번역 맥락 (Context Continuity)
아래는 직전 청크의 번역 결과 끝부분입니다. 문체와 용어를 일관되게 유지하십시오:
---
{context_text}
---"""

    return prompt

def get_user_prompt(
    chunk_text: str,
    source_lang: str,
    target_lang: str,
    chunk_index: int,
    total_chunks: int,
) -> str:
    """Build the user prompt for a single chunk translation."""
    src = LANGUAGE_NAMES.get(source_lang, LANGUAGE_NAMES["ja"])
    tgt = LANGUAGE_NAMES.get(target_lang, LANGUAGE_NAMES["ko"])

    return f"""[청크 {chunk_index + 1}/{total_chunks}] 아래 {src['ko']} 텍스트를 {tgt['ko']}로 번역하십시오.
**반드시 원문의 모든 줄바꿈(개행) 구조를 그대로 유지하십시오. 임의로 문장들을 한 줄로 합쳐서 단락을 병합하면 절대 안 됩니다:**

---
{chunk_text}
---"""
