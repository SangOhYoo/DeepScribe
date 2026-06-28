"""Patch app.py to add Gnuboard registration UI and event wiring."""
import os

APP_PATH = r"d:\DeepScribe\novel_translator\app.py"

with open(APP_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# Normalize double-CR line endings to single-CR
content = content.replace("\r\r\n", "\r\n")

# === PATCH 1: Add registration UI section after download_file ===
download_marker = '''                download_file = gr.File(
                    label="📥 번역 파일 다운로드",
                    interactive=False,
                    visible=True,
                )

            with gr.Tab("📕 의성어 사전 관리 (Dictionary Manager)"):'''

registration_ui = '''                download_file = gr.File(
                    label="📥 번역 파일 다운로드",
                    interactive=False,
                    visible=True,
                )

                # ── Register to Gnuboard ──
                with gr.Accordion("💾 그누보드 게시판에 등록 (Register to Gnuboard)", open=True):
                    with gr.Row():
                        reg_board_select = gr.Dropdown(
                            choices=[],
                            label="등록 대상 게시판",
                            value="",
                            interactive=True,
                            scale=2,
                            allow_custom_value=True,
                        )
                        reg_subject = gr.Textbox(
                            label="등록 제목 (Subject)",
                            placeholder="그누보드에 등록할 제목을 입력하세요...",
                            value="",
                            interactive=True,
                            scale=5,
                        )
                        btn_reg_save = gr.Button(
                            "💾 번역 결과 등록",
                            variant="primary",
                            interactive=False,
                            scale=2,
                        )
                    reg_status = gr.Markdown("등록 대기 중...", elem_id="reg-status")

            with gr.Tab("📕 의성어 사전 관리 (Dictionary Manager)"):'''

if download_marker in content:
    content = content.replace(download_marker, registration_ui, 1)
    print("[OK] PATCH 1: Registration UI section added.")
else:
    print("[FAIL] PATCH 1: Could not find download_marker in content.")
    # Debug: find closest match
    for line in download_marker.split('\n'):
        stripped = line.strip()
        if stripped and stripped in content:
            continue
        elif stripped:
            print(f"  Missing line: {repr(stripped)}")


# === PATCH 2: Wire up btn_translate.click .then() for registration button ===
translate_click_end = '''            outputs=[
                progress_text, progress_bar,
                viewer_original, viewer_translated,
                download_file,
                viewer_reasoning,
            ],
        )

        # Cancel'''

translate_click_end_with_then = '''            outputs=[
                progress_text, progress_bar,
                viewer_original, viewer_translated,
                download_file,
                viewer_reasoning,
            ],
        ).then(
            fn=on_translation_complete,
            inputs=[viewer_translated, file_input],
            outputs=[btn_reg_save, reg_subject],
        )

        # Cancel'''

if translate_click_end in content:
    content = content.replace(translate_click_end, translate_click_end_with_then, 1)
    print("[OK] PATCH 2: Translation .then() for registration wired.")
else:
    print("[FAIL] PATCH 2: Could not find translate_click_end.")


# === PATCH 3: Wire up btn_reg_save.click ===
# Add registration button click event after the copy-to-clipboard buttons
copy_translated_end = '''        btn_copy_translated.click(
            fn=None,
            inputs=[viewer_translated],
            js="(val) => { if(val) { navigator.clipboard.writeText(val); alert('번역문이 클립보드에 복사되었습니다.'); } else { alert('복사할 번역문이 없습니다.'); } }"
        )

        # ── Dictionary Manager Event Wiring ──'''

copy_translated_with_register = '''        btn_copy_translated.click(
            fn=None,
            inputs=[viewer_translated],
            js="(val) => { if(val) { navigator.clipboard.writeText(val); alert('번역문이 클립보드에 복사되었습니다.'); } else { alert('복사할 번역문이 없습니다.'); } }"
        )

        # ── Gnuboard Registration Event Wiring ──
        btn_reg_save.click(
            fn=on_register_to_gnuboard,
            inputs=[reg_board_select, reg_subject, viewer_translated],
            outputs=[reg_status],
        )

        # ── Dictionary Manager Event Wiring ──'''

if copy_translated_end in content:
    content = content.replace(copy_translated_end, copy_translated_with_register, 1)
    print("[OK] PATCH 3: Registration button click event wired.")
else:
    print("[FAIL] PATCH 3: Could not find copy_translated_end.")


# === PATCH 4: Wire up reset_ui outputs to include registration controls ===
reset_outputs_old = '''            outputs=[
                file_input,
                paste_input,
                file_info,
                chunk_estimate,
                progress_text,
                progress_bar,
                viewer_original,
                viewer_translated,
                viewer_reasoning,
                download_file,
                original_text_state,
                btn_translate,
                btn_extract,
            ]
        )'''

reset_outputs_new = '''            outputs=[
                file_input,
                paste_input,
                file_info,
                chunk_estimate,
                progress_text,
                progress_bar,
                viewer_original,
                viewer_translated,
                viewer_reasoning,
                download_file,
                original_text_state,
                btn_translate,
                btn_extract,
                btn_reg_save,
                reg_subject,
                reg_status,
            ]
        )'''

if reset_outputs_old in content:
    content = content.replace(reset_outputs_old, reset_outputs_new, 1)
    print("[OK] PATCH 4: Reset UI outputs updated.")
else:
    print("[FAIL] PATCH 4: Could not find reset_outputs_old.")


# === PATCH 5: Update app.load for on_board_load to output both dropdowns ===
board_load_old = '''        app.load(
            fn=on_board_load,
            inputs=[],
            outputs=[gb_board_select],
        )'''

board_load_new = '''        app.load(
            fn=on_board_load,
            inputs=[],
            outputs=[gb_board_select, reg_board_select],
        )'''

if board_load_old in content:
    content = content.replace(board_load_old, board_load_new, 1)
    print("[OK] PATCH 5: app.load board_load outputs updated.")
else:
    print("[FAIL] PATCH 5: Could not find board_load_old.")


# Write the patched content back
with open(APP_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("\n[DONE] All patches applied to app.py")
