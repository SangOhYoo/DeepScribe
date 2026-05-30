import re
import json
import time
import logging
import requests
from typing import Optional, Any

logger = logging.getLogger("DeepScribe.Client")

def extract_clean_json(text: str) -> Optional[dict[str, Any]]:
    """
    Extracts and parses JSON from a potentially messy text response.
    Handles markdown wrappers (```json ... ```) and leading/trailing filler text.
    """
    if not text:
        return None
    
    text_stripped = text.strip()
    
    # 1. Direct parsing check
    try:
        return json.loads(text_stripped)
    except json.JSONDecodeError:
        pass
    
    # 2. Extract block between first '{' and last '}'
    first_brace = text_stripped.find('{')
    last_brace = text_stripped.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = text_stripped[first_brace:last_brace + 1]
        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError as e:
            logger.error(f"JSON structure found but parsing failed: {e}")
            logger.debug(f"Raw candidate content: {json_candidate}")
            
            # Simple cleaning: replace literal newlines in multi-line strings
            # Often LLMs write: "novel_paragraph": "line 1
            # line 2"
            # We can attempt to replace raw newlines within double quotes, or do a simple replace
            # of carriage returns and unescaped tab characters.
            try:
                # Replace unescaped newlines in JSON strings:
                # Find occurrences of newlines that are not preceded by backslashes
                # Note: this is a heuristic. If it fails, we fall back to returning None.
                cleaned = re.sub(r'(?<!\\)\n', '\\n', json_candidate)
                # Ensure we didn't break JSON structure newlines (e.g. after commas/braces)
                # Actually, structural newlines are fine to keep or remove, json.loads handles both.
                # Let's see if loading works now:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass
    else:
        logger.error("No JSON structure (curly braces) found in the text.")
        logger.debug(f"Raw text: {text_stripped}")
        
    return None


class LlamaAPIClient:
    """
    API client for interacting with llama.cpp server.
    Implements timeout configs, error handling, retries, and JSON parsing.
    """
    def __init__(
        self,
        api_url: str,
        api_key: Optional[str] = None,
        timeout: float = 300.0,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def _call_api_with_retry(
        self,
        messages: list[dict[str, Any]],
        temperature: float,
        response_format_json: bool = False
    ) -> Optional[str]:
        """
        Sends requests to the llama.cpp server with exponential backoff retries.
        """
        payload: dict[str, Any] = {
            "model": "local-model",
            "messages": messages,
            "temperature": temperature,
        }
        if response_format_json:
            # Request JSON output constraint if supported by the server
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        key = self.api_key
        if not key:
            try:
                import os
                import json
                settings_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")
                if os.path.exists(settings_file):
                    with open(settings_file, "r", encoding="utf-8") as f:
                        settings = json.load(f)
                        key = settings.get("api_key")
            except Exception:
                pass
        if not key:
            key = "man-to-man-key-4501"
        if key:
            headers["Authorization"] = f"Bearer {key}"
        delay = 2.0

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Sending API request (Attempt {attempt}/{self.max_retries})...")
                response = requests.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                # Check HTTP error status codes
                response.raise_for_status()
                
                # Parse OpenAI-compliant chat completion output
                res_data = response.json()
                choices = res_data.get("choices", [])
                if not choices:
                    logger.error(f"Invalid API response schema: {res_data}")
                    return None
                    
                content = choices[0].get("message", {}).get("content")
                if content:
                    return content
                else:
                    logger.error("Empty content returned from model choice.")
                    return None
                    
            except requests.exceptions.Timeout as e:
                logger.error(f"API Request Timeout (Timeout={self.timeout}s) on attempt {attempt}: {e}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error on attempt {attempt}: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse API HTTP response as JSON on attempt {attempt}: {e}")

            if attempt < self.max_retries:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= self.backoff_factor

        logger.critical("All API retry attempts failed.")
        return None

    def send_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: Optional[str] = None,
        image_mime: str = "image/jpeg",
        temperature: float = 0.3,
        parse_json: bool = True
    ) -> Optional[dict[str, Any] | str]:
        """
        Builds the standard messages format (supporting multimodal input if image_base64 is present),
        sends the API request, and returns either parsed JSON (if parse_json=True) or raw string response.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        if image_base64:
            # Step 1: Multimodal message structure (OpenAI standard compatible)
            user_content = [
                {
                    "type": "text",
                    "text": user_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_mime};base64,{image_base64}"
                    }
                }
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            # Step 2: Text-only structure
            messages.append({"role": "user", "content": user_prompt})

        # Try parsing JSON up to 2 times by calling the model again if formatting fails
        max_parse_attempts = 2
        for attempt in range(1, max_parse_attempts + 1):
            raw_response = self._call_api_with_retry(
                messages=messages,
                temperature=temperature,
                response_format_json=parse_json
            )
            
            if not raw_response:
                return None
                
            if not parse_json:
                return raw_response
                
            # Attempt to extract and parse JSON from the response
            parsed_data = extract_clean_json(raw_response)
            if parsed_data is not None:
                return parsed_data
                
            logger.warning(
                f"Response content was not valid JSON (Attempt {attempt}/{max_parse_attempts}). "
                "Retrying API generation to fix format..."
            )
            
        logger.error("Failed to obtain valid JSON output after parsing attempts.")
        return None
