import os
import json
import threading
import logging
from flask import Flask, jsonify, request, render_template, send_from_directory
from typing import Any, Optional

from .config import API_URL, API_TIMEOUT
from .client import LlamaAPIClient
from .pipeline import MangaNovelizerPipeline
from .main import parse_cut_number

logger = logging.getLogger("DeepScribe.UI")

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))

# Path to persistent settings file
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")

# Global thread-safe processing state
state_lock = threading.Lock()
is_processing = False
should_stop = False
current_cut: Optional[int] = None
total_cuts = 0
completed_count = 0
status_message = "Idle"


def load_settings() -> dict[str, str]:
    """Loads settings from settings.json or returns default values."""
    defaults = {
        "api_url": API_URL,
        "api_key": "man-to-man-key-4501",
        "input_dir": "D:\\DeepScribe\\inputs",
        "output_dir": "D:\\DeepScribe\\outputs",
        "user_comment": ""
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all keys are present
                for k, v in defaults.items():
                    data.setdefault(k, v)
                return data
        except Exception as e:
            logger.error(f"Error reading settings file: {e}")
    return defaults


def save_settings(data: dict[str, str]) -> None:
    """Saves settings to settings.json."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error writing settings file: {e}")


def run_pipeline_thread(
    input_dir: str,
    output_dir: str,
    api_url: str,
    user_comment: str
) -> None:
    """Background worker running the sequential batch processing loop."""
    global is_processing, should_stop, current_cut, total_cuts, completed_count, status_message
    
    logger.info("Background pipeline thread started.")
    
    # 1. Initialize client and pipeline
    settings = load_settings()
    api_key = settings.get("api_key", "man-to-man-key-4501")
    client = LlamaAPIClient(api_url=api_url, api_key=api_key, timeout=API_TIMEOUT)
    pipeline = MangaNovelizerPipeline(client=client, output_dir=output_dir)
    
    last_completed = pipeline.last_completed_cut
    
    # 2. Scan input images
    valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".wrbp")
    image_tasks = []
    if os.path.exists(input_dir):
        for entry in os.scandir(input_dir):
            if entry.is_file() and entry.name.lower().endswith(valid_extensions):
                cut_num = parse_cut_number(entry.name)
                if cut_num is not None:
                    image_tasks.append((cut_num, entry.path, entry.name))
                    
    image_tasks.sort(key=lambda x: x[0])
    
    pending_tasks = [t for t in image_tasks if t[0] > last_completed]
    
    with state_lock:
        total_cuts = len(image_tasks)
        completed_count = len(image_tasks) - len(pending_tasks)
        is_processing = True
        should_stop = False
        
    if not pending_tasks:
        with state_lock:
            status_message = "All found manga cuts have already been processed."
            is_processing = False
        return

    # 3. Process sequentially
    for cut_num, img_path, img_name in pending_tasks:
        with state_lock:
            if should_stop:
                status_message = "Processing stopped by user."
                break
            current_cut = cut_num
            status_message = f"Processing Cut {cut_num} ({img_name})..."
            
        logger.info(f"UI thread processing Cut {cut_num}")
        result = pipeline.process_cut(
            image_path=img_path,
            cut_number=cut_num,
            user_comment=user_comment
        )
        
        with state_lock:
            if result is None:
                status_message = f"Failed processing Cut {cut_num}. Execution halted."
                break
            completed_count += 1
            
    with state_lock:
        if not should_stop and result is not None:
            status_message = "All pending cuts processed successfully!"
            current_cut = None
        is_processing = False
        
    logger.info("Background pipeline thread finished.")


@app.route('/')
def index():
    """Serves the main SPA index template."""
    return render_template("index.html")


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """Gets or updates pipeline configuration settings."""
    if request.method == 'POST':
        req_data = request.json or {}
        settings = load_settings()
        
        # Update settings safely
        settings["api_url"] = req_data.get("api_url", settings["api_url"])
        settings["api_key"] = req_data.get("api_key", settings["api_key"])
        settings["input_dir"] = req_data.get("input_dir", settings["input_dir"])
        settings["output_dir"] = req_data.get("output_dir", settings["output_dir"])
        settings["user_comment"] = req_data.get("user_comment", settings["user_comment"])
        
        save_settings(settings)
        return jsonify({"status": "success", "settings": settings})
    
    return jsonify(load_settings())


@app.route('/api/cuts', methods=['GET'])
def api_cuts():
    """Lists all cuts in the input directory and their corresponding statuses."""
    settings = load_settings()
    input_dir = settings["input_dir"]
    output_dir = settings["output_dir"]
    
    valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".wrbp")
    cuts_list = []
    
    if os.path.exists(input_dir):
        for entry in os.scandir(input_dir):
            if entry.is_file() and entry.name.lower().endswith(valid_extensions):
                cut_num = parse_cut_number(entry.name)
                if cut_num is not None:
                    # Check if output JSON exists
                    output_file = os.path.join(output_dir, f"{cut_num}.json")
                    status = "completed" if os.path.exists(output_file) else "pending"
                    cuts_list.append({
                        "cut_number": cut_num,
                        "filename": entry.name,
                        "status": status
                    })
                    
    # Sort cuts numerically
    cuts_list.sort(key=lambda x: x["cut_number"])
    return jsonify(cuts_list)


@app.route('/api/process', methods=['POST'])
def api_process():
    """Starts or stops the pipeline processing thread."""
    global is_processing, should_stop
    action = request.json.get("action", "start")
    
    if action == "start":
        with state_lock:
            if is_processing:
                return jsonify({"error": "Pipeline is already running"}), 400
                
        settings = load_settings()
        
        # Start worker thread
        t = threading.Thread(
            target=run_pipeline_thread,
            args=(
                settings["input_dir"],
                settings["output_dir"],
                settings["api_url"],
                settings["user_comment"]
            ),
            daemon=True
        )
        t.start()
        return jsonify({"status": "started"})
        
    elif action == "stop":
        with state_lock:
            if is_processing:
                should_stop = True
                return jsonify({"status": "stopping_requested"})
        return jsonify({"status": "not_running"})
        
    return jsonify({"error": "Invalid action"}), 400


@app.route('/api/status', methods=['GET'])
def api_status():
    """Returns the current pipeline processing state."""
    with state_lock:
        return jsonify({
            "is_processing": is_processing,
            "current_cut": current_cut,
            "total_cuts": total_cuts,
            "completed_count": completed_count,
            "status_message": status_message
        })


@app.route('/api/result/<int:cut_number>', methods=['GET'])
def api_result(cut_number: int):
    """Fetches result data for a specific completed cut."""
    settings = load_settings()
    output_file = os.path.join(settings["output_dir"], f"{cut_number}.json")
    
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                return jsonify(json.load(f))
        except Exception as e:
            return jsonify({"error": f"Failed to read result file: {e}"}), 500
            
    return jsonify({"error": "Result file not found"}), 404


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """Uploads manga image files to the input directory."""
    settings = load_settings()
    input_dir = settings["input_dir"]
    
    # Ensure input_dir exists
    os.makedirs(input_dir, exist_ok=True)
    
    if 'files' not in request.files:
        return jsonify({"error": "No files uploaded"}), 400
        
    uploaded_files = request.files.getlist('files')
    saved_files = []
    
    for file in uploaded_files:
        if file and file.filename:
            filename = file.filename
            # Sanitize path-unsafe characters to protect directories
            unsafe_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
            for c in unsafe_chars:
                filename = filename.replace(c, '_')
            
            file_path = os.path.join(input_dir, filename)
            file.save(file_path)
            saved_files.append(filename)
            
    return jsonify({"status": "success", "saved_files": saved_files})


@app.route('/media/input/<path:filename>')
def serve_input_image(filename):
    """Serves the input manga images to the web UI."""
    settings = load_settings()
    input_dir = settings["input_dir"]
    if not os.path.exists(input_dir):
        return jsonify({"error": "Input directory not found"}), 404
    return send_from_directory(input_dir, filename)


def start_server(port: int = 5000) -> None:
    """Convenience starter for the Flask application."""
    # Ensure default directories exist
    settings = load_settings()
    os.makedirs(settings["input_dir"], exist_ok=True)
    os.makedirs(settings["output_dir"], exist_ok=True)
    
    logger.info(f"Starting DeepScribe web server on port {port}")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    start_server(5000)
