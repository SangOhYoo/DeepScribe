import os
import re
import sys
import argparse
import logging
from typing import Optional

# Set up logging format before importing other modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DeepScribe.Main")

from .config import API_URL, API_TIMEOUT
from .client import LlamaAPIClient
from .pipeline import MangaNovelizerPipeline


def parse_cut_number(filename: str) -> Optional[int]:
    """
    Extracts the first numeric sequence from a filename to use as the cut number.
    e.g., '003_cut.jpg' -> 3, 'cut12.png' -> 12, 'manga.png' -> None.
    """
    match = re.search(r"\d+", filename)
    if match:
        return int(match.group(0))
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DeepScribe: Japanese Manga to Korean Novel + SD Prompt Extraction Pipeline"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="D:\\DeepScribe\\inputs",
        help="Directory containing manga image cuts (PNG, JPG, JPEG, WEBP)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="D:\\DeepScribe\\outputs",
        help="Directory to save the processed JSON outputs"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=API_URL,
        help=f"llama.cpp API completions endpoint (default: {API_URL})"
    )
    parser.add_argument(
        "--user-comment",
        type=str,
        default="",
        help="Additional global instructions/comment for the adaptation"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug-level logging"
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger("DeepScribe").setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    logger.info("Starting DeepScribe pipeline...")
    logger.info(f"API Endpoint: {args.api_url}")
    logger.info(f"Input Directory: {args.input_dir}")
    logger.info(f"Output Directory: {args.output_dir}")

    # Ensure input directory exists
    if not os.path.exists(args.input_dir):
        logger.warning(f"Input directory '{args.input_dir}' does not exist. Creating it.")
        os.makedirs(args.input_dir, exist_ok=True)
        logger.info("Please place manga images in the input directory and restart.")
        return

    # Initialize components
    client = LlamaAPIClient(api_url=args.api_url, timeout=API_TIMEOUT)
    pipeline = MangaNovelizerPipeline(client=client, output_dir=args.output_dir)
    
    last_completed = pipeline.last_completed_cut

    # Supported image extensions
    valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".wrbp")

    # Scan and map image files to cut numbers
    image_tasks: list[tuple[int, str]] = []
    
    for entry in os.scandir(args.input_dir):
        if entry.is_file() and entry.name.lower().endswith(valid_extensions):
            cut_num = parse_cut_number(entry.name)
            if cut_num is not None:
                image_tasks.append((cut_num, entry.path))
            else:
                logger.warning(f"Skipping file '{entry.name}' as no cut number could be extracted from its filename.")

    if not image_tasks:
        logger.warning(f"No valid image files found in '{args.input_dir}'.")
        return

    # Sort tasks sequentially by cut number
    image_tasks.sort(key=lambda x: x[0])
    
    logger.info(f"Found {len(image_tasks)} total image cuts in the input directory.")

    # Filter tasks to resume processing
    pending_tasks = [task for task in image_tasks if task[0] > last_completed]
    skipped_count = len(image_tasks) - len(pending_tasks)

    if skipped_count > 0:
        logger.info(f"Resuming task. Skipped {skipped_count} already processed cuts.")

    if not pending_tasks:
        logger.info("All found manga cuts have already been processed.")
        return

    logger.info(f"Processing {len(pending_tasks)} pending cuts...")

    # Process remaining cuts sequentially
    for cut_num, image_path in pending_tasks:
        logger.info(f"Processing Cut {cut_num} (File: {os.path.basename(image_path)})")
        
        result = pipeline.process_cut(
            image_path=image_path,
            cut_number=cut_num,
            user_comment=args.user_comment
        )
        
        if result is None:
            logger.error(
                f"Pipeline execution halted at Cut {cut_num} due to critical processing errors. "
                "Please check llama.cpp server logs and retry."
            )
            sys.exit(1)

    logger.info("All pending cuts have been successfully processed!")


if __name__ == "__main__":
    main()
