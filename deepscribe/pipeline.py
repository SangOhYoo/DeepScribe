import os
import re
import json
import base64
import logging
from collections import deque
from typing import Optional, Any

from .config import (
    SYSTEM_PROMPT_STEP1,
    USER_PROMPT_STEP1_TEMPLATE,
    SYSTEM_PROMPT_STEP2,
    USER_PROMPT_STEP2_TEMPLATE,
    TEMP_STEP1,
    TEMP_STEP2,
    MAX_HISTORY_LEN,
)
from .client import LlamaAPIClient

logger = logging.getLogger("DeepScribe.Pipeline")


class MangaNovelizerPipeline:
    """
    Manager class orchestrating Step 1 and Step 2 of the DeepScribe pipeline.
    Handles sliding window history, persistence, and state recovery.
    """
    def __init__(self, client: LlamaAPIClient, output_dir: str) -> None:
        self.client = client
        self.output_dir = output_dir
        self.context_history: deque[str] = deque(maxlen=MAX_HISTORY_LEN)
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Auto-resume state
        self.last_completed_cut = self._resume_context_history()

    def _resume_context_history(self) -> int:
        """
        Scans output_dir for existing JSON files, determines the last completed cut,
        and reconstructs the context history queue using up to the last 3 novel_paragraphs.
        Returns:
            int: The highest completed cut number (0 if none found).
        """
        pattern = re.compile(r"^(\d+)\.json$")
        completed_cuts: list[int] = []

        for filename in os.listdir(self.output_dir):
            match = pattern.match(filename)
            if match:
                completed_cuts.append(int(match.group(1)))

        if not completed_cuts:
            logger.info("No previous progress found. Starting pipeline from scratch.")
            return 0

        completed_cuts.sort()
        last_cut = completed_cuts[-1]
        logger.info(f"Found existing progress. Resuming from last completed cut: {last_cut}")

        # Reconstruct last N contexts in chronological order
        recent_cuts = completed_cuts[-MAX_HISTORY_LEN:]
        self.context_history.clear()
        
        for cut in recent_cuts:
            file_path = os.path.join(self.output_dir, f"{cut}.json")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    novel_paragraph = data.get("novel_paragraph")
                    if novel_paragraph:
                        self.context_history.append(novel_paragraph)
                        logger.debug(f"Recovered context from Cut {cut}: '{novel_paragraph[:30]}...'")
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Failed to load cut {cut}.json for context recovery: {e}")

        logger.info(f"Context history successfully restored. Active window size: {len(self.context_history)}.")
        return last_cut

    def _encode_image_to_base64(self, image_path: str) -> str:
        """
        Encodes an image file to a base64 string.
        Converts the image to standard RGB JPEG to ensure llama.cpp's
        stb_image decoder can read it (resolving failed to decode image bytes).
        """
        try:
            from PIL import Image
            from io import BytesIO
            
            with Image.open(image_path) as img:
                # Handle transparency by pasting onto a white background
                if img.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "RGBA":
                        background.paste(img, mask=img.split()[3])
                    elif img.mode == "LA":
                        background.paste(img, mask=img.split()[1])
                    else:
                        background.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[3])
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                
                # Resize if extremely large to prevent OOM
                max_dim = 2048
                if max(img.size) > max_dim:
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=90, optimize=True)
                return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to read, convert and encode image {image_path}: {e}")
            raise

    def process_cut(
        self,
        image_path: str,
        cut_number: int,
        user_comment: str = ""
    ) -> Optional[dict[str, Any]]:
        """
        Runs the 2-step pipeline for a single manga cut:
        1. Multimodal (Vision+Text) analysis to write novel paragraph & visual descriptions.
        2. Text-only Prompt engineering to generate positive/negative diffusion tags.
        Saves merged results to `{cut_number}.json` in `output_dir`.
        """
        logger.info(f"--- Processing Cut {cut_number} ---")
        
        # --- Step 1: Manga -> Novel JSON ---
        logger.info(f"[Step 1] Translating and novelizing manga image: {os.path.basename(image_path)}")
        try:
            image_base64 = self._encode_image_to_base64(image_path)
        except Exception:
            logger.error(f"Aborting Cut {cut_number} due to image access issues.")
            return None

        # Build context history block
        history_list = list(self.context_history)
        if history_list:
            history_text = "\n".join([f"- {idx+1}: {p}" for idx, p in enumerate(history_list)])
        else:
            history_text = "(None - this is the first cut)"

        user_prompt_step1 = USER_PROMPT_STEP1_TEMPLATE.format(
            cut_number=cut_number,
            history_count=len(history_list),
            context_history=history_text,
            user_comment=user_comment or "No special comments."
        )

        step1_result = self.client.send_chat_completion(
            system_prompt=SYSTEM_PROMPT_STEP1,
            user_prompt=user_prompt_step1,
            image_base64=image_base64,
            image_mime="image/jpeg",
            temperature=TEMP_STEP1,
            parse_json=True
        )

        if not step1_result or not isinstance(step1_result, dict):
            logger.error(f"[Step 1] Failed to obtain valid JSON result for Cut {cut_number}.")
            return None

        # Extract Step 1 data (use defaults to prevent key errors)
        scene_description = step1_result.get("scene_description", "")
        camera_angle = step1_result.get("camera_angle", "eye-level")
        manga_effects = step1_result.get("manga_effects", "none")
        novel_paragraph = step1_result.get("novel_paragraph", "")

        if not novel_paragraph:
            logger.error(f"[Step 1] Missing 'novel_paragraph' in LLM response: {step1_result}")
            return None

        logger.info("[Step 1] Successfully adapted to novel paragraph.")
        logger.info(f"Novel Paragraph: {novel_paragraph}")

        # --- Step 2: Novel JSON -> Image Prompt Tag Extraction (Text Only) ---
        logger.info("[Step 2] Extracting image generation prompts (Text-only)...")
        
        user_prompt_step2 = USER_PROMPT_STEP2_TEMPLATE.format(
            scene_description=scene_description,
            camera_angle=camera_angle,
            manga_effects=manga_effects
        )

        step2_result = self.client.send_chat_completion(
            system_prompt=SYSTEM_PROMPT_STEP2,
            user_prompt=user_prompt_step2,
            image_base64=None,  # Speed up and save VRAM by sending text only
            temperature=TEMP_STEP2,
            parse_json=True
        )

        if not step2_result or not isinstance(step2_result, dict):
            logger.warning(
                f"[Step 2] Failed to obtain valid JSON prompts for Cut {cut_number}. "
                "Defaulting to empty prompts."
            )
            step2_result = {
                "positive_prompt": "",
                "negative_prompt": ""
            }

        logger.info("[Step 2] Successfully extracted diffusion prompts.")
        logger.debug(f"Positive Prompt: {step2_result.get('positive_prompt')}")

        # Combine results
        final_result = {
            "cut_number": cut_number,
            "scene_description": scene_description,
            "camera_angle": camera_angle,
            "manga_effects": manga_effects,
            "novel_paragraph": novel_paragraph,
            "positive_prompt": step2_result.get("positive_prompt", ""),
            "negative_prompt": step2_result.get("negative_prompt", ""),
        }

        # Save to output folder
        output_file = os.path.join(self.output_dir, f"{cut_number}.json")
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(final_result, f, ensure_ascii=False, indent=2)
            logger.info(f"Successfully saved result for Cut {cut_number} to {output_file}.")
        except OSError as e:
            logger.error(f"Failed to write output file {output_file}: {e}")

        # Update sliding window memory queue
        self.context_history.append(novel_paragraph)

        return final_result
