import os

filepath = r"d:\DeepScribe\novel_translator\app.py"

with open(filepath, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

# Helper to find a line starting with a string, ignoring leading whitespace
def find_line_index(start_str, start_from=0):
    for i in range(start_from, len(lines)):
        if lines[i].strip().startswith(start_str):
            return i
    return -1

# Helper to replace a block of lines from start_idx to end_idx with new_text
def replace_block(start_idx, end_idx, new_text):
    global lines
    lines[start_idx:end_idx] = new_text.splitlines()

# 1. Replace on_merge_to_translator
idx_merge = find_line_index("def on_merge_to_translator")
if idx_merge != -1:
    idx_next = find_line_index("def on_merge_download", idx_merge + 1)
    if idx_next != -1:
        new_merge_code = """def on_merge_to_translator(bo_table, selected_ids_str):
    \"\"\"선택된 글들을 병합하여 번역기 원문으로 바로 로딩합니다. (동기식)\"\"\"
    if not bo_table:
        return "❌ 오류: 게시판을 선택해야 합니다.", "", "", gr.update(interactive=False), gr.update(interactive=False), None
    if not selected_ids_str or not selected_ids_str.strip():
        return "❌ 오류: 선택된 게시글이 없습니다. 테이블에서 체크박스를 선택해 주세요.", "", "", gr.update(interactive=False), gr.update(interactive=False), None
        
    wr_ids = [x.strip() for x in selected_ids_str.split(",") if x.strip()]
    
    merged_text = merge_posts_content(bo_table, wr_ids)
    if not merged_text:
        return "❌ 오류: 게시글 본문을 가져오지 못했습니다.", "", "", gr.update(interactive=False), gr.update(interactive=False), None
        
    normalized_text = normalize_input_text(merged_text)
    char_count = len(normalized_text)
    line_count = normalized_text.count('\\n') + 1
    
    info_msg = f"📂 **그누보드 가져오기 ({bo_table})**  ·  {len(wr_ids)}개 글 병합  ·  {char_count:,}자  ·  {line_count:,}줄"
    
    # Fetch posts metadata to return to state
    posts_meta = get_posts_details(bo_table, wr_ids)
    posts_metadata_payload = {
        "bo_table": bo_table,
        "wr_ids": wr_ids,
        "posts": posts_meta
    }
    
    return info_msg, normalized_text, normalized_text, gr.update(interactive=True), gr.update(interactive=True), posts_metadata_payload
"""
        replace_block(idx_merge, idx_next, new_merge_code)
        print("Success: Replaced on_merge_to_translator")
    else:
        print("Error: Could not find end of on_merge_to_translator")
else:
    print("Error: Could not find def on_merge_to_translator")

# 2. Replace reset_ui
idx_reset = find_line_index("def reset_ui")
if idx_reset != -1:
    idx_next = find_line_index("def on_register_to_gnuboard", idx_reset + 1)
    if idx_next != -1:
        new_reset_code = """def reset_ui():
    \"\"\"초기화 버튼 클릭 시 모든 UI 상태를 리셋합니다.\"\"\"
    global orchestrator
    orchestrator.reset()
    return (
        None,                         # file_input
        "",                           # paste_input
        "",                           # file_info
        "",                           # chunk_estimate
        "",                           # progress_text
        0,                            # progress_bar
        "",                           # viewer_original
        "",                           # viewer_translated
        "",                           # viewer_reasoning
        None,                         # download_file
        "",                           # original_text_state
        gr.update(interactive=False),  # btn_translate
        gr.update(interactive=False),  # btn_extract
        gr.update(interactive=False),  # btn_reg_save
        "",                           # reg_subject
        "등록 대기 중...",             # reg_status
        None,                         # gb_selected_posts_state
    )
"""
        replace_block(idx_reset, idx_next, new_reset_code)
        print("Success: Replaced reset_ui")
    else:
        print("Error: Could not find end of reset_ui")
else:
    print("Error: Could not find def reset_ui")

# 3. Replace on_register_to_gnuboard and on_translation_complete
idx_reg = find_line_index("def on_register_to_gnuboard")
if idx_reg != -1:
    idx_next = find_line_index("def run_onomatopoeia_extraction", idx_reg + 1)
    if idx_next != -1:
        new_reg_code = """def on_register_to_gnuboard(bo_table, subject, translated_content, gb_selected_posts):
    \"\"\"번역된 내용을 그누보드 게시판에 등록합니다.\"\"\"
    if not bo_table:
        return "❌ 오류: 대상 게시판을 선택해주세요."
    if not subject or not subject.strip():
        return "❌ 오류: 제목을 입력해주세요."
    if not translated_content or not translated_content.strip():
        return "❌ 오류: 번역된 내용이 없습니다. 먼저 번역을 실행해주세요."

    try:
        # HTML 형식으로 변환 (줄바꿈 -> <br>)
        html_content = translated_content.replace("\\n", "<br>\\n")
        
        # Prepare metadata if we have a source post
        wr_name = "최고관리자"
        wr_datetime = None
        wr_link1 = ""
        ca_name = "번역"
        
        if gb_selected_posts and gb_selected_posts.get("posts"):
            posts = gb_selected_posts["posts"]
            first_post = posts[0]
            wr_name = first_post.get("wr_name") or "최고관리자"
            # 원래 원문의 등록일자를 그대로 등록한다.
            wr_datetime = first_post.get("wr_datetime")
            
            # 그누보드 원문게시물의 link 를 그누보드 게시판 테이블의 컬럼 wr_link1에 입력.
            # 로컬형식인 http://localhost 로 시작하도록 한다.
            source_bo_table = gb_selected_posts.get("bo_table")
            source_wr_id = first_post.get("wr_id")
            wr_link1 = f"http://localhost/bbs/board.php?bo_table={source_bo_table}&wr_id={source_wr_id}"
            
        res = register_post_to_gnuboard(
            bo_table=bo_table,
            subject=subject.strip(),
            content=html_content,
            ca_name=ca_name,
            mb_id="admin",
            wr_name=wr_name,
            wr_datetime=wr_datetime,
            wr_1="translated",
            wr_link1=wr_link1
        )
        
        if res and str(res).startswith("updated:"):
            wr_id = str(res).split(":")[1]
            return f"✅ 게시판 **'{bo_table}'**에 성공적으로 업데이트! (글 ID: {wr_id})"
        elif res and str(res).startswith("skipped:"):
            wr_id = str(res).split(":")[1]
            return f"ℹ️ 동일한 글이 이미 존재합니다. (글 ID: {wr_id})"
        else:
            return f"✅ 게시판 **'{bo_table}'**에 성공적으로 등록! (글 ID: {res})"
    except Exception as e:
        logger.error(f"Error registering to gnuboard: {e}")
        return f"❌ 등록 중 오류가 발생했습니다: {str(e)}"


def on_translation_complete(translated_text, file_obj, gb_selected_posts, api_url, api_key):
    \"\"\"번역 완료 후 그누보드 등록 버튼을 활성화하고 기본 제목을 설정합니다.\"\"\"
    import datetime as dt
    if not translated_text or not translated_text.strip():
        return gr.update(interactive=False), gr.update()
 
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if gb_selected_posts and gb_selected_posts.get("posts"):
        # We have original post(s)!
        posts = gb_selected_posts["posts"]
        first_post = posts[0]
        original_subject = first_post.get("wr_subject", "")
        original_writer = first_post.get("wr_name", "")
        
        # Translate the title to Korean using LLM
        translated_title = original_subject
        try:
            client_kwargs = {}
            if api_url:
                client_kwargs["api_url"] = api_url.strip()
            if api_key:
                client_kwargs["api_key"] = api_key.strip()
            title_client = TranslationClient(**client_kwargs)
            
            system_prompt = (
                "당신은 소설 번역가입니다. 소설의 소제목이나 장 제목을 자연스러운 한국어 장명(제목)으로 번역해 주세요. "
                "장식이나 해설 없이 순수한 한국어 번역 결과만 한 줄로 출력하십시오."
            )
            user_prompt = f"원문 제목: {original_subject}\\n번역된 제목:"
            
            llm_res = title_client.translate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3
            )
            if llm_res:
                translated_title = llm_res.strip().strip('"').strip("'")
        except Exception as e:
            logger.error(f"Error translating title in completion callback: {e}")
            
        # Format: 번역된 한글제목 (원문제목) - 작성자
        default_subject = f"{translated_title} ({original_subject}) - {original_writer}"
    elif file_obj:
        filename_no_ext = os.path.splitext(os.path.basename(str(file_obj)))[0]
        default_subject = f"번역 완료 - {filename_no_ext}"
    else:
        default_subject = f"번역 완료 - {now_str}"
 
    return gr.update(interactive=True), gr.update(value=default_subject)
"""
        replace_block(idx_reg, idx_next, new_reg_code)
        print("Success: Replaced on_register_to_gnuboard and on_translation_complete")
    else:
        print("Error: Could not find end of on_translation_complete")
else:
    print("Error: Could not find def on_register_to_gnuboard")

# 4. Insert State
idx_state = find_line_index("gb_max_page = gr.State")
if idx_state != -1:
    # Check if not already added
    if not any("gb_selected_posts_state" in line for line in lines):
        lines.insert(idx_state + 1, "        gb_selected_posts_state = gr.State(None)")
        print("Success: Added gb_selected_posts_state")
    else:
        print("Info: gb_selected_posts_state already exists")
else:
    print("Error: Could not find gb_max_page state declaration")

# Let's save the file here to update line indices for the remaining wiring replacements
with open(filepath, "w", encoding="utf-8", newline="\r\n") as f:
    f.write("\r\n".join(lines))

print("Partial save complete. Re-reading file for wiring...")

# Re-read file to get correct indices after state insertion
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.read().splitlines()

# 5. Wiring 1: Translate.click().then() and reset_ui outputs
idx_then = find_line_index("inputs=[viewer_translated, file_input],")
if idx_then != -1:
    lines[idx_then] = "            inputs=[viewer_translated, file_input, gb_selected_posts_state, api_url, api_key],"
    print("Success: Updated then() inputs")
else:
    # Try looking for a slightly different one
    idx_then = find_line_index("fn=on_translation_complete,")
    if idx_then != -1:
        # Find next line starting with inputs=
        idx_inputs = find_line_index("inputs=", idx_then)
        if idx_inputs != -1:
            lines[idx_inputs] = "            inputs=[viewer_translated, file_input, gb_selected_posts_state, api_url, api_key],"
            print("Success: Updated then() inputs (fallback)")

# Reset UI outputs:
# We need to find outputs of reset_ui click
idx_reset_btn = find_line_index("btn_reset.click(")
if idx_reset_btn != -1:
    idx_outputs = find_line_index("outputs=[", idx_reset_btn)
    if idx_outputs != -1:
        # Find the closing bracket ]
        idx_close = find_line_index("]", idx_outputs)
        if idx_close != -1:
            # Insert gb_selected_posts_state right before the closing bracket
            lines.insert(idx_close, "                gb_selected_posts_state,")
            print("Success: Updated reset_ui outputs")
        else:
            print("Error: Could not find closing bracket of reset_ui outputs")
    else:
        print("Error: Could not find outputs=[ of reset_ui")
else:
    print("Error: Could not find btn_reset.click")

# 6. Wiring 2: btn_reg_save.click
idx_reg_wiring = find_line_index("btn_reg_save.click(")
if idx_reg_wiring != -1:
    idx_inputs = find_line_index("inputs=[reg_board_select, reg_subject, viewer_translated],", idx_reg_wiring)
    if idx_inputs != -1:
        lines[idx_inputs] = "            inputs=[reg_board_select, reg_subject, viewer_translated, gb_selected_posts_state],"
        print("Success: Updated btn_reg_save inputs")
    else:
        print("Error: Could not find inputs of btn_reg_save")
else:
    print("Error: Could not find btn_reg_save.click")

# 7. Wiring 3: gb_btn_merge_to_translator.click outputs
idx_merge_wiring = find_line_index("gb_btn_merge_to_translator.click(")
if idx_merge_wiring != -1:
    idx_outputs = find_line_index("outputs=[file_info, original_text_state, viewer_original, btn_translate, btn_extract],", idx_merge_wiring)
    if idx_outputs != -1:
        lines[idx_outputs] = "            outputs=[file_info, original_text_state, viewer_original, btn_translate, btn_extract, gb_selected_posts_state],"
        print("Success: Updated gb_btn_merge_to_translator outputs")
    else:
        print("Error: Could not find outputs of gb_btn_merge_to_translator")
else:
    print("Error: Could not find gb_btn_merge_to_translator.click")

# Save the final file
with open(filepath, "w", encoding="utf-8", newline="\r\n") as f:
    f.write("\r\n".join(lines))

print("All replacements done.")
