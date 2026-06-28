import sys
import os
import subprocess
import time

# 1. Populate DB
sys.path.insert(0, r"D:\DeepScribe")
from novel_translator.services.gnuboard_db import register_post_to_gnuboard

posts = [
    {
        "bo_table": "trs",
        "subject": "테스트 번역 1화 (テスト翻訳 1화)",
        "content": "「こんにちは」と彼は言った。彼女は静かに頷いた。窓の外は天気が良い。",
        "ca_name": "테스트",
        "wr_name": "최고관리자",
        "wr_link1": "/bbs/board.php?bo_table=noc&wr_id=999991"
    },
    {
        "bo_table": "trs",
        "subject": "테스트 번역 2화 (テスト翻訳 2화)",
        "content": "「また明日ね」と彼女は微笑んだ。空에는美しい星이輝いていた。静かな夜だ。",
        "ca_name": "테스트",
        "wr_name": "최고관리자",
        "wr_link1": "/bbs/board.php?bo_table=noc&wr_id=999992"
    },
    {
        "bo_table": "trs",
        "subject": "테스트 번역 3화 (テスト翻訳 3화)",
        "content": "「ありがとう」と彼は答えた。彼らの新しい旅はここから始まるのだ。",
        "ca_name": "테스트",
        "wr_name": "최고관리자",
        "wr_link1": "/bbs/board.php?bo_table=noc&wr_id=999993"
    }
]

print("Populating short test posts...")
for p in posts:
    try:
        res = register_post_to_gnuboard(
            bo_table=p["bo_table"],
            subject=p["subject"],
            content=p["content"],
            ca_name=p["ca_name"],
            wr_name=p["wr_name"],
            wr_link1=p["wr_link1"]
        )
        print(f"Populated: {res}")
    except Exception as e:
        print(f"Populate error: {e}")

# 2. Start mock llama server on 8081
python_exe = r"d:\DeepScribe\.venv\Scripts\python.exe"
if not os.path.exists(python_exe):
    python_exe = "python"

mock_server_path = r"d:\DeepScribe\tests\mock_server.py"
if os.path.exists(mock_server_path):
    subprocess.Popen(
        [python_exe, mock_server_path, "8081"],
        cwd=r"d:\DeepScribe",
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print("Spawned mock server.")

# 3. Start Gradio server on 7862
bat_path = r"d:\DeepScribe\run_novel_translator.bat"
if os.path.exists(bat_path):
    subprocess.Popen(
        [bat_path],
        cwd=r"d:\DeepScribe",
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    print("Spawned Gradio translator server.")
