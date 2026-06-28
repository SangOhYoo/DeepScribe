import re
import json
import time
import logging
import requests
from typing import Optional, Any

logger = logging.getLogger("NCSWriter.Client")

def extract_clean_json(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    text_stripped = text.strip()
    try:
        return json.loads(text_stripped)
    except json.JSONDecodeError:
        pass
    
    first_brace = text_stripped.find('{')
    last_brace = text_stripped.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = text_stripped[first_brace:last_brace + 1]
        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError:
            try:
                cleaned = re.sub(r'(?<!\\)\n', '\\n', json_candidate)
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
    return None

def optimize_prompt(text: str) -> str:
    if not text:
        return ""
    
    lines = text.split("\n")
    cleaned_lines = []
    prev_line = None
    for line in lines:
        stripped = line.strip()
        if not stripped and not prev_line:
            continue
        cleaned_lines.append(line)
        prev_line = stripped
        
    text = "\n".join(cleaned_lines).strip()
    return text

class LlamaAPIClient:
    """
    NCS Writer API Client for Llama.cpp Server.
    """
    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8081/v1/chat/completions",
        api_key: str = "man-to-man-key-4501",
        timeout: float = 300.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.last_system_prompt = ""
        self.last_user_prompt = ""

    def _call_api_with_retry(
        self,
        messages: list[dict[str, Any]],
        temperature: float,
        response_format_json: bool = False
    ) -> Optional[str]:
        payload: dict[str, Any] = {
            "model": "local-model",
            "messages": messages,
            "temperature": temperature,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        delay = 2.0

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                response.raise_for_status()
                res_data = response.json()
                choices = res_data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content")
            except Exception as e:
                logger.error(f"API Error on attempt {attempt}: {e}")
            
            if attempt < self.max_retries:
                time.sleep(delay)
                delay *= self.backoff_factor

        return None

    def send_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        parse_json: bool = False
    ) -> Optional[dict[str, Any] | str]:
        opt_sys = optimize_prompt(system_prompt)
        opt_user = optimize_prompt(user_prompt)
        self.last_system_prompt = opt_sys
        self.last_user_prompt = opt_user
        
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": opt_sys},
            {"role": "user", "content": opt_user}
        ]

        raw_response = self._call_api_with_retry(
            messages=messages,
            temperature=temperature,
            response_format_json=parse_json
        )
        
        if not raw_response:
            return None
            
        if not parse_json:
            return raw_response
            
        parsed_data = extract_clean_json(raw_response)
        if parsed_data is not None:
            return parsed_data
            
        return None

    def stream_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7
    ):
        opt_sys = optimize_prompt(system_prompt)
        opt_user = optimize_prompt(user_prompt)
        self.last_system_prompt = opt_sys
        self.last_user_prompt = opt_user
        
        messages = [
            {"role": "system", "content": opt_sys},
            {"role": "user", "content": opt_user}
        ]
        payload = {
            "model": "local-model",
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                stream=True
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    line_str = line.decode('utf-8', errors='replace')
                except Exception:
                    continue
                    
                if not line_str.startswith("data: "):
                    continue
                data_str = line_str[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue
        except Exception as e:
            logger.error(f"Streaming API Error: {e}")
