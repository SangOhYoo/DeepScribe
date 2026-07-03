"""
Translation Orchestrator.
Coordinates chunking, LLM translation, progress reporting,
and post-processing into a single pipeline.
Runs translation in a background thread to keep UI responsive.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

import chardet

from .chunker import SmartChunker, TextChunk
from .glossary import GlossaryManager
from .llm_client import TranslationClient
from .postprocessor import PostProcessor
from ..prompts.templates_new import get_system_prompt, get_user_prompt
from .onomatopoeia import OnomatopoeiaExtractor
from .onomatopoeia_db import OnomatopoeiaDB
from .onomatopoeia_worker import OnomatopoeiaWorker

logger = logging.getLogger("NovelTranslator.Translator")


class TranslationStatus(Enum):
    IDLE = "idle"
    READING = "reading"
    CHUNKING = "chunking"
    TRANSLATING = "translating"
    POSTPROCESSING = "postprocessing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class TranslationProgress:
    status: TranslationStatus = TranslationStatus.IDLE
    current_chunk: int = 0
    total_chunks: int = 0
    message: str = ""
    original_text: str = ""
    translated_text: str = ""
    reasoning_text: str = ""    # model thinking process (separate from translation)
    error: str = ""
    download_path: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @property
    def progress_ratio(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.current_chunk / self.total_chunks


def detect_encoding(file_path: str) -> str:
    """Detect file encoding using chardet with fallback chain."""
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        result = chardet.detect(raw)
        encoding = result.get("encoding", "utf-8")
        confidence = result.get("confidence", 0)
        logger.info(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")

        # Normalize common encoding names
        enc_map = {
            "euc-kr": "euc-kr",
            "cp949": "cp949",
            "iso-8859-1": "utf-8",  # Often misdetected
            "ascii": "utf-8",
            "shift_jis": "shift_jis",
            "euc-jp": "euc-jp",
            "gb2312": "gb2312",
            "gbk": "gbk",
        }

        normalized = enc_map.get(encoding.lower(), encoding) if encoding else "utf-8"

        # Verify by attempting decode
        try:
            raw.decode(normalized)
            return normalized
        except (UnicodeDecodeError, LookupError):
            pass

        # Fallback chain
        for enc in ["utf-8", "utf-8-sig", "cp949", "shift_jis", "euc-kr", "euc-jp"]:
            try:
                raw.decode(enc)
                logger.info(f"Fallback encoding: {enc}")
                return enc
            except (UnicodeDecodeError, LookupError):
                continue

        return "utf-8"

    except Exception as e:
        logger.error(f"Encoding detection failed: {e}")
        return "utf-8"


def normalize_input_text(text: str) -> str:
    """Normalize input text to ensure consistent double newlines between paragraphs."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip(" \t\u3000") for line in text.split("\n")]
    non_empty_lines = [line for line in lines if line]
    return "\n\n".join(non_empty_lines)


class ThinkingStreamParser:
    """
    Stateful parser that identifies and separates thinking/reasoning blocks
    from the actual translation content in a token stream.
    Supports DeepSeek (<think>) and Gemma 4 (<|channel>thought) formats.
    """
    def __init__(self, on_token_callback, enable_thinking: bool):
        self.on_token_callback = on_token_callback
        self.enable_thinking = enable_thinking
        self.in_thinking = False
        self.buffer = ""
        
        # Tags we search for
        self.start_tags = [
            "<think>", 
            "<|channel>thought\n", 
            "<|channel>thought",
            "<|thought|>",
            "<|thinking|>",
            "<|think|>"
        ]
        self.end_tags = [
            "</think>", 
            "<channel|>",
            "</thought>",
            "</thinking>"
        ]

    def feed(self, token: str):
        self.buffer += token
        
        while self.buffer:
            if not self.in_thinking:
                # We are in content mode. Check if buffer starts a thinking block.
                matched_start = False
                potential_match = False
                matched_tag = ""
                
                for tag in self.start_tags:
                    if self.buffer.startswith(tag):
                        matched_start = True
                        matched_tag = tag
                        break
                    elif tag.startswith(self.buffer):
                        potential_match = True
                
                if matched_start:
                    self.in_thinking = True
                    self.buffer = self.buffer[len(matched_tag):]
                    continue
                elif potential_match:
                    # Wait for more tokens to see if it matches fully
                    break
                else:
                    # Find first '<' character
                    idx = self.buffer.find('<')
                    if idx == -1:
                        # Flush all
                        self._emit(self.buffer, False)
                        self.buffer = ""
                    elif idx > 0:
                        # Flush up to '<'
                        self._emit(self.buffer[:idx], False)
                        self.buffer = self.buffer[idx:]
                    else:
                        # Buffer starts with '<' but does not match and is not potential match
                        self._emit(self.buffer[0], False)
                        self.buffer = self.buffer[1:]
            else:
                # We are in thinking mode. Check if buffer contains an end tag.
                first_idx = -1
                matched_tag = ""
                for tag in self.end_tags:
                    idx = self.buffer.find(tag)
                    if idx != -1:
                        if first_idx == -1 or idx < first_idx:
                            first_idx = idx
                            matched_tag = tag
                
                if first_idx != -1:
                    # Flush thinking content before the end tag
                    thinking_content = self.buffer[:first_idx]
                    if thinking_content:
                        self._emit(thinking_content, True)
                    self.in_thinking = False
                    self.buffer = self.buffer[first_idx + len(matched_tag):]
                    continue
                
                # Check for potential partial end tag at the end of buffer
                potential_match = False
                for tag in self.end_tags:
                    for l in range(1, len(tag)):
                        prefix = tag[:l]
                        if self.buffer.endswith(prefix):
                            potential_match = True
                            break
                    if potential_match:
                        break
                
                if potential_match:
                    # Find the longest partial match length
                    suffix_len = 0
                    for tag in self.end_tags:
                        for l in range(len(tag), 0, -1):
                            prefix = tag[:l]
                            if self.buffer.endswith(prefix):
                                if l > suffix_len:
                                    suffix_len = l
                    
                    flush_len = len(self.buffer) - suffix_len
                    if flush_len > 0:
                        self._emit(self.buffer[:flush_len], True)
                        self.buffer = self.buffer[flush_len:]
                    break
                else:
                    self._emit(self.buffer, True)
                    self.buffer = ""

    def _emit(self, text: str, is_reasoning: bool):
        if is_reasoning:
            if self.enable_thinking:
                self.on_token_callback(text, True)
        else:
            self.on_token_callback(text, False)

    def flush(self):
        if self.buffer:
            self._emit(self.buffer, self.in_thinking)
            self.buffer = ""


class TranslationOrchestrator:
    """
    Main orchestrator that coordinates the entire translation pipeline.
    Designed to run in a background thread with progress callbacks.
    """

    def __init__(self) -> None:
        self.progress = TranslationProgress()
        self.client: Optional[TranslationClient] = None
        self.glossary = GlossaryManager()
        self.postprocessor = PostProcessor()
        self._cancel_flag = threading.Event()
        self._lock = threading.Lock()
        self._translated_chunks: list[str] = []
        self._prev_file_path: str = ""
        self._prev_source_lang: str = ""
        self._prev_target_lang: str = ""
        self._prev_context_size: int = 0
        self._prev_original_text: str = ""
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.onomatopoeia_csv = os.path.join(base_dir, "japanese_erotic_onomatopoeia.csv")
        self.onomatopoeia_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "onomatopoeia.db")
        self.onomatopoeia_extractor = OnomatopoeiaExtractor(self.onomatopoeia_csv)
        self.onomatopoeia_db = OnomatopoeiaDB(self.onomatopoeia_db_path)
        self.onomatopoeia_worker = OnomatopoeiaWorker(self.onomatopoeia_db_path)
        self.onomatopoeia_worker.start()

    def reload_onomatopoeia(self) -> None:
        """Reload the registered onomatopoeia dictionary."""
        self.onomatopoeia_extractor.load_dictionary()

    def cancel(self) -> None:
        """Signal cancellation to the running translation."""
        self._cancel_flag.set()
        logger.info("Translation cancellation requested.")

    def reset(self) -> None:
        """Completely reset the orchestrator's state and resume cache."""
        with self._lock:
            self.progress = TranslationProgress()
            self._translated_chunks = []
            self._prev_file_path = ""
            self._prev_source_lang = ""
            self._prev_target_lang = ""
            self._prev_context_size = 0
            self._prev_original_text = ""
            self._cancel_flag.clear()
        logger.info("Translation orchestrator state reset.")

    def _is_cancelled(self) -> bool:
        return self._cancel_flag.is_set()

    def _update_progress(
        self, status: TranslationStatus, message: str = "",
        current_chunk: int = -1, translated_so_far: str = "",
        reasoning_so_far: str = ""
    ) -> None:
        with self._lock:
            self.progress.status = status
            if message:
                self.progress.message = message
            if current_chunk >= 0:
                self.progress.current_chunk = current_chunk
            if translated_so_far:
                self.progress.translated_text = translated_so_far
            if reasoning_so_far:
                self.progress.reasoning_text = reasoning_so_far

    def get_progress(self) -> TranslationProgress:
        with self._lock:
            # Return a shallow copy
            return TranslationProgress(
                status=self.progress.status,
                current_chunk=self.progress.current_chunk,
                total_chunks=self.progress.total_chunks,
                message=self.progress.message,
                original_text=self.progress.original_text,
                translated_text=self.progress.translated_text,
                reasoning_text=self.progress.reasoning_text,
                error=self.progress.error,
                download_path=self.progress.download_path,
                start_time=self.progress.start_time,
                end_time=self.progress.end_time,
            )

    def extract_and_queue_onomatopoeia(self, text: str) -> int:
        """
        Scan the text, extract unregistered onomatopoeia candidates from DIALOGUE blocks only,
        filter for groan/moan/sigh sounds, and queue them in SQLite.
        Returns the number of unique candidates added.
        """
        if not text:
            return 0

        # 1. Extract dialogue blocks (text inside hook brackets 「...」 or 『...』)
        import re
        dialogue_pattern = re.compile(r'「(.*?)」|『(.*?)』', re.DOTALL)
        dialogues = []
        for match in dialogue_pattern.finditer(text):
            content = next((g for g in match.groups() if g is not None), "")
            if content.strip():
                dialogues.append(content)
        
        dialogue_text = "\n".join(dialogues)
        if not dialogue_text:
            return 0

        # 2. Extract unregistered candidates from the dialogue text
        candidates = self.onomatopoeia_extractor.extract_unregistered(dialogue_text)
        if not candidates:
            return 0

        # Helper to check if a word is a moan, groan, or sigh
        def is_groan_sigh_moan(word: str) -> bool:
            w = word.strip()
            if not w:
                return False
            # Strip trailing particles if present
            if w.endswith(("と", "ト")):
                w = w[:-1]
            if len(w) < 2 or len(w) > 5:
                return False
            
            # Character set for moan/sigh sounds (Japanese voices)
            voice_set = set("あいうえおはひふへほんっーァィゥェォハヒフヘホアンッぁぃぅぇぉゃゅょャュョくぐクグむムふフしシ")
            if all(c in voice_set for c in w):
                return True
                
            has_small_or_long = any(c in "ぁぃぅぇぉっッーァィゥェォゃゅょャュョ" for c in w)
            starts_with_voice = w[0] in "あいうえおはひふへほんアアイウエオハヒフヘホアン"
            if has_small_or_long and starts_with_voice:
                return True
                
            return False

        # 3. Filter candidates for groans/sighs/moans
        filtered_candidates = [c for c in candidates if is_groan_sigh_moan(c)]
        if not filtered_candidates:
            return 0

        # 4. Split text into lines to find contexts for the candidates
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        # 5. For each candidate, find a context line containing it
        for word in filtered_candidates:
            context_line = ""
            for line in lines:
                if word in line:
                    # Prefer dialogue lines as context
                    if "「" in line or "『" in line:
                        context_line = line
                        break
                    elif not context_line:
                        context_line = line
            
            # Queue to DB (INSERT OR IGNORE handles duplicates)
            self.onomatopoeia_db.add_to_queue(word, (context_line or word)[:250])

        return len(filtered_candidates)

    def auto_register_character_names(self, text: str, glossary_path: str) -> None:
        """
        Analyze the first ~15,000 characters of the novel to extract character names,
        translate them to Korean, and save them to the glossary files (both default and custom)
        and load them into the current active glossary manager.
        """
        if not text or not self.client:
            return

        # Take the first ~15,000 characters
        sample_len = min(len(text), 15000)
        sample_text = text[:sample_len]

        self._update_progress(
            TranslationStatus.TRANSLATING,
            "인명/고유명사 추출 및 용어 사전 자동 등록 중..."
        )

        system_prompt = (
            "[인명 추출 전문가 / Character Name Extractor]\n"
            "당신은 일본어 소설에서 등장인물의 이름(한자 또는 가타카나 표기)을 추출하고, "
            "이를 표준적이고 자연스러운 한국어 표기로 번역하는 언어 전문가입니다.\n\n"
            "규칙:\n"
            "1. 입력 텍스트에 등장하는 주요 인물들의 이름만 추출하십시오. 지명이나 일반 명사, 의성어는 제외하십시오.\n"
            "2. 출력은 설명 없이 오직 CSV 형식만 지원해야 합니다. 각 라인은 '원본이름,한국어번역' 형식이어야 합니다.\n"
            "3. 마크다운 기호(예: ```csv 등)나 설명글을 절대 포함하지 마십시오.\n"
            "4. 한국어 번역 시 성과 이름을 붙여 쓰거나 널리 쓰이는 표준 일본어 인명 표기법을 따르십시오.\n\n"
            "예시 출력:\n"
            "真弓,마유미\n"
            "克樹,카츠키\n"
            "仁美,히토미"
        )

        user_prompt = (
            f"아래 소설의 앞부분에서 등장인물들의 이름을 추출하고 한국어 번역을 CSV로 출력해 주세요:\n\n"
            f"---\n"
            f"{sample_text}\n"
            f"---"
        )

        try:
            logger.info("Requesting LLM to extract character names...")
            response = self.client.translate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,  # Low temperature for deterministic/factual extraction
            )

            if not response:
                logger.warning("LLM returned empty response for character name extraction.")
                return

            logger.info(f"LLM character name extraction response:\n{response}")

            import json
            # Parse CSV response
            new_entries = []
            for line in response.split("\n"):
                line = line.strip()
                if not line or "," not in line:
                    continue
                parts = line.split(",", 1)
                source = parts[0].strip()
                target = parts[1].strip()

                # Clean up any residual markdown or spaces
                source = source.replace("`", "").replace('"', "").replace("'", "")
                target = target.replace("`", "").replace('"', "").replace("'", "")

                # Basic validation: source should be Japanese name (contains Kanji/Kana), target should be Korean (Hangul)
                if not source or not target:
                    continue
                # Skip header if LLM outputted one
                if source.lower() in ("source", "original", "원본이름", "일본어") or target.lower() in ("target", "translation", "한국어번역", "한국어"):
                    continue

                new_entries.append((source, target))

            if not new_entries:
                logger.info("No new character names extracted.")
                return

            logger.info(f"Extracted {len(new_entries)} candidate names: {new_entries}")

            # Register entries
            registered_count = 0
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            default_glossary = os.path.join(base_dir, "word_Jp2Kr.csv")

            # Load existing terms in the CSVs first to avoid duplicates
            existing_terms = set()
            
            # Read existing default glossary to avoid duplicates
            if os.path.exists(default_glossary):
                try:
                    with open(default_glossary, "r", encoding="utf-8") as f:
                        for row in f:
                            row = row.strip()
                            if row and "," in row:
                                parts = row.split(",", 1)
                                existing_terms.add(parts[0].strip())
                except Exception as e:
                    logger.error(f"Failed to read default glossary: {e}")

            # Let's save new entries
            entries_to_append = []
            for src, tgt in new_entries:
                # Only add if not already in the glossary manager and not already in the file
                if src not in self.glossary._source_index and src not in existing_terms:
                    self.glossary.add_entry(src, tgt, "character")
                    entries_to_append.append((src, tgt))
                    registered_count += 1

            if entries_to_append:
                # Append to default glossary file
                try:
                    # Check if file ends with newline
                    needs_newline = False
                    if os.path.exists(default_glossary) and os.path.getsize(default_glossary) > 0:
                        with open(default_glossary, "rb") as f:
                            f.seek(-1, 2)
                            last_char = f.read(1)
                            needs_newline = (last_char != b'\n' and last_char != b'\r')

                    with open(default_glossary, "a", encoding="utf-8") as f:
                        if needs_newline:
                            f.write("\n")
                        for src, tgt in entries_to_append:
                            f.write(f"{src},{tgt}\n")
                    logger.info(f"Appended {len(entries_to_append)} names to default glossary: {default_glossary}")
                except Exception as e:
                    logger.error(f"Failed to append to default glossary: {e}")

                # If custom glossary path exists and is different, append to it as well
                if glossary_path and os.path.exists(glossary_path) and os.path.abspath(glossary_path) != os.path.abspath(default_glossary):
                    try:
                        if glossary_path.lower().endswith(".json"):
                            # Handle JSON custom glossary
                            with open(glossary_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            
                            is_list = isinstance(data, list)
                            entries_list = data if is_list else data.get("entries", [])
                            
                            custom_existing = {item.get("source", "").strip() for item in entries_list if isinstance(item, dict)}
                            
                            added = False
                            for src, tgt in entries_to_append:
                                if src not in custom_existing:
                                    new_entry = {"source": src, "target": tgt, "category": "character"}
                                    entries_list.append(new_entry)
                                    added = True
                                    
                            if added:
                                if not is_list:
                                    data["entries"] = entries_list
                                with open(glossary_path, "w", encoding="utf-8") as f:
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                                logger.info(f"Appended {len(entries_to_append)} names to custom JSON glossary: {glossary_path}")
                        else:
                            # Handle CSV custom glossary
                            custom_existing = set()
                            with open(glossary_path, "r", encoding="utf-8") as f:
                                for row in f:
                                    row = row.strip()
                                    if row and "," in row:
                                        parts = row.split(",", 1)
                                        custom_existing.add(parts[0].strip())

                            custom_append = [(src, tgt) for src, tgt in entries_to_append if src not in custom_existing]
                            if custom_append:
                                needs_newline = False
                                with open(glossary_path, "rb") as f:
                                    f.seek(-1, 2)
                                    last_char = f.read(1)
                                    needs_newline = (last_char != b'\n' and last_char != b'\r')

                                with open(glossary_path, "a", encoding="utf-8") as f:
                                    if needs_newline:
                                        f.write("\n")
                                    for src, tgt in custom_append:
                                        f.write(f"{src},{tgt}\n")
                                logger.info(f"Appended {len(custom_append)} names to custom CSV glossary: {glossary_path}")
                    except Exception as e:
                        logger.error(f"Failed to append to custom glossary: {e}")

            logger.info(f"Auto-registered {registered_count} character name entries.")

        except Exception as e:
            logger.error(f"Error during auto-registration of character names: {e}")

    def translate_file(
        self,
        file_path: str,
        source_lang: str = "ja",
        target_lang: str = "ko",
        context_size: int = 16384,
        api_url: str = "",
        api_key: str = "",
        glossary_path: str = "",
        temperature: float = 0.3,
        enable_thinking: bool = False,
        frequency_penalty: float = 0.05,
        presence_penalty: float = 0.05,
    ) -> str:
        """
        Execute the full translation pipeline synchronously.
        Call this from a background thread.

        Returns the translated text or empty string on failure.
        """
        self._cancel_flag.clear()
        self.onomatopoeia_worker.pause()  # Pause background worker to give translation 100% priority

        try:
            # --- Phase 1: Read file ---
            self._update_progress(TranslationStatus.READING, "파일 읽는 중...")
            encoding = detect_encoding(file_path)
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    original_text = f.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    original_text = f.read()

            original_text = normalize_input_text(original_text)

            if not original_text.strip():
                self._update_progress(TranslationStatus.ERROR, error_msg="빈 파일입니다.")
                self.progress.error = "빈 파일입니다."
                return ""

            # Check if we can resume from previous progress
            can_resume = (
                bool(self._translated_chunks)
                and self._prev_file_path == file_path
                and self._prev_source_lang == source_lang
                and self._prev_target_lang == target_lang
                and self._prev_context_size == context_size
                and self._prev_original_text == original_text
            )

            # Store current run settings for future resume checks
            self._prev_file_path = file_path
            self._prev_source_lang = source_lang
            self._prev_target_lang = target_lang
            self._prev_context_size = context_size
            self._prev_original_text = original_text

            if not can_resume:
                self._translated_chunks = []
                self.progress = TranslationProgress()
                self.progress.original_text = original_text
                self.progress.start_time = time.time()
            else:
                # Retain existing progress but reset any completed/cancelled state
                self.progress.status = TranslationStatus.READING
                self.progress.original_text = original_text
                self.progress.error = ""
                self.progress.download_path = ""
                if self.progress.start_time is None:
                    self.progress.start_time = time.time()
                self.progress.end_time = None

            logger.info(f"Read file: {len(original_text)} chars, encoding={encoding}")

            if self._is_cancelled():
                self.progress.end_time = time.time()
                self._update_progress(TranslationStatus.CANCELLED, "취소됨")
                return ""

            # --- Phase 2: Load glossary ---
            self.glossary.clear()
            
            # 1. Load default glossary first
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            default_glossary = os.path.join(base_dir, "word_Jp2Kr.csv")
            default_count = 0
            if os.path.exists(default_glossary):
                default_count = self.glossary.load_from_file(default_glossary)
                
            # 2. Load custom glossary if provided and different from default
            custom_count = 0
            if glossary_path and os.path.exists(glossary_path) and os.path.abspath(glossary_path) != os.path.abspath(default_glossary):
                custom_count = self.glossary.load_from_file(glossary_path)
                
            total_count = self.glossary.size
            if total_count > 0:
                msg = f"용어 사전 로드: {total_count}개 항목"
                if custom_count > 0:
                    msg += f" (기본 {default_count}개 + 사용자 {custom_count}개)"
                self._update_progress(
                    TranslationStatus.READING,
                    msg
                )


            # --- Phase 3: Chunk text ---
            self._update_progress(TranslationStatus.CHUNKING, "텍스트 분할 중...")
            chunker = SmartChunker(
                context_size=context_size,
                source_lang=source_lang,
            )
            chunks = chunker.chunk_text(original_text)

            if not chunks:
                self._update_progress(TranslationStatus.ERROR)
                self.progress.error = "텍스트 분할 실패"
                return ""

            self.progress.total_chunks = len(chunks)
            logger.info(f"Text split into {len(chunks)} chunks")

            # --- Phase 4: Initialize LLM client ---
            client_kwargs = {}
            if api_url:
                client_kwargs["api_url"] = api_url
            if api_key:
                client_kwargs["api_key"] = api_key
            self.client = TranslationClient(**client_kwargs)
            self.onomatopoeia_worker.client = self.client

            # --- Phase 4.5: Auto-extract and register character names ---
            if not can_resume and source_lang == "ja" and target_lang == "ko":
                self.auto_register_character_names(original_text, glossary_path)

            # --- Phase 5: Translate chunks ---
            start_chunk_idx = len(self._translated_chunks) if can_resume else 0

            if can_resume:
                logger.info(f"Resuming translation from chunk {start_chunk_idx + 1}")
                self._update_progress(
                    TranslationStatus.TRANSLATING,
                    f"번역 재개 중... (이전 {start_chunk_idx}/{len(chunks)}개 청크 완료)",
                    current_chunk=start_chunk_idx,
                )
            else:
                self._update_progress(
                    TranslationStatus.TRANSLATING,
                    f"번역 시작 (총 {len(chunks)}개 청크)..."
                )

            previous_translation = ""
            if self._translated_chunks:
                previous_translation = self._translated_chunks[-1]

            for i in range(start_chunk_idx, len(chunks)):
                chunk = chunks[i]
                if self._is_cancelled():
                    self._update_progress(TranslationStatus.CANCELLED, "사용자 취소")
                    break

                self._update_progress(
                    TranslationStatus.TRANSLATING,
                    f"청크 {i + 1}/{len(chunks)} 번역 중... "
                    f"(≈{chunk.estimated_tokens} tokens)",
                    current_chunk=i + 1,
                )

                # Build glossary section (only terms found in this chunk)
                glossary_text = self.glossary.format_for_prompt(chunk.text)

                # --- Onomatopoeia Matching & Few-Shot Injection ---
                few_shot_text = ""
                if source_lang == "ja":
                    registered_matches = self.onomatopoeia_extractor.extract_registered(chunk.text)
                    if registered_matches:
                        few_shot_text = self.onomatopoeia_extractor.format_few_shot_prompt(registered_matches)
                        logger.info(f"Matched registered onomatopoeia: {[e['source'] for e in registered_matches]}")
                    
                    unregistered_matches = self.onomatopoeia_extractor.extract_unregistered(chunk.text)
                    if unregistered_matches:
                        logger.info(f"Found unregistered onomatopoeia candidates: {unregistered_matches}")
                        for word in unregistered_matches:
                            # Extract context (line containing word)
                            lines = chunk.text.split("\n")
                            context = ""
                            for line in lines:
                                if word in line:
                                    context = line.strip()
                                    break
                            if not context:
                                context = chunk.text[:200]
                            self.onomatopoeia_db.add_to_queue(word, context)

                # Build context from previous translation
                context_text = ""
                if previous_translation:
                    # Take last ~200 chars of previous translation for continuity
                    context_text = previous_translation[-300:].strip()

                system_prompt = get_system_prompt(
                    source_lang=source_lang,
                    target_lang=target_lang,
                    glossary_text=glossary_text,
                    context_text=context_text,
                    enable_thinking=enable_thinking,
                    few_shot_text=few_shot_text
                )
                user_prompt = get_user_prompt(
                    chunk.text, source_lang, target_lang, i, len(chunks)
                )

                # Call LLM with streaming callback
                current_content_tokens = []
                current_reasoning_tokens = []
                
                # GPU token generation is too fast; throttle UI updates to 0.15s intervals
                last_update_time = [time.time()]
                
                def on_token(token: str, is_reasoning: bool = False):
                    if self._is_cancelled():
                        return
                    
                    if is_reasoning:
                        if not enable_thinking:
                            return
                        # Thinking process
                        current_reasoning_tokens.append(token)
                        
                        now = time.time()
                        if now - last_update_time[0] >= 0.15:
                            reasoning_so_far = "".join(current_reasoning_tokens)
                            self._update_progress(
                                TranslationStatus.TRANSLATING,
                                f"청크 {i + 1}/{len(chunks)} 사고 중... 🧠",
                                current_chunk=i + 1,
                                reasoning_so_far=reasoning_so_far,
                            )
                            last_update_time[0] = now
                    else:
                        # Actual translation content
                        current_content_tokens.append(token)
                        
                        now = time.time()
                        if now - last_update_time[0] >= 0.15:
                            current_translated = "".join(current_content_tokens)
                            all_chunks = self._translated_chunks + [current_translated]
                            merged_so_far = self.postprocessor.merge_chunks(all_chunks)
                            self._update_progress(
                                TranslationStatus.TRANSLATING,
                                f"청크 {i + 1}/{len(chunks)} 번역 중... "
                                f"(≈{chunk.estimated_tokens} tokens)",
                                current_chunk=i + 1,
                                translated_so_far=merged_so_far,
                            )
                            last_update_time[0] = now

                # Wrap the callback using ThinkingStreamParser to filter out any inline reasoning tags (e.g. for Gemma 4)
                parser = ThinkingStreamParser(on_token, enable_thinking=enable_thinking)
                
                def on_token_wrapper(token: str, is_reasoning: bool = False):
                    if is_reasoning:
                        on_token(token, True)
                    else:
                        parser.feed(token)

                translated = self.client.translate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                    on_token_callback=on_token_wrapper,
                )
                parser.flush()

                # Force final update for the chunk to ensure no tokens are missed
                if current_reasoning_tokens:
                    reasoning_so_far = "".join(current_reasoning_tokens)
                    self._update_progress(TranslationStatus.TRANSLATING, reasoning_so_far=reasoning_so_far)
                if current_content_tokens:
                    current_translated = "".join(current_content_tokens)
                    all_chunks = self._translated_chunks + [current_translated]
                    merged_so_far = self.postprocessor.merge_chunks(all_chunks)
                    self._update_progress(TranslationStatus.TRANSLATING, translated_so_far=merged_so_far)
                if translated is None:
                    logger.error(f"Chunk {i + 1} translation failed!")
                    translated = f"[번역 실패: 청크 {i + 1}]\n{chunk.text}"
                else:
                    # Use the filtered clean translation content instead of raw response with thinking tags
                    translated = "".join(current_content_tokens)

                self._translated_chunks.append(translated)
                previous_translation = translated

                # Update progress with merged translation so far
                merged_so_far = self.postprocessor.merge_chunks(
                    self._translated_chunks
                )
                self._update_progress(
                    TranslationStatus.TRANSLATING,
                    f"청크 {i + 1}/{len(chunks)} 완료",
                    current_chunk=i + 1,
                    translated_so_far=merged_so_far,
                )

            if self._is_cancelled():
                self.progress.end_time = time.time()
                return self.postprocessor.merge_chunks(self._translated_chunks)

            # --- Phase 6: Post-process ---
            self._update_progress(TranslationStatus.POSTPROCESSING, "후처리 중...")
            final_text = self.postprocessor.merge_chunks(self._translated_chunks)

            # Save final text to output file for download
            download_path = None
            if final_text:
                try:
                    base = os.path.splitext(os.path.basename(file_path))[0]
                    if base == "_pasted_input":
                        base = "pasted_text"
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
                    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
                    os.makedirs(out_dir, exist_ok=True)
                    download_path = os.path.join(out_dir, f"{base}_translated_{timestamp}.txt")
                    with open(download_path, "w", encoding="utf-8") as f:
                        f.write(final_text)
                    logger.info(f"Saved translated file to {download_path}")
                except Exception as e:
                    logger.error(f"Failed to save download file: {e}")

            self.progress.end_time = time.time()
            self._update_progress(
                TranslationStatus.COMPLETED,
                f"번역 완료! ({len(chunks)}개 청크, {len(final_text):,}자)",
                current_chunk=len(chunks),
                translated_so_far=final_text,
            )
            if download_path:
                with self._lock:
                    self.progress.download_path = download_path

            return final_text

        except Exception as e:
            logger.exception(f"Translation pipeline error: {e}")
            self.progress.end_time = time.time()
            self.progress.status = TranslationStatus.ERROR
            self.progress.error = str(e)
            self.progress.message = f"오류 발생: {e}"
            return ""
        finally:
            self.onomatopoeia_worker.resume()  # Always resume background worker when translation ends
