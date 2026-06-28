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
    app.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True, theme=gr.themes.Monochrome())

if __name__ == "__main__":
    main()
