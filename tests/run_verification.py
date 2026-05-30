import os
import sys
import time
import json
import shutil
import subprocess

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

# Define paths
DEEP_SCRIBE_DIR = "D:\\DeepScribe"
TEST_INPUT_DIR = os.path.join(DEEP_SCRIBE_DIR, "test_inputs")
TEST_OUTPUT_DIR = os.path.join(DEEP_SCRIBE_DIR, "test_outputs")
PYTHON_EXE = os.path.join(DEEP_SCRIBE_DIR, ".venv", "Scripts", "python.exe")
MOCK_SERVER_SCRIPT = os.path.join(DEEP_SCRIBE_DIR, "tests", "mock_server.py")

# Valid 1x1 transparent PNG file bytes
DUMMY_PNG_BYTES = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

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

def run_pipeline(user_comment: str = "") -> subprocess.CompletedProcess:
    """Invokes the DeepScribe pipeline main.py via the venv python."""
    cmd = [
        PYTHON_EXE,
        "-m", "deepscribe.main",
        "--input-dir", TEST_INPUT_DIR,
        "--output-dir", TEST_OUTPUT_DIR,
    ]
    if user_comment:
        cmd.extend(["--user-comment", user_comment])
        
    print(f"Executing: {' '.join(cmd)}")
    # Run from the D:\DeepScribe folder to ensure module resolution is correct
    return subprocess.run(
        cmd,
        cwd=DEEP_SCRIBE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

def main():
    print("=== DeepScribe Automated Pipeline Verification ===")
    
    # 1. Start Mock Server
    print("Starting Mock llama.cpp API server in background...")
    server_proc = subprocess.Popen(
        [PYTHON_EXE, MOCK_SERVER_SCRIPT, "8081"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2)  # Give server time to bind and start listening
    
    if server_proc.poll() is not None:
        print("Error: Mock server failed to start. Exiting verification.")
        sys.exit(1)
        
    try:
        # 2. Phase 1: Test standard processing of Cuts 1 and 2
        print("\n--- PHASE 1: Normal Processing (Cut 1 and Cut 2) ---")
        setup_dirs()
        create_dummy_image("001_cut.png")
        create_dummy_image("002_cut.png")
        
        result = run_pipeline("First session run.")
        print(result.stdout)
        if result.returncode != 0:
            print("ERROR: Pipeline exited with non-zero code in Phase 1.")
            print(result.stderr)
            sys.exit(1)
            
        # Verify JSON files are created
        json1 = os.path.join(TEST_OUTPUT_DIR, "1.json")
        json2 = os.path.join(TEST_OUTPUT_DIR, "2.json")
        
        if not os.path.exists(json1) or not os.path.exists(json2):
            print("ERROR: Missing expected output JSON files in Phase 1.")
            sys.exit(1)
            
        with open(json1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
            print(f"Verified 1.json: novel_paragraph -> '{data1.get('novel_paragraph')}'")
            if "Cut 1" not in data1.get("scene_description", ""):
                print("ERROR: Cut number tracking failed in 1.json contents.")
                sys.exit(1)

        with open(json2, "r", encoding="utf-8") as f:
            data2 = json.load(f)
            print(f"Verified 2.json: novel_paragraph -> '{data2.get('novel_paragraph')}'")
            
        print("Phase 1 verification successful!")

        # 3. Phase 2: Resume logic (adding Cut 3, processing should skip 1 & 2)
        print("\n--- PHASE 2: Resume Processing (Add Cut 3) ---")
        create_dummy_image("003_cut.png")
        
        result_resume = run_pipeline("Second session run with resume.")
        print(result_resume.stdout)
        
        if result_resume.returncode != 0:
            print("ERROR: Pipeline exited with non-zero code in Phase 2.")
            print(result_resume.stderr)
            sys.exit(1)
            
        # Check logs for resume confirmation
        stdout_text = result_resume.stdout
        if "Resuming from last completed cut: 2" not in stdout_text:
            print("ERROR: Resume logs not found or incorrect.")
            sys.exit(1)
        if "Skipped 2 already processed cuts" not in stdout_text:
            print("ERROR: Cut skipping verification failed in log output.")
            sys.exit(1)
            
        json3 = os.path.join(TEST_OUTPUT_DIR, "3.json")
        if not os.path.exists(json3):
            print("ERROR: 3.json was not generated in Phase 2.")
            sys.exit(1)
            
        with open(json3, "r", encoding="utf-8") as f:
            data3 = json.load(f)
            print(f"Verified 3.json: novel_paragraph -> '{data3.get('novel_paragraph')}'")
            print(f"Verified 3.json: positive_prompt -> '{data3.get('positive_prompt')}'")
            
        print("Phase 2 (Resume & History Recovery) verification successful!")
        
        print("\n=== All Tests Passed Successfully! ===")
        
    finally:
        # Clean up Mock Server
        print("\nTerminating Mock llama.cpp server...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        print("Mock server stopped.")

if __name__ == "__main__":
    main()
