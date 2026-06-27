"""
Smart Text Chunker for Novel Translation.
Splits large text into LLM-digestible chunks preserving narrative coherence.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger("NovelTranslator.Chunker")

SENTENCE_ENDINGS = {
    "ja": re.compile(r'(?<=[。！？」』）\n])\s*'),
    "zh": re.compile(r'(?<=[。！？」』）\n])\s*'),
    "ko": re.compile(r'(?<=[.!?」』）\n])\s*'),
    "en": re.compile(r'(?<=[.!?"\n])\s+'),
}
PARAGRAPH_SEP = re.compile(r'\n\s*\n')


@dataclass
class TextChunk:
    index: int
    text: str
    start_char: int
    end_char: int
    estimated_tokens: int
    paragraph_complete: bool


class SmartChunker:
    TOKEN_RATIOS = {"ja": 1.5, "zh": 1.5, "ko": 1.8, "en": 4.0, "default": 2.0}
    PROMPT_OVERHEAD_TOKENS = 2500  # system prompt + user prompt template overhead

    def __init__(self, context_size: int = 16384, source_lang: str = "ja",
                 overlap_chars: int = 200) -> None:
        self.context_size = context_size
        self.source_lang = source_lang
        self.overlap_chars = overlap_chars
        available = context_size - self.PROMPT_OVERHEAD_TOKENS
        # Use 1/3 of context for input, but cap it at 1000 tokens to ensure the LLM
        # can generate both thinking and complete translation without hitting output token limits.
        self.max_input_tokens = min(max(available // 3, 800), 1000)
        self.chars_per_token = self.TOKEN_RATIOS.get(source_lang, self.TOKEN_RATIOS["default"])
        self.max_chars = int(self.max_input_tokens * self.chars_per_token)
        logger.info(f"SmartChunker: ctx={context_size}, lang={source_lang}, "
                     f"max_tokens={self.max_input_tokens}, max_chars≈{self.max_chars}")

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        cjk = sum(1 for ch in text if self._is_cjk(ch))
        latin = len(text) - cjk
        ratio = self.TOKEN_RATIOS.get(self.source_lang, 2.0)
        return max(int(cjk / ratio + latin / 4.0), 1)

    @staticmethod
    def _is_cjk(char: str) -> bool:
        cp = ord(char)
        return ((0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or
                (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF) or
                (0xAC00 <= cp <= 0xD7AF) or (0x1100 <= cp <= 0x11FF) or
                (0xFF00 <= cp <= 0xFFEF) or (0x3000 <= cp <= 0x303F))

    def _get_sentence_splitter(self) -> re.Pattern:
        return SENTENCE_ENDINGS.get(self.source_lang, SENTENCE_ENDINGS["ja"])

    def _split_paragraphs(self, text: str) -> list[str]:
        return [p.strip() for p in PARAGRAPH_SEP.split(text) if p.strip()]

    def _split_sentences(self, text: str) -> list[str]:
        return [s.strip(" \t\r\u3000") for s in self._get_sentence_splitter().split(text) if s.strip(" \t\r\u3000")]

    def _force_split(self, text: str) -> list[str]:
        chunks = []
        while text:
            if len(text) <= self.max_chars:
                chunks.append(text)
                break
            sp = self.max_chars
            search_start = int(self.max_chars * 0.8)
            region = text[search_start:sp]
            best = None
            for pat in [r'[。！？.!?]\s*', r'[、，,;；]\s*', r'\s+']:
                matches = list(re.finditer(pat, region))
                if matches:
                    best = search_start + matches[-1].end()
                    break
            if best is None:
                best = self.max_chars
            chunks.append(text[:best].strip())
            text = text[best:].strip()
        return chunks

    def chunk_text(self, text: str) -> list[TextChunk]:
        if not text or not text.strip():
            return []
        text = text.strip()
        paragraphs = self._split_paragraphs(text)
        if not paragraphs:
            return []

        chunks: list[TextChunk] = []
        parts: list[str] = []
        tokens = 0
        start = 0
        idx = 0

        def flush(paragraph_complete: bool):
            nonlocal parts, tokens, start, idx
            if not parts:
                return
            ct = "\n\n".join(parts)
            end = start + len(ct)
            chunks.append(TextChunk(idx, ct, start, end, tokens, paragraph_complete))
            idx += 1
            start = end
            parts = []
            tokens = 0

        for para in paragraphs:
            pt = self.estimate_tokens(para)

            if pt > self.max_input_tokens:
                flush(True)
                sents = self._split_sentences(para)
                s_parts: list[str] = []
                s_tok = 0
                for sent in sents:
                    st = self.estimate_tokens(sent)
                    if st > self.max_input_tokens:
                        if s_parts:
                            ct = "".join(s_parts)
                            end = start + len(ct)
                            chunks.append(TextChunk(idx, ct, start, end, s_tok, False))
                            idx += 1
                            start = end
                            s_parts, s_tok = [], 0
                        for fp in self._force_split(sent):
                            ft = self.estimate_tokens(fp)
                            end = start + len(fp)
                            chunks.append(TextChunk(idx, fp, start, end, ft, False))
                            idx += 1
                            start = end
                        continue
                    if s_tok + st > self.max_input_tokens and s_parts:
                        ct = "".join(s_parts)
                        end = start + len(ct)
                        chunks.append(TextChunk(idx, ct, start, end, s_tok, False))
                        idx += 1
                        start = end
                        s_parts, s_tok = [], 0
                    s_parts.append(sent)
                    s_tok += st
                if s_parts:
                    ct = "".join(s_parts)
                    end = start + len(ct)
                    chunks.append(TextChunk(idx, ct, start, end, s_tok, True))
                    idx += 1
                    start = end
                continue

            if tokens + pt > self.max_input_tokens and parts:
                flush(True)
            parts.append(para)
            tokens += pt

        flush(True)
        logger.info(f"Chunked into {len(chunks)} chunks, total chars={len(text)}")
        return chunks

    def get_overlap_context(self, previous_chunk: TextChunk) -> str:
        text = previous_chunk.text
        if len(text) <= self.overlap_chars:
            return text
        tail = text[-self.overlap_chars:]
        sents = self._split_sentences(tail)
        if sents and len(sents) > 1:
            return sents[-1] if len(sents[-1]) > 50 else "".join(sents[-2:])
        return tail
