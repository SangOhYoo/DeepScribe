import re
import os

filepath = r"d:\DeepScribe\novel_translator\app.py"

with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. 이전 패치 도중 엉킨 부분을 완벽하게 기존 정상 코드로 먼저 되돌립니다.
# (gb_sort_select 드롭다운 복구 및 얽힌 아코디언 부분 복구)
target_corrupt_pattern = """                                    gb_sort_select = gr.Dropdown(
                                        choices=[
                                            ("최신순", "wr_id"),
                                            ("오래된순", "wr_id_asc"),
                                            ("제목순", "wr_subject"),
                                            (                # ── Advanced Settings (Collapsed) ──
                with gr.Accordion("⚙️ 고급 설정", open=False):"""

# 원래 있었어야 하는 코드 구조
reconstructed_normal_flow = """                                    gb_sort_select = gr.Dropdown(
                                        choices=[
                                            ("최신순", "wr_id"),
                                            ("오래된순", "wr_id_asc"),
                                            ("제목순", "wr_subject"),
                                            ("제목역순", "wr_subject_desc"),
                                        ],
                                        label="정렬",
                                        value="wr_id",
                                        interactive=True,
                                        scale=2
                                    )
                                    gb_rows_select = gr.Dropdown(
                                        choices=[("20개", 20), ("50개", 50), ("100개", 100), ("300개", 300), ("500개", 500), ("1000개", 1000)],
                                        label="출력수",
                                        value=20,
                                        interactive=True,
                                        scale=2
                                    )
                                    gb_btn_search = gr.Button("검색", variant="primary", scale=1)

                                with gr.Row(elem_id="gnuboard-control-row"):
                                    with gr.Column(scale=3):
                                        gb_search_summary = gr.HTML(
                                            value='<h4>검색 결과: <span style="color:#3182ce; font-weight:bold;">0</span>건</h4>'
                                                  '<small style="color:#718096;">왼쪽의 <b>☰ 핸들</b>을 드래그하여 병합 순서를 변경하세요.</small>'
                                        )
                                    with gr.Column(scale=2):
                                        with gr.Row():
                                            gb_btn_merge_to_translator = gr.Button("📥 번역기에 입력", variant="primary", size="sm")
                                            gb_btn_merge_download = gr.Button("📥 선택 항목 병합 다운로드", variant="secondary", size="sm")
                                
                                gb_table_html = gr.HTML(value=get_initial_table_html())
                                
                                with gr.Row():
                                    gb_btn_prev_page = gr.Button("<<", size="sm", scale=1)
                                    gb_page_number_display = gr.Markdown("1 / 1 페이지", elem_id="page-num-display")
                                    gb_btn_next_page = gr.Button(">>", size="sm", scale=1)

                        file_info = gr.Markdown("", elem_id="file-info")
                        chunk_estimate = gr.Markdown("", elem_id="chunk-estimate")

                    # Right: Language & Settings
                    with gr.Column(scale=2):
                        with gr.Row():
                            source_lang = gr.Dropdown(
                                choices=LANG_CHOICES_SOURCE,
                                value="ja",
                                label="📥 원문 언어",
                                interactive=True,
                            )
                            target_lang = gr.Dropdown(
                                choices=LANG_CHOICES_TARGET,
                                value="ko",
                                label="📤 번역 언어",
                                interactive=True,
                            )"""

content = content.replace(target_corrupt_pattern, reconstructed_normal_flow)

# 2. 고급설정 바깥에 남아있는 불필요하게 꼬인 duplicated block 제거
target_duplicate_block = """                        context_size = gr.Dropdown(
                            choices=[
                                ("2,048 (2K)", 2048),
                                ("4,096 (4K)", 4096),
                                ("8,192 (8K)", 8192),
                                ("16,384 (16K)", 16384),
                                ("32,768 (32K)", 32768),
                                ("65,536 (65K)", 65536),
                                ("131,072 (128K)", 131072),
                            ],
                            value=16384,
                            label="🧠 컨텍스트 윈도우 크기 (tokens)",
                            info="LLM의 최대 컨텍스트 크기에 맞춰 설정",
                            interactive=True,
                        )

                        temperature = gr.Slider(
                            minimum=0.0,
                            maximum=1.0,
                            value=0.3,
                            step=0.05,
                            label="🌡️ Temperature",
                            info="낮을수록 정확, 높을수록 창의적",
                        )

                        enable_thinking = gr.Checkbox(
                            value=False,
                            label="🧠 모델 사고 과정(Thinking) 활성화",
                            info="활성화 시 추론 과정을 거쳐 품질이 향상될 수 있으나 번역 속도가 느려집니다. (비활성화 시 속도가 대폭 향상됨)",
                        )"""

content = content.replace(target_duplicate_block, "")

# 3. 고급 설정(Accordion) 내부로 컨텍스트 윈도우 크기, Temperature, Thinking 체크박스를 이동시킵니다.
old_accordion_block = """                # ── Advanced Settings (Collapsed) ──
                with gr.Accordion("⚙️ 고급 설정", open=False):
                    with gr.Row():
                        api_url = gr.Textbox(
                            label="API URL",
                            value="",
                            placeholder="http://127.0.0.1:8081/v1/chat/completions (기본값)",
                            info="비워두면 settings.json 또는 기본값 사용",
                        )"""

new_accordion_block = """                # ── Advanced Settings (Collapsed) ──
                with gr.Accordion("⚙️ 고급 설정", open=False):
                    with gr.Row():
                        context_size = gr.Dropdown(
                            choices=[
                                ("2,048 (2K)", 2048),
                                ("4,096 (4K)", 4096),
                                ("8,192 (8K)", 8192),
                                ("16,384 (16K)", 16384),
                                ("32,768 (32K)", 32768),
                                ("65,536 (65K)", 65536),
                                ("131,072 (128K)", 131072),
                            ],
                            value=16384,
                            label="🧠 컨텍스트 윈도우 크기 (tokens)",
                            info="LLM의 최대 컨텍스트 크기에 맞춰 설정",
                            interactive=True,
                        )
                        temperature = gr.Slider(
                            minimum=0.0,
                            maximum=1.0,
                            value=0.3,
                            step=0.05,
                            label="🌡️ Temperature",
                            info="낮을수록 정확, 높을수록 창의적",
                        )
                    with gr.Row():
                        enable_thinking = gr.Checkbox(
                            value=False,
                            label="🧠 모델 사고 과정(Thinking) 활성화",
                            info="활성화 시 추론 과정을 거쳐 품질이 향상될 수 있으나 번역 속도가 느려집니다.",
                        )
                    with gr.Row():
                        api_url = gr.Textbox(
                            label="API URL",
                            value="",
                            placeholder="http://127.0.0.1:8081/v1/chat/completions (기본값)",
                            info="비워두면 settings.json 또는 기본값 사용",
                        )"""

content = content.replace(old_accordion_block, new_accordion_block)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print("Manual fix script finished successfully.")
