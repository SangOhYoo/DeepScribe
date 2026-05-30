import os
import sys
import time
import json
import shutil
import subprocess
import requests

# Define paths
DEEP_SCRIBE_DIR = "D:\\DeepScribe"
TEST_INPUT_DIR = os.path.join(DEEP_SCRIBE_DIR, "test_inputs")
TEST_OUTPUT_DIR = os.path.join(DEEP_SCRIBE_DIR, "test_outputs")
PYTHON_EXE = os.path.join(DEEP_SCRIBE_DIR, ".venv", "Scripts", "python.exe")
MOCK_SERVER_SCRIPT = os.path.join(DEEP_SCRIBE_DIR, "tests", "mock_server.py")
UI_SERVER_SCRIPT = os.path.join(DEEP_SCRIBE_DIR, "deepscribe", "ui.py")

# Valid 1x1 transparent PNG file bytes
DUMMY_PNG_BYTES = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

# Override print to safely handle Windows console encoding (e.g. cp949)
_original_print = print
def print(*args, **kwargs):
    enc = sys.stdout.encoding or "utf-8"
    new_args = []
    for arg in args:
        if isinstance(arg, str):
            new_args.append(arg.encode(enc, errors="replace").decode(enc))
        else:
            new_args.append(arg)
    _original_print(*new_args, **kwargs)

def setup_dirs():
    """Create test input/output directories and clean existing ones."""
    if os.path.exists(TEST_INPUT_DIR):
        shutil.rmtree(TEST_INPUT_DIR)
    if os.path.exists(TEST_OUTPUT_DIR):
        shutil.rmtree(TEST_OUTPUT_DIR)
    os.makedirs(TEST_INPUT_DIR, exist_ok=True)
    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)
    print("Test directories prepared.")

def create_dummy_image(name: str):
    """Creates a dummy 1x1 pixel PNG file."""
    path = os.path.join(TEST_INPUT_DIR, name)
    with open(path, "wb") as f:
        f.write(DUMMY_PNG_BYTES)
    print(f"Created mock image task: {name}")

def main():
    print("=== DeepScribe UI Backend Integration Test ===")
    
    # 1. Setup mock images
    setup_dirs()
    create_dummy_image("001_cut.png")
    create_dummy_image("002_cut.png")
    create_dummy_image("003_cut.png")

    # 2. Start Mock llama.cpp Server (port 8081)
    print("Starting Mock llama.cpp API server...")
    mock_server_proc = subprocess.Popen(
        [PYTHON_EXE, MOCK_SERVER_SCRIPT, "8081"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # 3. Start Flask UI Server (port 5000)
    print("Starting Flask UI Server...")
    ui_server_proc = subprocess.Popen(
        [PYTHON_EXE, "-m", "deepscribe.ui"],
        cwd=DEEP_SCRIBE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    time.sleep(3)  # Give servers time to boot
    
    if mock_server_proc.poll() is not None:
        print("ERROR: Mock API server failed to start.")
        sys.exit(1)
        
    if ui_server_proc.poll() is not None:
        print("ERROR: Flask UI server failed to start.")
        mock_server_proc.terminate()
        sys.exit(1)
        
    try:
        ui_base_url = "http://127.0.0.1:5000"
        
        # 4. Test GET /api/config
        print("\nTesting GET /api/config...")
        res = requests.get(f"{ui_base_url}/api/config")
        assert res.status_code == 200, "Config GET failed"
        config = res.json()
        print(f"Original Config loaded: {config}")
        
        # 5. Test POST /api/config to redirect to test directories
        print("\nUpdating configurations via POST /api/config...")
        update_payload = {
            "api_url": "http://127.0.0.1:8081/v1/chat/completions",
            "input_dir": TEST_INPUT_DIR,
            "output_dir": TEST_OUTPUT_DIR,
            "user_comment": "Testing UI Backend."
        }
        res = requests.post(f"{ui_base_url}/api/config", json=update_payload)
        assert res.status_code == 200, "Config POST failed"
        updated_config = res.json()["settings"]
        print(f"Updated Config: {updated_config}")
        
        # 6. Test GET /api/cuts (Verify all 3 cuts show pending)
        print("\nTesting GET /api/cuts...")
        res = requests.get(f"{ui_base_url}/api/cuts")
        assert res.status_code == 200, "Cuts GET failed"
        cuts = res.json()
        print(f"Loaded Cuts: {cuts}")
        assert len(cuts) == 3, "Should find 3 cuts"
        assert all(c["status"] == "pending" for c in cuts), "All cuts should be pending"
        
        # 6.5. Test POST /api/upload (Upload 4th cut)
        print("\nTesting POST /api/upload...")
        upload_files = {
            "files": ("004_cut.png", DUMMY_PNG_BYTES, "image/png")
        }
        res = requests.post(f"{ui_base_url}/api/upload", files=upload_files)
        if res.status_code != 200:
            print(f"Upload failed with status {res.status_code}: {res.text}")
        assert res.status_code == 200, "Upload POST failed"
        upload_res = res.json()
        print(f"Upload Response: {upload_res}")
        assert "004_cut.png" in upload_res["saved_files"]
        assert os.path.exists(os.path.join(TEST_INPUT_DIR, "004_cut.png")), "Uploaded file not saved"

        # Verify cuts list now has 4 items
        res = requests.get(f"{ui_base_url}/api/cuts")
        assert res.status_code == 200, "Cuts GET failed"
        cuts = res.json()
        print(f"Loaded Cuts after upload: {[c['filename'] for c in cuts]}")
        assert len(cuts) == 4, "Should find 4 cuts after upload"
        
        # 7. Test POST /api/process (Start Processing)
        print("\nTriggering pipeline start POST /api/process...")
        res = requests.post(f"{ui_base_url}/api/process", json={"action": "start"})
        assert res.status_code == 200, "Process start failed"
        print(f"Start Response: {res.json()}")
        
        # 8. Poll GET /api/status until complete
        print("\nPolling status...")
        timeout_limit = 35
        start_time = time.time()
        completed = False
        
        while time.time() - start_time < timeout_limit:
            res = requests.get(f"{ui_base_url}/api/status")
            assert res.status_code == 200, "Status GET failed"
            status = res.json()
            print(f"Current Status: Completed={status['completed_count']}/{status['total_cuts']}, Processing={status['is_processing']}, Msg={status['status_message']}")
            
            if not status["is_processing"] and status["completed_count"] == 4:
                completed = True
                break
            time.sleep(1)
            
        assert completed, "Pipeline failed to process all 4 cuts within timeout."
        
        # 9. Verify generated results via GET /api/result/4
        print("\nVerifying outputs via GET /api/result/4...")
        res = requests.get(f"{ui_base_url}/api/result/4")
        assert res.status_code == 200, "Failed to load result for Cut 4"
        result_data = res.json()
        print(f"Result for Cut 4: {result_data}")
        assert result_data["cut_number"] == 4
        assert "determined" in result_data["scene_description"].lower()
        assert "masterpiece" in result_data["positive_prompt"].lower()
        
        print("\n=== UI Backend REST APIs Integration Test Passed! ===")
        
    finally:
        print("\nStopping background servers...")
        mock_server_proc.terminate()
        ui_server_proc.terminate()
        try:
            mock_server_proc.wait(timeout=3)
            ui_server_proc.wait(timeout=3)
        except Exception:
            mock_server_proc.kill()
            ui_server_proc.kill()
        print("Servers stopped.")

if __name__ == "__main__":
    main()
