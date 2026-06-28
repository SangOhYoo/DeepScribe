import subprocess
import sys

try:
    import gradio
    import sqlalchemy
except ImportError:
    print("Installing missing dependencies (gradio, sqlalchemy)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gradio", "sqlalchemy"])
    print("Dependencies installed successfully!")

from ui import build_ui

def main():
    print("Starting Abyss Writer UI...")
    import gradio as gr
    app = build_ui()
    import sys
    port = 7860
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    app.launch(
        server_name="127.0.0.1", 
        server_port=port, 
        inbrowser=True, 
        theme=gr.themes.Soft(primary_hue="purple", secondary_hue="indigo", neutral_hue="slate")
    )

if __name__ == "__main__":
    main()
