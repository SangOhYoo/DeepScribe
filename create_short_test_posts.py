import sys
import os

# Add DeepScribe directory to path
sys.path.insert(0, r"D:\DeepScribe")

from novel_translator.services.gnuboard_db import register_post_to_gnuboard

def create_posts():
    posts = [
        {
            "bo_table": "trs",
            "subject": "테스트 번역 1화 (テスト翻訳 1話)",
            "content": "「こんにちは」と彼は言った。彼女は静かに頷いた。窓の外は天気が良い。",
            "ca_name": "테스트",
            "wr_name": "최고관리자",
            "wr_link1": "/bbs/board.php?bo_table=noc&wr_id=999991"
        },
        {
            "bo_table": "trs",
            "subject": "테스트 번역 2화 (テスト翻訳 2話)",
            "content": "「また明日ね」と彼女は微笑んだ。空には美しい星が輝いていた。静かな夜だ。",
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
    
    print("Registering short test posts...")
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
            print(f"Post '{p['subject']}' registration: {res}")
        except Exception as e:
            print(f"Error registering '{p['subject']}': {e}")

if __name__ == '__main__':
    create_posts()
