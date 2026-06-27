"""
Translation-focused LLM Client.
Lightweight wrapper around llama.cpp OpenAI-compatible API,
optimized for long-form novel translation (text-only, no JSON parsing).
Based on deepscribe/client.py pattern.
"""

import json
import logging
import os
import time
import requests
from typing import Optional, Any

logger = logging.getLogger("NovelTranslator.LLMClient")

DEFAULT_API_URL = "http://127.0.0.1:8081/v1/chat/completions"
DEFAULT_API_KEY = "man-to-man-key-4501"


def _load_settings() -> dict:
    """Load settings from the project root settings.json."""
    try:
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        path = os.path.join(base, "settings.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


class TranslationClient:
    """
    LLM API client specialized for novel translation.
    Key differences from deepscribe/client.py:
      - Returns raw text (no JSON parsing)
      - Higher timeout (novels produce long outputs)
      - Simplified interface for translation use case
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 600.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        settings = _load_settings()
        self.api_url = api_url or settings.get("api_url", DEFAULT_API_URL)
        self.api_key = api_key or settings.get("api_key", DEFAULT_API_KEY)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        logger.info(f"TranslationClient initialized: {self.api_url}")

    def _call_api_standard(
        self, messages: list[dict[str, Any]], temperature: float,
        frequency_penalty: float = 0.05, presence_penalty: float = 0.05
    ) -> Optional[str]:
        """Standard (non-streaming) API call with retries."""
        payload = {
            "model": "local-model",
            "messages": messages,
            "temperature": temperature,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        delay = 2.0
        attempt = 1
        max_attempts = self.max_retries

        while attempt <= max_attempts:
            try:
                logger.info(f"[Standard] API attempt {attempt}/{max_attempts}...")
                resp = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                
                # Check for 503 (Service Unavailable / Model is loading)
                if resp.status_code == 503:
                    if max_attempts < 10:
                        logger.info("[Standard] Server returned 503 (Model is loading). Increasing max retries to 10 to wait for model load.")
                        max_attempts = 10
                    logger.warning(f"[Standard] Server returned 503 (Model is loading/Service Unavailable). Attempt {attempt}/{max_attempts}. Waiting 6 seconds before retry...")
                    if attempt < max_attempts:
                        time.sleep(6.0)
                        attempt += 1
                        continue
                    else:
                        return None

                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    logger.error(f"Empty choices: {data}")
                    return None
                msg = choices[0].get("message", {})
                content = msg.get("content")
                if content:
                    return content
                # Fallback: thinking models (Gemma 4) put output in reasoning_content
                reasoning = msg.get("reasoning_content", "")
                if reasoning:
                    logger.info(f"[Standard] Using reasoning_content fallback ({len(reasoning)} chars)")
                    return reasoning
                logger.error("Empty content in standard response.")
                return None
            except requests.exceptions.Timeout:
                logger.error(f"Timeout ({self.timeout}s) on attempt {attempt}")
            except requests.exceptions.RequestException as e:
                # If we got a 503 inside the exception response
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 503:
                    if max_attempts < 10:
                        logger.info("[Standard] Server returned 503 (Model is loading). Increasing max retries to 10 to wait for model load.")
                        max_attempts = 10
                    logger.warning(f"[Standard] Server returned 503. Attempt {attempt}/{max_attempts}. Waiting 6s...")
                    if attempt < max_attempts:
                        time.sleep(6.0)
                        attempt += 1
                        continue
                    else:
                        return None
                logger.error(f"Network error on attempt {attempt}: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error on attempt {attempt}: {e}")

            if attempt < max_attempts:
                logger.info(f"Retrying in {delay}s...")
                time.sleep(delay)
                delay *= self.backoff_factor
            attempt += 1

        logger.critical("All standard API retry attempts failed.")
        return None

    def _call_api_stream(
        self, messages: list[dict[str, Any]], temperature: float,
        frequency_penalty: float = 0.05, presence_penalty: float = 0.05,
        on_token_callback: Any = None
    ) -> Optional[str]:
        """Streaming API call — single attempt, no retries (fallback handles failures)."""
        payload = {
            "model": "local-model",
            "messages": messages,
            "temperature": temperature,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "stream": True,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            logger.info("[Stream] Attempting streaming request...")
            resp = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                stream=True,
            )
            resp.raise_for_status()

            content_tokens = []
            reasoning_tokens = []
            raw_lines_debug = []

            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8", errors="replace").strip()
                if len(raw_lines_debug) < 5:
                    raw_lines_debug.append(line_str)

                # SSE format: "data: {...}" or "data:{...}"
                if line_str.startswith("data:"):
                    data_content = line_str[5:].strip()
                    if data_content == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_content)
                        delta = chunk_data.get("choices", [{}])[0].get("delta", {})

                        # Actual content (priority)
                        text_token = delta.get("content") or ""
                        if text_token:
                            content_tokens.append(text_token)
                            on_token_callback(text_token, False)

                        # Thinking model reasoning_content
                        reasoning_token = delta.get("reasoning_content") or ""
                        if reasoning_token:
                            reasoning_tokens.append(reasoning_token)
                            on_token_callback(reasoning_token, True)

                    except json.JSONDecodeError:
                        continue

            # Prefer content; fallback to reasoning_content
            content = "".join(content_tokens)
            if content:
                logger.info(f"[Stream] Success via content — {len(content)} chars")
                return content

            reasoning = "".join(reasoning_tokens)
            if reasoning:
                logger.info(f"[Stream] Success via reasoning_content fallback — {len(reasoning)} chars")
                return reasoning

            # Stream returned nothing — log first few raw lines for debugging
            logger.warning(
                f"[Stream] Empty result after parsing {len(raw_lines_debug)} lines. "
                f"First 3 raw lines: {raw_lines_debug[:3]}"
            )
            return None

        except Exception as e:
            logger.warning(f"[Stream] Failed: {e}")
            return None

    def _call_api(
        self, messages: list[dict[str, Any]], temperature: float,
        frequency_penalty: float = 0.05, presence_penalty: float = 0.05,
        on_token_callback: Optional[Any] = None
    ) -> Optional[str]:
        """
        Main API dispatcher.
        If a streaming callback is provided:
          1) Try streaming first for real-time output.
          2) If streaming yields empty, auto-fallback to standard request.
        Otherwise, use standard request directly.
        """
        if on_token_callback:
            # Try streaming
            result = self._call_api_stream(messages, temperature, frequency_penalty, presence_penalty, on_token_callback)
            if result:
                return result

            # Fallback to standard
            logger.warning("[Fallback] Streaming returned empty — retrying with standard request...")
            result = self._call_api_standard(messages, temperature, frequency_penalty, presence_penalty)
            if result:
                # Push full text to callback so UI still updates
                on_token_callback(result, False)
            return result
        else:
            return self._call_api_standard(messages, temperature, frequency_penalty, presence_penalty)

    def translate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        frequency_penalty: float = 0.05,
        presence_penalty: float = 0.05,
        on_token_callback: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Send a translation request and return raw text response.
        Supports streaming to the provided callback function.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call_api(
            messages,
            temperature,
            frequency_penalty,
            presence_penalty,
            on_token_callback
        )

    def test_connection(self) -> tuple[bool, str]:
        """Test if the LLM server is reachable."""
        try:
            resp = requests.get(
                self.api_url.replace("/v1/chat/completions", "/v1/models"),
                timeout=5.0,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            if resp.status_code == 200:
                return True, "서버 연결 성공 ✅"
            return False, f"서버 응답 오류: HTTP {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "서버에 연결할 수 없습니다. llama.cpp 서버가 실행 중인지 확인하세요."
        except Exception as e:
            return False, f"연결 테스트 실패: {e}"
