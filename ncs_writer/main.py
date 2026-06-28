import sys
import os

# Add the current directory to sys.path to ensure local module imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import build_ui

def main():
    print("========================================================")
    print("      NCS Competency Standard Writing System")
    print("========================================================")
    print("[SYSTEM] Starting NCS Writer Server...")
    
    app = build_ui()
    
    # Launch Gradio server on port 7870
    app.launch(
        server_name="127.0.0.1",
        server_port=7870,
        share=False,
        inbrowser=False
    )

if __name__ == "__main__":
    main()
