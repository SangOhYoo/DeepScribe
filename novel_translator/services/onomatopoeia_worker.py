import time
import json
import re
import logging
import threading
from typing import Optional
from .llm_client import TranslationClient
from .onomatopoeia_db import OnomatopoeiaDB

logger = logging.getLogger("NovelTranslator.OnomatopoeiaWorker")

WORKER_SYSTEM_PROMPT = """너는 일본어 문학 번역 전문가이자 사전 편집자이다.
원문 문장과 신규 의성어/의태어가 주어지면, 해당 단어의 가장 적절한 한국어 번역(소설 번역 시 자연스럽게 쓸 수 있는 의역 중심)과 단어의 문맥 및 상황 설명(notes), 그리고 해당 단어가 사용된 원문을 포함한 올바른 번역 예시(example_correct) 및 피해야 할 기계적 직역 오답 예시(example_wrong)를 아래 JSON 형식으로 작성해라.

JSON 형식:
{
  "suggested_translation": "한국어 번역어 (예: 질척질척, 챠박챠박)",
  "notes": "상황에 따라 '질척질척', '챠박챠박' 등 젖은 마찰음 계열로 문맥에 맞게 조사(이/가, 을/를)를 붙여 자연스럽게 소설적으로 의역해야 한다. 기계적으로 '쿠츄쿠츄'라고 직역하지 마라.",
  "example_wrong": "방에 쿠츄쿠츄하고 음란한 소리가 울린다.",
  "example_correct": "방 안에 질척이는 음란한 소리가 울려 퍼졌다."
}

반드시 JSON 이외의 다른 설명이나 텍스트를 출력하지 마라.
"""

def parse_llm_json(response: str) -> Optional[dict]:
    """Parse JSON from LLM output robustly, handling markdown blocks and syntax errors."""
    if not response:
        return None
    
    # Try to find json block
    match = re.search(r'\{.*\}', response, re.DOTALL)
    if not match:
        return None
    
    json_str = match.group(0).strip()
    try:
        return json.loads(json_str)
    except Exception:
        # Fallback manual regex extraction for semi-malformed JSON
        keys = ["suggested_translation", "notes", "example_wrong", "example_correct"]
        extracted = {}
        for key in keys:
            pat = re.compile(rf'"{key}"\s*:\s*"([^"]*?)"')
            m = pat.search(response)
            if m:
                extracted[key] = m.group(1)
            else:
                extracted[key] = ""
        
        if extracted.get("suggested_translation"):
            return extracted
    return None


class OnomatopoeiaWorker:
    def __init__(self, db_path: str, client: Optional[TranslationClient] = None):
        self.db = OnomatopoeiaDB(db_path)
        self.client = client or TranslationClient()
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def pause(self):
        """Pause the worker thread."""
        self.pause_event.set()
        logger.info("OnomatopoeiaWorker paused.")

    def resume(self):
        """Resume the worker thread."""
        self.pause_event.clear()
        logger.info("OnomatopoeiaWorker resumed.")

    def start(self):
        """Start worker in a background thread."""
        if self.thread and self.thread.is_alive():
            logger.info("OnomatopoeiaWorker is already running.")
            return
        
        self.stop_event.clear()
        self.pause_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="OnomatopoeiaWorker")
        self.thread.start()
        logger.info("OnomatopoeiaWorker thread started.")

    def stop(self):
        """Stop the background worker."""
        self.stop_event.set()
        self.pause_event.clear()
        if self.thread:
            self.thread.join(timeout=2.0)
            logger.info("OnomatopoeiaWorker thread stopped.")

    def _run_loop(self):
        """Main loop that polls the queue database."""
        while not self.stop_event.is_set():
            try:
                # If paused, wait here without sending any LLM requests
                if self.pause_event.is_set():
                    time.sleep(1.0)
                    continue

                pending_items = self.db.get_pending_extraction()
                if not pending_items:
                    # Sleep and poll again
                    time.sleep(5.0)
                    continue

                for item in pending_items:
                    if self.stop_event.is_set() or self.pause_event.is_set():
                        break

                    word = item["word"]
                    context = item["context"]
                    
                    logger.info(f"Processing queued word '{word}' with LLM...")
                    
                    # Update status to working (pending_llm) so multiple threads/polls don't double process
                    self.db.set_status(word, "pending_llm")

                    user_prompt = f"원문 문장: '{context}'\n신규 단어: '{word}'"
                    
                    try:
                        # Call LLM with low temperature for structured output
                        response = self.client.translate(
                            system_prompt=WORKER_SYSTEM_PROMPT,
                            user_prompt=user_prompt,
                            temperature=0.2
                        )
                        
                        parsed = parse_llm_json(response)
                        if parsed and parsed.get("suggested_translation"):
                            self.db.update_llm_result(
                                word=word,
                                translation=parsed.get("suggested_translation", ""),
                                notes=parsed.get("notes", ""),
                                wrong=parsed.get("example_wrong", ""),
                                correct=parsed.get("example_correct", "")
                            )
                        else:
                            logger.warning(f"Failed to parse LLM response for word '{word}'. Response: {response}")
                            # Revert status back to pending_extraction to retry later, or mark as error?
                            # Let's set it back to pending_extraction so it can retry next round,
                            # but increment a retry counter or just sleep to prevent infinite tight loop.
                            self.db.set_status(word, "pending_extraction")
                            time.sleep(10.0) # Wait a bit on error
                            
                    except Exception as ex:
                        logger.error(f"Error calling LLM for word '{word}': {ex}")
                        self.db.set_status(word, "pending_extraction")
                        time.sleep(10.0) # Wait a bit on error
                        
            except Exception as e:
                logger.error(f"Error in OnomatopoeiaWorker loop: {e}")
                time.sleep(10.0)
