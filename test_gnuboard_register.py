import sys
sys.path.insert(0, r"D:\DeepScribe\.venv\Lib\site-packages")

import os
from novel_translator.services.gnuboard_db import register_post_to_gnuboard

def main():
    print("Testing Gnuboard Registration...")
    bo_table = "trs"
    subject = "테스트 번역 제목 - (テスト翻訳タイトル - 작성자 )"
    content = "<p>이것은 테스트 번역 내용입니다.</p>"
    ca_name = "테스트"
    wr_name = "테스터"
    wr_datetime = "2026-06-26 12:00:00"
    wr_link1 = "/bbs/board.php?bo_table=noc&wr_id=123"
    
    try:
        res = register_post_to_gnuboard(
            bo_table=bo_table,
            subject=subject,
            content=content,
            ca_name=ca_name,
            mb_id="admin",
            wr_name=wr_name,
            wr_datetime=wr_datetime,
            wr_1="test_flag",
            wr_link1=wr_link1
        )
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error during registration: {e}")

if __name__ == '__main__':
    main()
