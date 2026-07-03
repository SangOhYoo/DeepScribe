import logging

import os

import sys

import tempfile

import threading

import time

from typing import Optional

import csv

import sqlite3



import gradio as gr



# Ensure parent directory is in path for imports

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))



from novel_translator.services.translator import (

    TranslationOrchestrator,

    TranslationStatus,

    detect_encoding,

    normalize_input_text,

)

from novel_translator.services.llm_client import TranslationClient

from novel_translator.services.chunker import SmartChunker

from novel_translator.services.gnuboard_db import get_boards, search_posts, merge_posts_content, register_post_to_gnuboard, get_posts_details

from novel_translator.services.onomatopoeia_db import OnomatopoeiaDB
from novel_translator.services.dict_manager import (
    load_current_dictionary,
    get_pending_choices,
    reject_pending_word,
    load_pending_word_details,
    approve_pending_word,
    approve_all_pending_words,
    get_registered_choices,
    load_registered_word_details,
    update_registered_word,
    delete_registered_word,
)



# ─── Logging ────────────────────────────────────────────────────────────

logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",

)

logger = logging.getLogger("NovelTranslator.App")



# ─── Constants ──────────────────────────────────────────────────────────

LANG_CHOICES_SOURCE = [

    ("일본어 (Japanese)", "ja"),

    ("중국어 (Chinese)", "zh"),

    ("영어 (English)", "en"),

    ("한국어 (Korean)", "ko"),

]

LANG_CHOICES_TARGET = [

    ("한국어 (Korean)", "ko"),

    ("일본어 (Japanese)", "ja"),

    ("영어 (English)", "en"),

    ("중국어 (Chinese)", "zh"),

]



# ─── Global State ───────────────────────────────────────────────────────

orchestrator = TranslationOrchestrator()

translation_thread: Optional[threading.Thread] = None



# ─── CSS Theme ──────────────────────────────────────────────────────────

CUSTOM_CSS = """

/* ─── Fluid width, no fixed max-width ─── */

.gradio-container {

    max-width: 100% !important;

    padding: 20px 3vw !important;

}



/* ─── Header: muted, readable ─── */

#app-header {

    background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%) !important;

    padding: 18px 28px !important;

    border-radius: 12px !important;

    margin-bottom: 14px !important;

    border: 1px solid #4a5568 !important;

}

#app-header h1 {

    color: #e2e8f0 !important;

    font-size: 1.6em !important;

    font-weight: 700 !important;

    margin: 0 !important;

}

#app-header p {

    color: #a0aec0 !important;

    margin: 4px 0 0 !important;

    font-size: 0.9em !important;

}



/* ─── Buttons: legible, not garish ─── */

#btn-translate {

    background: #4a6fa5 !important;

    border: 1px solid #5a7fb5 !important;

    color: #fff !important;

    font-size: 1.05em !important;

    font-weight: 600 !important;

    padding: 10px 28px !important;

    border-radius: 8px !important;

    transition: background 0.2s ease !important;

}

#btn-translate:hover {

    background: #5a7fb5 !important;

}



#btn-cancel {

    background: #c53030 !important;

    border: 1px solid #e53e3e !important;

    color: #fff !important;

    border-radius: 8px !important;

}

#btn-cancel:hover {

    background: #e53e3e !important;

}



#btn-test {

    background: #2f855a !important;

    border: 1px solid #38a169 !important;

    color: #fff !important;

    border-radius: 8px !important;

}



/* ─── Progress status ─── */

#progress-status {

    font-weight: 600 !important;

    color: #3182ce !important;

}

.dark #progress-status {

    color: #63b3ed !important;

}



/* ─── Viewer textboxes: comfortable reading (light/dark adapt) ─── */

#viewer-original textarea, #viewer-translated textarea, #paste-input textarea {

    font-family: 'Noto Sans KR', 'Noto Sans JP', 'Malgun Gothic', sans-serif !important;

    font-size: 14px !important;

    line-height: 1.85 !important;

    background: var(--input-background-fill) !important;

    color: var(--body-text-color) !important;

    border: 1px solid var(--border-color-primary) !important;

    border-radius: 6px !important;

    padding: 12px !important;

}



/* Hide original textareas since we use custom diff viewer HTML */

#viewer-original, #viewer-translated {

    display: none !important;

}

/* Hide Gnuboard tracking textboxes but keep them in DOM for JS access */

#gb-posts-json, #gb-selected-ids {

    visibility: hidden !important;

    position: absolute !important;

    height: 0 !important;

    width: 0 !important;

    overflow: hidden !important;

    pointer-events: none !important;

}



/* ─── CSS Variables for Diff Viewer ─── */

:root {

    --diff-bg: #ffffff;

    --diff-gutter-bg: #f7f9fa;

    --diff-gutter-color: #718096;

    --diff-border-color: #e2e8f0;

    --diff-center-border-color: #cbd5e0;

    --diff-hover-bg: rgba(74, 111, 165, 0.05);

}



.dark, [data-theme="dark"] {

    --diff-bg: #1a202c;

    --diff-gutter-bg: #2d3748;

    --diff-gutter-color: #a0aec0;

    --diff-border-color: #4a5568;

    --diff-center-border-color: #4a5568;

    --diff-hover-bg: rgba(255, 255, 255, 0.08);

}



#diff-view-wrapper {

    border: 1px solid var(--border-color-primary, #e2e8f0);

    border-radius: 8px;

    background-color: var(--diff-bg);

    overflow: hidden;

    margin-top: 10px;

    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);

}



.diff-header-row {

    display: grid;

    grid-template-columns: 1fr 1fr;

    background-color: var(--diff-gutter-bg);

    border-bottom: 1px solid var(--border-color-primary, #e2e8f0);

    font-weight: 600;

    color: var(--body-text-color, #4a5568);

    font-size: 0.9em;

}



.diff-header-col {

    padding: 10px 16px;

    text-align: left;

}



.diff-header-col:first-child {

    border-right: 1px solid var(--diff-center-border-color);

}



#diff-view-container {

    max-height: 550px;

    overflow-y: auto;

    background-color: var(--diff-bg);

}



.diff-placeholder {

    padding: 40px;

    text-align: center;

    color: #a0aec0;

    font-style: italic;

}



.diff-row {

    display: grid;

    grid-template-columns: 45px minmax(0, 1fr) 45px minmax(0, 1fr);

    border-bottom: 1px solid var(--border-color-primary, #e2e8f0);

    transition: background-color 0.15s ease;

}



.diff-row:hover {

    background-color: var(--diff-hover-bg) !important;

}



.diff-line-num {

    text-align: right;

    padding-right: 10px;

    user-select: none;

    color: var(--diff-gutter-color);

    background-color: var(--diff-gutter-bg);

    font-family: 'Fira Code', 'Consolas', monospace;

    font-size: 11px;

    line-height: 1.8;

    border-right: 1px solid var(--diff-border-color);

    padding-top: 4px;

    padding-bottom: 4px;

}



.diff-line-content {

    padding: 4px 16px;

    white-space: pre-wrap;

    word-break: break-all;

    font-size: 13.5px;

    line-height: 1.8;

    font-family: 'Noto Sans KR', 'Noto Sans JP', sans-serif;

    color: var(--body-text-color, #2d3748);

}



.diff-original-content {

    border-right: 1px solid var(--diff-center-border-color);

}



/* Scrollbar styling */

#diff-view-container::-webkit-scrollbar {

    width: 8px;

    height: 8px;

}

#diff-view-container::-webkit-scrollbar-track {

    background: var(--diff-gutter-bg);

}

#diff-view-container::-webkit-scrollbar-thumb {

    background: #cbd5e0;

    border-radius: 4px;

}

#diff-view-container::-webkit-scrollbar-thumb:hover {

    background: #a0aec0;

}



/* ─── Reasoning viewer: subtle, secondary look ─── */

#viewer-reasoning textarea {

    font-family: 'Consolas', 'Noto Sans KR', monospace !important;

    font-size: 12px !important;

    line-height: 1.6 !important;

    background: #f7f7f0 !important;

    color: #6b7280 !important;

    border: 1px solid #d1d5db !important;

    border-radius: 6px !important;

    padding: 10px !important;

}

.dark #viewer-reasoning textarea, [data-theme="dark"] #viewer-reasoning textarea {

    background: #1e1e2e !important;

    color: #9ca3af !important;

    border: 1px solid #374151 !important;

}



/* ─── File info badge ─── */

#file-info {

    padding: 8px 14px !important;

    background: rgba(74, 111, 165, 0.08) !important;

    border-radius: 6px !important;

    border-left: 3px solid #4a6fa5 !important;

    color: #4a5568 !important;

}

.dark #file-info, [data-theme="dark"] #file-info {

    background: rgba(74, 111, 165, 0.15) !important;

    color: #cbd5e0 !important;

}



/* ─── Tabs ─── */

.tab-nav button {

    font-weight: 600 !important;

}

"""





# ─── Helper Functions ───────────────────────────────────────────────────



def format_duration(seconds: float) -> str:

    s = int(round(seconds))

    if s < 60:

        return f"{s}초"

    m = s // 60

    s = s % 60

    if m < 60:

        return f"{m}분 {s}초"

    h = m // 60

    m = m % 60

    return f"{h}시간 {m}분 {s}초"





def format_time_info(prog) -> str:

    if not prog or prog.start_time is None:

        return ""

    

    end_time = prog.end_time if prog.end_time is not None else time.time()

    elapsed = end_time - prog.start_time

    if elapsed < 0:

        elapsed = 0.0



    if prog.status == TranslationStatus.COMPLETED:

        return f"소요시간: {format_duration(elapsed)}"



    if prog.status == TranslationStatus.TRANSLATING and prog.current_chunk > 0 and prog.total_chunks > 0:

        avg_time_per_chunk = elapsed / prog.current_chunk

        remaining_chunks = prog.total_chunks - prog.current_chunk

        remaining_time = remaining_chunks * avg_time_per_chunk

        return f"소요: {format_duration(elapsed)} / 남은 예상: {format_duration(remaining_time)}"



    return f"소요: {format_duration(elapsed)}"





def on_file_upload(file_obj):

    """Handle file upload and return file info + text content."""

    if file_obj is None:

        return "", "", gr.update(interactive=False), gr.update(interactive=False)



    file_path = str(file_obj)



    if not os.path.exists(file_path):

        return "파일을 찾을 수 없습니다.", "", gr.update(interactive=False), gr.update(interactive=False)



    # Detect encoding and read

    encoding = detect_encoding(file_path)

    try:

        with open(file_path, "r", encoding=encoding) as f:

            text = normalize_input_text(f.read())

    except Exception as e:

        return f"파일 읽기 오류: {e}", "", gr.update(interactive=False), gr.update(interactive=False)



    file_size = os.path.getsize(file_path)

    char_count = len(text)

    line_count = text.count('\n') + 1

    file_name = os.path.basename(file_path)



    info = (

        f"📄 **{file_name}**  ·  "

        f"{char_count:,}자  ·  {line_count:,}줄  ·  "

        f"{file_size / 1024:.1f} KB  ·  인코딩: {encoding}"

    )



    return info, text, gr.update(interactive=True), gr.update(interactive=True)





def on_paste_text(pasted_text):

    """Handle pasted text input."""

    if not pasted_text or not pasted_text.strip():

        return "", gr.update(interactive=False), gr.update(interactive=False)



    text = pasted_text.strip()

    char_count = len(text)

    line_count = text.count('\n') + 1



    info = f"📋 붙여넣기 입력  ·  {char_count:,}자  ·  {line_count:,}줄"

    return info, gr.update(interactive=True), gr.update(interactive=True)





def estimate_chunks(text, source_lang, context_size):

    """Estimate how many chunks the text will be split into."""

    if not text:

        return ""

    try:

        ctx_size = int(context_size)

    except Exception:

        try:

            clean_str = "".join(c for c in str(context_size) if c.isdigit())

            ctx_size = int(clean_str)

        except Exception:

            ctx_size = 16384



    chunker = SmartChunker(context_size=ctx_size, source_lang=source_lang)

    chunks = chunker.chunk_text(text)

    total_tokens = sum(c.estimated_tokens for c in chunks)

    return (

        f"📊 예상 청크: **{len(chunks)}**개  ·  "

        f"예상 토큰: **{total_tokens:,}**  ·  "

        f"청크당 평균: ~{total_tokens // max(len(chunks), 1):,} tokens"

    )





def test_connection(api_url, api_key):

    """Test LLM server connection."""

    client = TranslationClient(

        api_url=api_url if api_url else None,

        api_key=api_key if api_key else None,

    )

    ok, msg = client.test_connection()

    return msg





def on_board_load():

    """게시판 목록을 동적으로 가져와 드롭다운을 업데이트합니다. (동기식)"""

    choices = get_boards()

    default_val = choices[0][1] if choices else ""

    # "trs"가 choices에 있으면 등록 대상 기본값으로 설정

    trs_default = "trs" if any(c[1] == "trs" for c in choices) else default_val

    return gr.update(choices=choices, value=default_val), gr.update(choices=choices, value=trs_default)





def on_search_click(bo_table, stx, sort, page_rows, page=1):

    """그누보드 글을 검색하여 JSON 스트링과 요약 정보를 반환합니다. (동기식)"""

    import json

    if not bo_table:

        return "[]", '<h4>게시판을 선택해 주세요.</h4>', 1, 1, "1 / 1 페이지"

        

    try:

        page_val = int(page)

    except:

        page_val = 1

        

    res = search_posts(

        bo_table=bo_table,

        stx=stx,

        sort=sort,

        page_rows=page_rows,

        page=page_val

    )

    

    posts = res["posts"]

    total = res["total_count"]

    max_page = res["max_page"]

    cur_page = res["page"]

    

    posts_json = json.dumps(posts, ensure_ascii=False)

    

    summary_html = f"""

    <h4>검색 결과: <span style="color:#3182ce; font-weight:bold;">{total:,}</span>건 <span style="color:#718096; font-size:0.8em; font-weight:normal; margin-left:10px;">({cur_page} / {max_page} 페이지)</span></h4>

    <small style="color:#718096;">왼쪽의 <b>☰ 핸들</b>을 드래그하여 병합 순서를 변경하세요.</small>

    """

    

    page_text = f"{cur_page} / {max_page} 페이지"

    

    return posts_json, summary_html, cur_page, max_page, page_text





def on_prev_page(bo_table, stx, sort, page_rows, cur_page, max_page):

    try:

        page = int(cur_page) - 1

        if page < 1:

            page = 1

    except:

        page = 1

    return on_search_click(bo_table, stx, sort, page_rows, page)





def on_next_page(bo_table, stx, sort, page_rows, cur_page, max_page):

    try:

        page = int(cur_page) + 1

        if page > int(max_page):

            page = int(max_page)

    except:

        page = 1

    return on_search_click(bo_table, stx, sort, page_rows, page)





def on_merge_to_translator(bo_table, selected_ids_str):

    """선택된 글들을 병합하여 번역기 원문으로 바로 로딩합니다. (동기식)"""

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

    line_count = normalized_text.count('\n') + 1

    

    info_msg = f"📂 **그누보드 가져오기 ({bo_table})**  ·  {len(wr_ids)}개 글 병합  ·  {char_count:,}자  ·  {line_count:,}줄"

    

    # Fetch posts metadata to return to state
    posts_meta = get_posts_details(bo_table, wr_ids)
    posts_metadata_payload = {
        "bo_table": bo_table,
        "wr_ids": wr_ids,
        "posts": posts_meta
    }
    
    return info_msg, normalized_text, normalized_text, gr.update(interactive=True), gr.update(interactive=True), posts_metadata_payload





def on_merge_download(bo_table, selected_ids_str):

    """선택된 글들을 병합하여 txt 파일로 다운로드합니다. (동기식)"""

    if not bo_table or not selected_ids_str or not selected_ids_str.strip():

        return None

        

    wr_ids = [x.strip() for x in selected_ids_str.split(",") if x.strip()]

    

    merged_text = merge_posts_content(bo_table, wr_ids)

    if not merged_text:

        return None

        

    try:

        tmp_dir = os.path.join(os.path.dirname(__file__), "outputs")

        os.makedirs(tmp_dir, exist_ok=True)

        filename = f"merge_{bo_table}_{int(time.time())}.txt"

        filepath = os.path.join(tmp_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:

            f.write(merged_text)

        return filepath

    except Exception as e:

        logger.error(f"Failed to create merge download file: {e}")

        return None





def start_translation(

    file_obj, original_text, source_lang, target_lang, context_size,

    api_url, api_key, glossary_file, temperature, enable_thinking

):

    """

    Start translation as a Gradio generator for live progress updates.

    Uses original_text directly to support all input types (upload, paste, Gnuboard).

    """

    global orchestrator



    if not original_text or not original_text.strip():

        yield "❌ 번역할 원문 텍스트가 비어 있습니다.", 0, "", "", None, ""

        return



    # Setup file path for background processing

    file_path = None

    if file_obj is not None:

        file_path = str(file_obj)

    else:

        # Save original_text to a temp file in outputs directory

        try:

            tmp_dir = os.path.join(os.path.dirname(__file__), "outputs")

            os.makedirs(tmp_dir, exist_ok=True)

            temp_file_path = os.path.join(tmp_dir, "webui_input.txt")

            with open(temp_file_path, "w", encoding="utf-8") as f:

                f.write(original_text)

            file_path = temp_file_path

        except Exception as e:

            yield f"❌ 임시 파일 저장 오류: {e}", 0, "", "", None, ""

            return



    # Setup glossary

    glossary_path = ""

    if glossary_file is not None:

        glossary_path = str(glossary_file)

    else:

        # Fallback to default glossary if it exists

        default_glossary = "D:\\DeepScribe\\word_Jp2Kr.csv"

        if os.path.exists(default_glossary):

            glossary_path = default_glossary



    # Run translation in background thread

    result_holder = {"text": ""}



    try:

        ctx_size = int(context_size)

    except Exception:

        try:

            clean_str = "".join(c for c in str(context_size) if c.isdigit())

            ctx_size = int(clean_str)

        except Exception:

            ctx_size = 16384



    def run_translation():

        result_holder["text"] = orchestrator.translate_file(

            file_path=file_path,

            source_lang=source_lang,

            target_lang=target_lang,

            context_size=ctx_size,

            api_url=api_url if api_url else "",

            api_key=api_key if api_key else "",

            glossary_path=glossary_path,

            temperature=float(temperature),

            enable_thinking=enable_thinking,

        )



    thread = threading.Thread(target=run_translation, daemon=True)

    thread.start()



    # Poll progress and yield updates (no character limits)

    while thread.is_alive():

        prog = orchestrator.get_progress()

        status_icon = {

            TranslationStatus.READING: "📖",

            TranslationStatus.CHUNKING: "✂️",

            TranslationStatus.TRANSLATING: "🔄",

            TranslationStatus.POSTPROCESSING: "✨",

        }.get(prog.status, "⏳")



        time_info = format_time_info(prog)

        time_suffix = f" ({time_info})" if time_info else ""

        progress_text = f"{status_icon} {prog.message}{time_suffix}"

        ratio = int(prog.progress_ratio * 100)



        yield (

            progress_text,

            ratio,

            prog.original_text or "",

            prog.translated_text or "",

            None,

            prog.reasoning_text or "",

        )

        time.sleep(0.2)



    # Final result

    thread.join()

    prog = orchestrator.get_progress()



    if prog.status == TranslationStatus.ERROR:

        yield f"❌ 오류: {prog.error}", 0, prog.original_text or "", "", None, prog.reasoning_text or ""

        return



    if prog.status == TranslationStatus.CANCELLED:

        yield (

            "⚠️ 번역이 취소되었습니다.", int(prog.progress_ratio * 100),

            prog.original_text or "", prog.translated_text or "", None,

            prog.reasoning_text or "",

        )

        return



    time_info = format_time_info(prog)

    time_suffix = f", {time_info}" if time_info else ""

    yield (

        f"✅ 번역 완료! ({prog.total_chunks}개 청크, {len(result_holder['text']):,}자{time_suffix})",

        100,

        prog.original_text or "",

        result_holder["text"],

        prog.download_path if prog.download_path else None,

        prog.reasoning_text or "",

    )





def on_register_each_to_trs(
    bo_table, selected_ids_str,
    source_lang, target_lang, context_size,
    api_url, api_key, glossary_file, temperature,
    enable_thinking
):
    """선택된 글들을 각각 순차적으로 번역한 후 'trs' 게시판에 개별적으로 등록합니다."""
    if not bo_table:
        yield "❌ 오류: 게시판을 선택해야 합니다.", 0, "❌ 오류: 게시판을 선택해야 합니다.", "", ""
        return
    if not selected_ids_str or not selected_ids_str.strip():
        yield "❌ 오류: 선택된 게시글이 없습니다. 테이블에서 체크박스를 선택해 주세요.", 0, "❌ 오류: 선택된 게시글이 없습니다. 테이블에서 체크박스를 선택해 주세요.", "", ""
        return

    wr_ids = [x.strip() for x in selected_ids_str.split(",") if x.strip()]

    raw_posts = get_posts_details(bo_table, wr_ids)
    if not raw_posts:
        yield "❌ 오류: 선택된 게시글의 데이터를 가져오지 못했습니다.", 0, "❌ 오류: 선택된 게시글의 데이터를 가져오지 못했습니다.", "", ""
        return

    success_count = 0
    fail_count = 0
    skipped_count = 0
    results_wr_ids = []

    tmp_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(tmp_dir, exist_ok=True)

    total_posts = len(raw_posts)

    for idx, post in enumerate(raw_posts, 1):
        orig_subject = post.get("wr_subject", "")
        orig_content = post.get("wr_content", "")
        source_wr_id = post.get("wr_id")

        base_ratio = (idx - 1) / total_posts

        # 1. 준비
        prep_msg = f"⏳ [{idx}/{total_posts}] '{orig_subject}' (원문 ID: {source_wr_id}) 번역 준비 중..."
        yield prep_msg, int(base_ratio * 100), prep_msg, orig_content, ""

        # 2. 제목 번역
        title_msg = f"⏳ [{idx}/{total_posts}] '{orig_subject}' 제목 번역 중..."
        yield title_msg, int((base_ratio + 0.05 / total_posts) * 100), title_msg, orig_content, ""
        translated_subject = orig_subject
        try:
            client = TranslationClient(
                api_url=api_url if api_url else None,
                api_key=api_key if api_key else None,
            )
            system_prompt = (
                "당신은 소설 번역가입니다. 소설의 소제목이나 장 제목을 장식이나 해설 없이 순수한 한국어 번역 결과만 한 줄로 출력하십시오."
            )
            user_prompt = f"원문 제목: {orig_subject}\n번역된 제목:"
            translated_title_res = client.translate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
            )
            if translated_title_res:
                translated_subject = str(translated_title_res).strip().strip('"').strip("'")
        except Exception as e:
            logger.error(f"Error translating title for post {source_wr_id}: {e}")

        # 3. 본문 번역
        body_msg = f"⏳ [{idx}/{total_posts}] '{orig_subject}' 본문 번역 중..."
        yield body_msg, int((base_ratio + 0.1 / total_posts) * 100), body_msg, orig_content, ""
        translated_content = ""
        temp_file_path = os.path.join(tmp_dir, f"temp_register_{source_wr_id}.txt")

        try:
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(orig_content)

            orchestrator.reset()

            glossary_path = ""
            if glossary_file is not None:
                glossary_path = str(glossary_file)
            else:
                default_glossary_csv = "D:/DeepScribe/word_Jp2Kr.csv"
                if os.path.exists(default_glossary_csv):
                    glossary_path = default_glossary_csv

            try:
                ctx_size = int(context_size)
            except Exception:
                ctx_size = 16384

            result_holder = {"text": ""}
            def run_translation():
                result_holder["text"] = orchestrator.translate_file(
                    file_path=temp_file_path,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    context_size=ctx_size,
                    api_url=api_url if api_url else "",
                    api_key=api_key if api_key else "",
                    glossary_path=glossary_path,
                    temperature=float(temperature),
                    enable_thinking=enable_thinking,
                )

            thread = threading.Thread(target=run_translation, daemon=True)
            thread.start()

            while thread.is_alive():
                prog = orchestrator.get_progress()
                status_icon = {
                    TranslationStatus.READING: "📖",
                    TranslationStatus.CHUNKING: "✂️",
                    TranslationStatus.TRANSLATING: "🔄",
                    TranslationStatus.POSTPROCESSING: "✨",
                }.get(prog.status, "⏳")

                ratio = int(prog.progress_ratio * 100)
                overall_ratio = int((base_ratio + (prog.progress_ratio * 0.8) / total_posts) * 100)
                status_msg = f"⏳ [{idx}/{total_posts}] '{orig_subject}' 본문 번역 중... ({status_icon} 청크 {prog.current_chunk}/{prog.total_chunks} - {ratio}%)"
                yield status_msg, overall_ratio, status_msg, prog.original_text or orig_content, prog.translated_text or ""
                time.sleep(0.5)

            thread.join()

            prog = orchestrator.get_progress()
            if prog.status == TranslationStatus.ERROR:
                raise Exception(prog.error)
            elif prog.status == TranslationStatus.CANCELLED:
                raise Exception("번역 취소됨")

            translated_content = result_holder["text"]

        except Exception as e:
            logger.error(f"Failed to translate content for post {source_wr_id}: {e}")
            fail_count += 1
            fail_msg = f"❌ [{idx}/{total_posts}] '{orig_subject}' 번역 실패: {str(e)}"
            yield fail_msg, int((idx / total_posts) * 100), fail_msg, orig_content, ""
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass
            continue

        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

        # 4. 'trs' 게시판 등록
        reg_msg = f"⏳ [{idx}/{total_posts}] '{orig_subject}' 번역 완료! 'trs' 게시판 등록 중..."
        yield reg_msg, int((base_ratio + 0.95 / total_posts) * 100), reg_msg, orig_content, translated_content

        try:
            wr_name = post.get("wr_name") or "최고관리자"
            wr_datetime = post.get("wr_datetime")
            ca_name = post.get("ca_name") or "번역"
            wr_option = post.get("wr_option") or "html1"
            wr_link1 = f"http://localhost/bbs/board.php?bo_table={bo_table}&wr_id={source_wr_id}"

            target_board = "trs"

            final_subject = translated_subject
            if orig_subject:
                if wr_name:
                    final_subject = f"{translated_subject} - ({orig_subject} - {wr_name})"
                else:
                    final_subject = f"{translated_subject} - ({orig_subject})"

            final_content = translated_content.replace("\n", "<br>\n") if translated_content else ""

            res = register_post_to_gnuboard(
                bo_table=target_board,
                subject=final_subject,
                content=final_content,
                ca_name=ca_name,
                mb_id="admin",
                wr_name=wr_name,
                wr_datetime=wr_datetime,
                wr_option=wr_option,
                wr_1="",
                wr_link1=wr_link1,
            )

            if res and str(res).startswith("skipped:"):
                skipped_count += 1
                skip_msg = f"⚠️ [{idx}/{total_posts}] '{orig_subject}' 중복 등록 스킵됨."
                yield skip_msg, int((idx / total_posts) * 100), skip_msg, orig_content, translated_content
            else:
                success_count += 1
                res_msg = str(res).split(":")
                wr_id = res_msg[1] if len(res_msg) > 1 else res
                results_wr_ids.append(wr_id)
                success_msg = f"✅ [{idx}/{total_posts}] '{orig_subject}' 'trs' 게시판 등록 성공! (새 ID: {wr_id})"
                yield success_msg, int((idx / total_posts) * 100), success_msg, orig_content, translated_content

        except Exception as e:
            logger.error(f"Error registering translated post {source_wr_id} to trs: {e}")
            fail_count += 1
            fail_reg_msg = f"❌ [{idx}/{total_posts}] '{orig_subject}' 등록 실패: {str(e)}"
            yield fail_reg_msg, int((idx / total_posts) * 100), fail_reg_msg, orig_content, translated_content

    summary_msg = f"📋 **'trs' 게시판 각각 등록 결과** · "
    parts = []
    if success_count > 0:
        parts.append(f"성공: {success_count}개 (ID: {', '.join(results_wr_ids)})")
    if skipped_count > 0:
        parts.append(f"스킵(중복): {skipped_count}개")
    if fail_count > 0:
        parts.append(f"실패: {fail_count}개")

    summary_msg += "  |  ".join(parts)
    yield summary_msg, 100, summary_msg, "", ""





def cancel_translation():

    """Cancel the running translation."""

    global orchestrator

    if orchestrator:

        orchestrator.cancel()

        return "⚠️ 취소 요청 전송..."

    return "실행 중인 번역이 없습니다."





def check_active_translation():

    """

    On app load (F5 refresh), check if a background translation is active.

    If active, it automatically reconnects and updates the progress.

    """

    global orchestrator

    if orchestrator is None:

        # Default state

        yield (

            "", 0, "", "", None, "",

            gr.update(interactive=False)

        )

        return



    prog = orchestrator.get_progress()

    status_icon = {

        TranslationStatus.READING: "📖",

        TranslationStatus.CHUNKING: "✂️",

        TranslationStatus.TRANSLATING: "🔄",

        TranslationStatus.POSTPROCESSING: "✨",

    }



    is_running = prog.status in [

        TranslationStatus.READING,

        TranslationStatus.CHUNKING,

        TranslationStatus.TRANSLATING,

        TranslationStatus.POSTPROCESSING,

    ]



    if is_running:

        while True:

            prog = orchestrator.get_progress()

            current_is_running = prog.status in [

                TranslationStatus.READING,

                TranslationStatus.CHUNKING,

                TranslationStatus.TRANSLATING,

                TranslationStatus.POSTPROCESSING,

            ]



            icon = status_icon.get(prog.status, "⏳")

            time_info = format_time_info(prog)

            time_suffix = f" ({time_info})" if time_info else ""

            progress_msg = f"{icon} {prog.message}{time_suffix}"

            ratio = int(prog.progress_ratio * 100)



            yield (

                progress_msg,

                ratio,

                prog.original_text or "",

                prog.translated_text or "",

                None,

                prog.reasoning_text or "",

                gr.update(interactive=False)

            )



            if not current_is_running:

                break

            time.sleep(1.0)



    # Finished or recovered state

    prog = orchestrator.get_progress()

    if prog.status == TranslationStatus.COMPLETED:

        time_info = format_time_info(prog)

        time_suffix = f", {time_info}" if time_info else ""

        yield (

            f"✅ 번역 완료! ({prog.total_chunks}개 청크, {len(prog.translated_text):,}자{time_suffix})",

            100,

            prog.original_text or "",

            prog.translated_text or "",

            prog.download_path if prog.download_path else None,

            prog.reasoning_text or "",

            gr.update(interactive=True)

        )

    elif prog.status == TranslationStatus.ERROR:

        yield (

            f"❌ 오류: {prog.error}",

            0,

            prog.original_text or "",

            "",

            None,

            prog.reasoning_text or "",

            gr.update(interactive=True)

        )

    elif prog.status == TranslationStatus.CANCELLED:

        yield (

            "⚠️ 번역이 취소되었습니다.",

            int(prog.progress_ratio * 100),

            prog.original_text or "",

            prog.translated_text or "",

            None,

            prog.reasoning_text or "",

            gr.update(interactive=True)

        )

    else:

        # Idle

        can_translate = bool(prog.original_text)

        yield (

            "",

            0,

            prog.original_text or "",

            prog.translated_text or "",

            None,

            prog.reasoning_text or "",

            gr.update(interactive=can_translate)

        )





def reset_ui():

    """Reset the translation UI components to their initial state."""

    global orchestrator

    if orchestrator:

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





def on_register_to_gnuboard(bo_table, subject, translated_content, gb_selected_posts, request: gr.Request):

    """번역된 내용을 그누보드 게시판에 등록합니다."""

    if not bo_table:

        return "❌ 오류: 대상 게시판을 선택해주세요."

    if not subject or not subject.strip():

        return "❌ 오류: 제목을 입력해주세요."

    if not translated_content or not translated_content.strip():

        return "❌ 오류: 번역된 내용이 없습니다. 먼저 번역을 실행해주세요."



    try:

        # HTML 형식으로 변환 (줄바꿈 -> <br>)

        html_content = translated_content.replace("\n", "<br>\n")

        # Prepare metadata if we have a source post
        wr_name = "최고관리자"
        wr_datetime = None
        wr_link1 = ""
        ca_name = "번역"
        wr_1 = "" # 기본값은 빈 문자열로 초기화
        
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
            # 'trs' 게시판이 아닐 경우에만 'translated' 값을 wr_1에 설정
            if bo_table != 'trs':
                wr_1 = "translated" # 원문이 있을 때만 'translated' 설정

        res = register_post_to_gnuboard(
            bo_table=bo_table,
            subject=subject.strip(),
            content=html_content,
            ca_name=ca_name,
            mb_id="admin",
            wr_name=wr_name,
            wr_datetime=wr_datetime,
            wr_option="html1",
            wr_1=wr_1, # 조건에 따라 설정된 wr_1 값 전달
            wr_link1=wr_link1
        )

        

        if res and str(res).startswith("updated:"):

            wr_id = str(res).split(":")[1]

            return f"✅ 게시판 **'{bo_table}'**에 성공적으로 업데이트! (글 ID: {wr_id})"

        elif res and str(res).startswith("skipped:"):

            wr_id = str(res).split(":")[1]

            return f"ℹ️ 동일한 글이 이미 존재합니다. (글 ID: {wr_id})"

        else:
            # res can be "inserted:wr_id"
            res_msg = str(res).split(":")
            wr_id = res_msg[1] if len(res_msg) > 1 else res
            return f"✅ 게시판 **'{bo_table}'**에 성공적으로 등록! (글 ID: {wr_id})"

    except Exception as e:

        logger.error(f"Error registering to gnuboard: {e}")

        return f"❌ 등록 중 오류가 발생했습니다: {str(e)}"





def on_translation_complete(translated_text, file_obj, gb_selected_posts, api_url, api_key):

    """번역 완료 후 그누보드 등록 버튼을 활성화하고 기본 제목을 설정합니다."""

    import datetime as dt

    if not translated_text or not translated_text.strip():

        return gr.update(interactive=False), gr.update()



    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    if gb_selected_posts and gb_selected_posts.get("posts"):
        posts = gb_selected_posts["posts"]
        first_post = posts[0]
        original_subject = first_post.get("wr_subject", "")
        original_writer = first_post.get("wr_name", "")
        
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
            user_prompt = f"원문 제목: {original_subject}\n번역된 제목:"
            
            llm_res = title_client.translate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3
            )
            if llm_res:
                translated_title = llm_res.strip().strip('"').strip("'")
        except Exception as e:
            logger.error(f"Error translating title in completion callback: {e}")
            
        default_subject = f"{translated_title} ({original_subject}) - {original_writer}"
    elif file_obj:
        filename_no_ext = os.path.splitext(os.path.basename(str(file_obj)))[0]
        default_subject = f"번역 완료 - {filename_no_ext}"
    else:
        default_subject = f"번역 완료 - {now_str}"



    return gr.update(interactive=True), gr.update(value=default_subject)





def run_onomatopoeia_extraction(text, api_url, api_key):

    """Scan text, extract unregistered candidates, queue to DB, and return feedback."""

    if not text or not text.strip():

        return "❌ 오류: 분석할 텍스트가 비어 있습니다.", gr.update()

    

    # Update background worker's LLM credentials dynamically

    if hasattr(orchestrator, 'onomatopoeia_worker') and orchestrator.onomatopoeia_worker:

        if api_url:

            orchestrator.onomatopoeia_worker.client.api_url = api_url.strip()

        if api_key:

            orchestrator.onomatopoeia_worker.client.api_key = api_key.strip()



    try:

        count = orchestrator.extract_and_queue_onomatopoeia(text)

        

        # Get updated choices for the dropdown

        db = OnomatopoeiaDB(orchestrator.onomatopoeia_db_path)

        pending = db.get_pending_review()

        choices = [item["word"] for item in pending]

        

        total_pending_extraction = len(db.get_pending_extraction())

        

        if count == 0:

            msg = "🔍 분석 완료: 원문에서 새로 제안할 미등록 의성어/의태어가 발견되지 않았습니다."

        else:

            msg = (

                f"✅ **{count}개**의 새로운 의성어/의태어 후보를 원문에서 추출하여 DB 큐에 등록했습니다.\n\n"

                f"현재 검수 대기 중(번역 작성 완료): **{len(choices)}개**\n"

                f"백그라운드 LLM 워크스레드가 사전 항목 자동 작성을 시작했습니다 (남은 대기: {total_pending_extraction}개).\n\n"

                f"**'의성어 사전 관리' 탭으로 이동**하여 생성된 번역 예시를 확인하고 승인해 주세요!"

            )

        

        return msg, gr.update(choices=choices, value=choices[0] if choices else None)

    except Exception as e:

        logger.error(f"Error during onomatopoeia extraction from text: {e}")

        return f"❌ 오류 발생: {e}", gr.update()





def select_word_from_dict_view(file_path, evt: gr.SelectData):

    if not evt.value:
        return (gr.update(), gr.update()) + (gr.update(),) * 6

    word = evt.value
    details_tuple = load_registered_word_details(word, file_path)
    
    # Return: tab selection, dropdown value, and the 6 detail fields
    return (gr.update(selected="tab_registered"), gr.update(value=word)) + details_tuple





def get_initial_table_html():

    return """

    <style>

        .gb-table { width: 100%; border-collapse: collapse; margin-top: 10px; background-color: var(--diff-bg, #fff); }

        .gb-table th, .gb-table td { padding: 10px; border: 1px solid var(--diff-border-color, #dee2e6); text-align: left; }

        .gb-table th { background-color: var(--diff-gutter-bg, #f8f9fa); color: var(--body-text-color); font-weight: bold; }

        .gb-table tr:hover { background-color: var(--diff-hover-bg, #f1f3f5); }

        .drag-handle { cursor: grab; color: #adb5bd; font-size: 1.2rem; padding: 5px; user-select: none; }

        .drag-handle:active { cursor: grabbing; }

        .sortable-ghost { opacity: 0.4; background-color: #e9ecef; }

        .sortable-drag { background-color: #fff; box-shadow: 0 5px 15px rgba(0,0,0,0.15); }

        #gnuboard-table-container { margin-top: 15px; }

        #gnuboard-control-row { align-items: center; margin-top: 10px; margin-bottom: 10px; }

    </style>

    <div class="table-responsive" id="gnuboard-table-container">

        <table class="gb-table">

            <thead>

                <tr>

                    <th style="text-align:center; width:60px;">이동</th>

                    <th style="text-align:center; width:50px;"><input type="checkbox" id="gb-toggle-all" onclick="gbToggleAll(this)"></th>

                    <th style="text-align:center; width:120px;">분류</th>

                    <th>제목</th>

                    <th style="width:120px;">작성자</th>

                    <th style="width:150px;">작성일</th>

                </tr>

            </thead>

            <tbody id="gb-table-body">

                <tr>

                    <td colspan="6" style="text-align:center; color:#a0aec0; padding:30px;">게시판을 선택하고 검색 버튼을 눌러주세요.</td>

                </tr>

            </tbody>

        </table>

    </div>

    

    <script type="text/plain" id="gb-table-js">

    (function() {

        if (window.__gbTableInterval) {

            clearInterval(window.__gbTableInterval);

        }

        

        console.log("Gnuboard Table JS Initializing...");

        

        window.gbToggleAll = function(source) {

            const checkboxes = document.querySelectorAll('input[name="gb_chk_wr_id"]');

            checkboxes.forEach((cb) => {

                cb.checked = source.checked;

            });

            updateSelectedIds();

        };

        

        window.updateSelectedIds = function() {

            const checkboxes = document.querySelectorAll('input[name="gb_chk_wr_id"]');

            const selected = [];

            const rows = document.querySelectorAll('#gb-table-body tr');

            rows.forEach((row) => {

                const cb = row.querySelector('input[name="gb_chk_wr_id"]');

                if (cb && cb.checked) {

                    selected.push(cb.value);

                }

            });

            

            const targetEl = document.querySelector('#gb-selected-ids textarea, #gb-selected-ids input');

            if (targetEl) {

                targetEl.value = selected.join(',');

                targetEl.dispatchEvent(new Event('input', { bubbles: true }));

            }

        };



        const renderTable = (jsonEl, tbody) => {

            const jsonVal = jsonEl.value || "[]";

            if (jsonVal === tbody.__lastJson) {

                if (window.Sortable && tbody.querySelector('tr[data-id]') && !tbody.__sortableInitialized) {

                    initSortable(tbody);

                }

                return;

            }

            tbody.__lastJson = jsonVal;

            

            let posts = [];

            try {

                posts = JSON.parse(jsonVal);

            } catch (e) {

                console.error("JSON parse error: ", e);

                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:red; padding:30px;">데이터 파싱 에러</td></tr>';

                return;

            }

            

            if (!posts || posts.length === 0) {

                tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#a0aec0; padding:30px;">검색 결과가 없습니다.</td></tr>';

                const masterCb = document.getElementById('gb-toggle-all');

                if (masterCb) masterCb.checked = false;

                return;

            }

            

            let html = '';

            posts.forEach((post) => {

                const wr_id = post.wr_id;

                const ca_name = post.ca_name || "";

                const wr_subject = post.wr_subject || "";

                const wr_name = post.wr_name || "";

                const wr_datetime = post.wr_datetime || "";

                

                html += `

                    <tr data-id="${wr_id}">

                        <td style="text-align:center;"><span class="drag-handle" style="user-select:none;">☰</span></td>

                        <td style="text-align:center;"><input type="checkbox" name="gb_chk_wr_id" value="${wr_id}" class="form-check-input" onchange="updateSelectedIds()"></td>

                        <td style="text-align:center; color:#718096; font-size:0.9em;">${ca_name}</td>

                        <td style="font-weight:500; word-break:break-all;">${wr_subject}</td>

                        <td>${wr_name}</td>

                        <td style="color:#718096; font-size:0.9em;">${wr_datetime}</td>

                    </tr>

                `;

            });

            

            tbody.innerHTML = html;

            tbody.__sortableInitialized = false;

            

            const masterCb = document.getElementById('gb-toggle-all');

            if (masterCb) masterCb.checked = false;

            

            if (window.Sortable) {

                initSortable(tbody);

            }

            

            updateSelectedIds();

        };



        const initSortable = (tbody) => {

            if (tbody.__sortableInstance) {

                try {

                    tbody.__sortableInstance.destroy();

                } catch(e) {}

            }

            tbody.__sortableInstance = Sortable.create(tbody, {

                handle: '.drag-handle',

                animation: 150,

                ghostClass: 'sortable-ghost',

                dragClass: 'sortable-drag',

                onEnd: function() {

                    const rows = tbody.querySelectorAll('tr[data-id]');

                    const newOrderIds = [];

                    rows.forEach(row => {

                        newOrderIds.push(row.getAttribute('data-id'));

                    });

                    

                    const jsonEl = document.querySelector('#gb-posts-json textarea, #gb-posts-json input');

                    if (jsonEl) {

                        try {

                            const posts = JSON.parse(jsonEl.value || "[]");

                            const postsMap = {};

                            posts.forEach(p => { postsMap[p.wr_id] = p; });

                            

                            const reorderedPosts = [];

                            newOrderIds.forEach(id => {

                                if (postsMap[id]) {

                                    reorderedPosts.push(postsMap[id]);

                                }

                            });

                            

                            const newJsonVal = JSON.stringify(reorderedPosts);

                            tbody.__lastJson = newJsonVal;

                            jsonEl.value = newJsonVal;

                            jsonEl.dispatchEvent(new Event('input', { bubbles: true }));

                        } catch(e) {

                            console.error("Error reordering posts JSON:", e);

                        }

                    }

                    

                    updateSelectedIds();

                }

            });

            tbody.__sortableInitialized = true;

            console.log("Sortable successfully bound to table body.");

        };

        

        window.__gbTableInterval = setInterval(() => {

            const jsonEl = document.querySelector('#gb-posts-json textarea, #gb-posts-json input');

            const tbody = document.getElementById('gb-table-body');

            

            if (jsonEl && tbody) {

                if (!tbody.__renderInitialized) {

                    tbody.__renderInitialized = true;

                    jsonEl.addEventListener('input', () => renderTable(jsonEl, tbody));

                }

                renderTable(jsonEl, tbody);

            }

        }, 250);

    })();

    </script>

    <img src="does-not-exist" onerror="

        if (!window.Sortable) {

            var s = document.createElement('script');

            s.src = 'https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js';

            s.onload = function() { console.log('SortableJS loaded from CDN'); eval(document.getElementById('gb-table-js').textContent); };

            s.onerror = function() { console.error('Failed to load SortableJS CDN'); eval(document.getElementById('gb-table-js').textContent); };

            document.head.appendChild(s);

        } else {

            eval(document.getElementById('gb-table-js').textContent);

        }

    " style="display:none;"/>

    """





# ─── Gradio UI ──────────────────────────────────────────────────────────



def create_ui() -> gr.Blocks:

    """Build and return the Gradio Blocks interface."""



    with gr.Blocks(

        title="Novel Translator — DeepScribe",

    ) as app:



        # ── State ──

        original_text_state = gr.State("")

        gb_posts_json = gr.Textbox(visible=True, value="[]", elem_id="gb-posts-json")

        gb_selected_ids = gr.Textbox(visible=True, value="", elem_id="gb-selected-ids")

        gb_current_page = gr.State(1)

        gb_max_page = gr.State(1)
        onomatopoeia_db_path_state = gr.State(orchestrator.onomatopoeia_db_path)

        gb_selected_posts_state = gr.State(None)
        dict_file_path = gr.State(orchestrator.onomatopoeia_csv)



        with gr.Tabs() as main_tabs:

            with gr.Tab("🔌 번역 실행 (Translate)"):



                # ── Header ──

                with gr.Column(elem_id="app-header"):

                    gr.Markdown("# 📖 Novel Translator")

                    gr.Markdown("로컬 LLM 기반 소설 번역기 — 대용량 텍스트 스마트 청킹 & 맥락 유지 번역")



                # ── Input Section: File Upload OR Paste OR Gnuboard ──

                with gr.Row():

                    # Left: Input methods (tabs)

                    with gr.Column(scale=3):

                        with gr.Tabs():

                            with gr.Tab("📄 파일 업로드"):

                                file_input = gr.File(

                                    label="txt 파일을 드래그하거나 클릭하여 업로드",

                                    file_types=[".txt"],

                                    type="filepath",

                                    elem_id="file-input",

                                )

                            with gr.Tab("📋 텍스트 붙여넣기"):

                                paste_input = gr.Textbox(

                                    label="원문 텍스트를 여기에 붙여넣기 (Ctrl+V)",

                                    placeholder="번역할 소설 텍스트를 직접 붙여넣으세요...",

                                    lines=8,

                                    elem_id="paste-input",

                                )

                            with gr.Tab("📂 그누보드 게시판"):

                                with gr.Row():

                                    gb_board_select = gr.Dropdown(

                                        choices=[],

                                        label="게시판 선택",

                                        value="",

                                        interactive=True,

                                        scale=2

                                    )

                                    gb_search_keyword = gr.Textbox(

                                        label="검색어",

                                        placeholder="검색어 입력 (빈칸 조회 가능)",

                                        value="",

                                        scale=3

                                    )

                                    gb_sort_select = gr.Dropdown(

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

                                            gb_btn_register_each = gr.Button("📝 각각 등록", variant="secondary", size="sm")

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

                            )



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



                        enable_thinking = gr.Checkbox(

                            value=False,

                            label="🧠 모델 사고 과정(Thinking) 활성화",

                            info="활성화 시 추론 과정을 거쳐 품질이 향상될 수 있으나 번역 속도가 느려집니다. (비활성화 시 속도가 대폭 향상됨)",

                        )



                # ── Advanced Settings (Collapsed) ──

                with gr.Accordion("⚙️ 고급 설정", open=False):

                    with gr.Row():

                        api_url = gr.Textbox(

                            label="API URL",

                            value="",

                            placeholder="http://127.0.0.1:8081/v1/chat/completions (기본값)",

                            info="비워두면 settings.json 또는 기본값 사용",

                        )

                        api_key = gr.Textbox(

                            label="API Key",

                            value="",

                            placeholder="비워두면 settings.json 또는 기본값 사용",

                            type="password",

                        )

                    with gr.Row():

                        default_glossary = "D:\\\\DeepScribe\\\\word_Jp2Kr.csv"

                        glossary_file = gr.File(

                            label="📕 용어 사전 (CSV/JSON, 선택사항)",

                            file_types=[".csv", ".json", ".txt"],

                            type="filepath",

                            value=default_glossary if os.path.exists(default_glossary) else None,

                        )

                        with gr.Column():

                            btn_test = gr.Button(

                                "🔌 서버 연결 테스트",

                                elem_id="btn-test",

                                size="sm",

                            )

                            test_result = gr.Markdown("")



                # ── Action Buttons ──

                with gr.Row():

                    btn_translate = gr.Button(

                        "▶️  번역 시작",

                        elem_id="btn-translate",

                        variant="primary",

                        interactive=False,

                        scale=3,

                    )

                    btn_extract = gr.Button(

                        "🔍 신규 의성어 추출",

                        elem_id="btn-extract",

                        variant="secondary",

                        interactive=False,

                        scale=2,

                    )

                    btn_cancel = gr.Button(

                        "⏹️ 취소",

                        elem_id="btn-cancel",

                        variant="stop",

                        scale=1,

                    )

                    btn_reset = gr.Button(

                        "🔄 화면 초기화",

                        elem_id="btn-reset",

                        variant="secondary",

                        scale=1,

                    )



                # ── Progress ──

                progress_text = gr.Markdown("", elem_id="progress-status")

                progress_bar = gr.Slider(

                    minimum=0, maximum=100, value=0,

                    label="진행률 (%)", interactive=False,

                    elem_id="progress-bar",

                )



                # ── Side-by-side Viewer ──

                gr.Markdown("### 📖 원문 / 번역문 대조 뷰어")

                with gr.Row():

                    btn_copy_original = gr.Button("📋 원문 복사", size="sm", elem_id="btn-copy-orig")

                    btn_copy_translated = gr.Button("📋 번역문 복사", size="sm", elem_id="btn-copy-trans")

                

                # Hidden textboxes to hold raw data

                viewer_original = gr.Textbox(

                    show_label=False,

                    interactive=False,

                    elem_id="viewer-original",

                    visible=True,

                    lines=2,

                )

                viewer_translated = gr.Textbox(

                    show_label=False,

                    interactive=False,

                    elem_id="viewer-translated",

                    visible=True,

                    lines=2,

                )



                # Modern IDE Diff View HTML (with autoscroll)

                diff_viewer_html = gr.HTML(

                    value="""

                    <div id="diff-view-wrapper">

                        <div class="diff-header-row">

                            <div class="diff-header-col">원문 (Original)</div>

                            <div class="diff-header-col">번역문 (Translated)</div>

                        </div>

                        <div id="diff-view-container">

                            <div class="diff-placeholder">소설 텍스트를 불러오면 여기에 대조 뷰어가 표시됩니다.</div>

                        </div>

                    </div>

                    

                    <script type="text/plain" id="diff-view-js">

                    (function() {

                        if (window.__diffViewerInterval) {

                            clearInterval(window.__diffViewerInterval);

                        }

                        

                        console.log("Diff Viewer JS Initializing...");

                        

                        const escapeHtml = (text) => {

                            return text

                                .replace(/&/g, "&amp;")

                                .replace(/</g, "&lt;")

                                .replace(/>/g, "&gt;")

                                .replace(/"/g, "&quot;")

                                .replace(/'/g, "&#039;");

                        };

                        

                        const updateDiff = () => {

                            const origEl = document.querySelector('#viewer-original textarea, #viewer-original input');

                            const transEl = document.querySelector('#viewer-translated textarea, #viewer-translated input');

                            const container = document.getElementById('diff-view-container');

                            

                            if (!origEl || !transEl || !container) return;

                            

                            const origText = origEl.value || "";

                            const transText = transEl.value || "";

                            

                            if (origText === container.__lastOrig && transText === container.__lastTrans) {

                                return;

                            }

                            

                            container.__lastOrig = origText;

                            container.__lastTrans = transText;

                            

                            if (!origText.trim() && !transText.trim()) {

                                container.innerHTML = '<div class="diff-placeholder">소설 텍스트를 불러오면 여기에 대조 뷰어가 표시됩니다.</div>';

                                return;

                            }

                            

                            const origLines = origText.split('\\n');

                            const transLines = transText.split('\\n');

                            const maxLines = Math.max(origLines.length, transLines.length);

                            

                            let html = '';

                            for (let i = 0; i < maxLines; i++) {

                                const origLine = i < origLines.length ? origLines[i] : "";

                                const transLine = i < transLines.length ? transLines[i] : "";

                                

                                const origNum = i < origLines.length ? (i + 1) : "";

                                const transNum = i < transLines.length ? (i + 1) : "";

                                

                                const displayOrig = origLine || '\\u200B';

                                const displayTrans = transLine || '\\u200B';

                                

                                const isTranslated = !!transLine.trim();

                                const rowClass = isTranslated ? 'diff-row translated-row' : 'diff-row untranslated-row';

                                

                                html += `

                                    <div class="${rowClass}" data-line="${i + 1}">

                                        <div class="diff-line-num diff-original-num">${origNum}</div>

                                        <div class="diff-line-content diff-original-content">${escapeHtml(displayOrig)}</div>

                                        <div class="diff-line-num diff-translated-num">${transNum}</div>

                                        <div class="diff-line-content diff-translated-content">${escapeHtml(displayTrans)}</div>

                                    </div>

                                `;

                            }

                            

                            container.innerHTML = html;

                            

                            // Smoothly scroll to the latest translated row

                            const translatedRows = container.querySelectorAll('.translated-row');

                            if (translatedRows.length > 0) {

                                const lastRow = translatedRows[translatedRows.length - 1];

                                lastRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

                            }

                        };

                        

                        window.__diffViewerInterval = setInterval(updateDiff, 250);

                    })();

                    </script>

                    

                    <img src="does-not-exist" onerror="eval(document.getElementById('diff-view-js').textContent)" style="display:none;"/>

                    """,

                    elem_id="diff-viewer-component",

                )



                # ── Thinking Process (collapsible) ──

                with gr.Accordion("🧠 모델 사고 과정 (Thinking)", open=False):

                    viewer_reasoning = gr.Textbox(

                        label="모델이 번역하면서 생각하는 과정 (참고용)",

                        lines=12,

                        interactive=False,

                        elem_id="viewer-reasoning",

                    )



                # ── Download ──

                download_file = gr.File(

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



            with gr.Tab("📕 의성어 사전 관리 (Dictionary Manager)"):

                gr.Markdown("### 🔍 미등록 신규 의성어/의태어 검수")

                gr.Markdown("소설 번역 중에 MeCab/Regex가 자동으로 추출하여 백엔드 LLM이 사전 데이터를 임시 작성한 항목들입니다. 승인 시 번역 사전에 자동 반영됩니다.")

                

                with gr.Row():

                    # Left column: Edit/Delete or Review tabs

                    with gr.Column(scale=2):

                        with gr.Tabs() as edit_tabs:

                            with gr.Tab("📥 신규 검수 대기", id="tab_pending"):

                                pending_word_dropdown = gr.Dropdown(

                                    choices=[],

                                    label="📥 검수 대기 단어 선택",

                                    interactive=True,

                                )

                                btn_refresh_pending = gr.Button("🔄 대기 목록 새로고침", size="sm")

                                

                                gr.Markdown("#### 📝 신규 번역 검수 및 편집")

                                word_input = gr.Textbox(label="원어 (Japanese)", interactive=False)

                                suggested_translation_input = gr.Textbox(label="추천 번역 (Korean)")

                                notes_input = gr.Textbox(label="문맥 설명 (Notes)")

                                example_source_input = gr.Textbox(label="원문 문장 (Example Source)")

                                example_wrong_input = gr.Textbox(label="오답 번역 예시 (Example Wrong)")

                                example_correct_input = gr.Textbox(label="정답 번역 예시 (Example Correct)")

                                

                                with gr.Row():
                                    btn_approve = gr.Button("✅ 승인 (Approve)", variant="primary", size="sm")
                                    btn_reject = gr.Button("❌ 반려 (Reject)", variant="stop", size="sm")
                                    btn_approve_all = gr.Button("✨ 일괄 승인 (Approve All)", variant="secondary", size="sm")

                                    

                            with gr.Tab("📖 등록된 사전 편집/삭제", id="tab_registered"):

                                registered_word_dropdown = gr.Dropdown(

                                    choices=[],

                                    label="📖 등록된 단어 선택",

                                    interactive=True,

                                )

                                btn_refresh_registered = gr.Button("🔄 등록 목록 새로고침", size="sm")

                                

                                gr.Markdown("#### 📝 등록된 번역 편집")

                                reg_word_input = gr.Textbox(label="원어 (Japanese)", interactive=False)

                                reg_suggested_translation_input = gr.Textbox(label="추천 번역 (Korean)")

                                reg_notes_input = gr.Textbox(label="문맥 설명 (Notes)")

                                reg_example_source_input = gr.Textbox(label="원문 문장 (Example Source)")

                                reg_example_wrong_input = gr.Textbox(label="오답 번역 예시 (Example Wrong)")

                                reg_example_correct_input = gr.Textbox(label="정답 번역 예시 (Example Correct)")

                                

                                with gr.Row():
                                    btn_update = gr.Button("💾 수정 저장 (Save)", variant="primary", size="sm")
                                    btn_delete = gr.Button("🗑️ 삭제 (Delete)", variant="stop", size="sm")

                                    

                        action_status = gr.Markdown("")

                        

                    # Right column: Current Dictionary View

                    with gr.Column(scale=3):
                        with gr.Column():
                            gr.Markdown("#### 📖 현재 등록된 의성어 사전 목록 (페이지네이션)")
                            with gr.Row():
                                dict_search_term = gr.Textbox(label="사전 검색", placeholder="검색할 단어(원어 또는 번역어)를 입력하세요...", scale=4)
                                dict_search_button = gr.Button("🔍 검색", variant="primary", scale=1)
                            
                            with gr.Row(variant="panel"):
                                dict_prev_button = gr.Button("◀ 이전", size="sm")
                                dict_page_info = gr.Markdown("0 / 0 페이지 (총 0개)", elem_id="dict-page-info")
                                dict_next_button = gr.Button("다음 ▶", size="sm")
                            
                            dict_view = gr.DataFrame(
                                headers=["원어", "추천 번역", "설명/문맥", "원어 예문", "기존 번역(오답)", "추천 번역(정답)"],
                                datatype=["str", "str", "str", "str", "str", "str"],
                                row_count=(10, "fixed"),
                                col_count=(6, "fixed"),
                                interactive=False,
                                wrap=True,
                                elem_id="dict-view-df"
                            )
                            
                            # States for pagination
                            dict_page_state = gr.State(1)
                            dict_total_pages_state = gr.State(1)



        # ── Event Wiring ──



        # File upload → show info + store text + enable translate + update viewer_original + update estimate

        file_input.change(

            fn=on_file_upload,

            inputs=[file_input],

            outputs=[file_info, original_text_state, btn_translate, btn_extract],

        ).then(

            fn=lambda text: text,

            inputs=[original_text_state],

            outputs=[viewer_original],

        ).then(

            fn=estimate_chunks,

            inputs=[original_text_state, source_lang, context_size],

            outputs=[chunk_estimate],

        )



        # Paste text → show info + store text + enable translate + update viewer_original + update estimate

        paste_input.change(

            fn=on_paste_text,

            inputs=[paste_input],

            outputs=[file_info, btn_translate, btn_extract],

        )

        paste_input.change(

            fn=lambda t: normalize_input_text(t) if t else "",

            inputs=[paste_input],

            outputs=[original_text_state],

        ).then(

            fn=lambda text: text,

            inputs=[original_text_state],

            outputs=[viewer_original],

        ).then(

            fn=estimate_chunks,

            inputs=[original_text_state, source_lang, context_size],

            outputs=[chunk_estimate],

        )



        # Update chunk estimate when settings change (without race conditions)

        for trigger in [source_lang, context_size]:

            trigger.change(

                fn=estimate_chunks,

                inputs=[original_text_state, source_lang, context_size],

                outputs=[chunk_estimate],

            )



        # Test connection

        btn_test.click(

            fn=test_connection,

            inputs=[api_url, api_key],

            outputs=[test_result],

        )



        # Extract onomatopoeia candidates from raw text

        btn_extract.click(

            fn=run_onomatopoeia_extraction,

            inputs=[original_text_state, api_url, api_key],

            outputs=[progress_text, pending_word_dropdown],

        )



        # Start translation (generator for live updates)

        btn_translate.click(

            fn=start_translation,

            inputs=[

                file_input, original_text_state,

                source_lang, target_lang, context_size,

                api_url, api_key, glossary_file, temperature,

                enable_thinking,

            ],

            outputs=[

                progress_text, progress_bar,

                viewer_original, viewer_translated,

                download_file,

                viewer_reasoning,

            ],

        ).then(

            fn=on_translation_complete,

            inputs=[viewer_translated, file_input, gb_selected_posts_state, api_url, api_key],

            outputs=[btn_reg_save, reg_subject],

        )



        # Cancel

        btn_cancel.click(

            fn=cancel_translation,

            inputs=[],

            outputs=[progress_text],

        )



        # Reset UI for a new translation

        btn_reset.click(

            fn=reset_ui,

            inputs=[],

            outputs=[

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

                gb_selected_posts_state,

            ]

        )



        # Copy to Clipboard Buttons (Client-side JS)

        btn_copy_original.click(

            fn=None,

            inputs=[viewer_original],

            js="(val) => { if(val) { navigator.clipboard.writeText(val); alert('원문이 클립보드에 복사되었습니다.'); } else { alert('복사할 원문이 없습니다.'); } }"

        )

        btn_copy_translated.click(

            fn=None,

            inputs=[viewer_translated],

            js="(val) => { if(val) { navigator.clipboard.writeText(val); alert('번역문이 클립보드에 복사되었습니다.'); } else { alert('복사할 번역문이 없습니다.'); } }"

        )



        # ── Gnuboard Registration Event Wiring ──

        btn_reg_save.click(

            fn=on_register_to_gnuboard,

            inputs=[reg_board_select, reg_subject, viewer_translated, gb_selected_posts_state],

            outputs=[reg_status],

        )



        # ── Dictionary Manager Event Wiring ──

        

        # 1. Refresh pending list dropdown

        btn_refresh_pending.click(

            fn=get_pending_choices,
            inputs=[onomatopoeia_db_path_state],
            outputs=[pending_word_dropdown],

        )

        
        # 2. Select word from dropdown -> fill textboxes

        pending_word_dropdown.change(

            fn=load_pending_word_details,
            inputs=[pending_word_dropdown, onomatopoeia_db_path_state],
            outputs=[

                word_input,

                suggested_translation_input,

                notes_input,

                example_source_input,

                example_wrong_input,

                example_correct_input,

            ]

        )

        

        # 3. Approve -> save to CSV, update status, reload, update UI

        btn_approve.click(

            fn=approve_pending_word,

            inputs=[

                word_input,

                suggested_translation_input,

                notes_input,

                example_source_input,

                example_wrong_input,

                example_correct_input,

                dict_file_path
            ],

            outputs=[action_status, registered_word_dropdown, pending_word_dropdown, dict_view],
        ).then(fn=orchestrator.reload_onomatopoeia, inputs=None, outputs=None).then(
            fn=load_current_dictionary,
            inputs=[dict_file_path, dict_search_term, dict_page_state],
            outputs=[dict_view, dict_page_info, dict_page_state, dict_total_pages_state]
        )

        

        # 4. Reject -> delete / update status, update UI

        btn_reject.click(

            fn=reject_pending_word,
            inputs=[word_input, onomatopoeia_db_path_state],

            outputs=[action_status, pending_word_dropdown],

        )



        # 4.5. Approve All -> save all pending to CSV, update status, reload, update UI

        btn_approve_all.click(

            fn=approve_all_pending_words,
            inputs=[dict_file_path],
            outputs=[action_status, registered_word_dropdown, pending_word_dropdown, dict_view],
        ).then(fn=orchestrator.reload_onomatopoeia, inputs=None, outputs=None).then(
            fn=load_current_dictionary,
            inputs=[dict_file_path, dict_search_term, dict_page_state],
            outputs=[dict_view, dict_page_info, dict_page_state, dict_total_pages_state]
        )



        # 6. Refresh registered list dropdown

        btn_refresh_registered.click(

            fn=get_registered_choices,
            inputs=[dict_file_path],
            outputs=[registered_word_dropdown],

        )



        # 7. Select registered word from dropdown -> fill textboxes

        registered_word_dropdown.change(

            fn=load_registered_word_details,
            inputs=[registered_word_dropdown, dict_file_path],
            outputs=[
                reg_word_input, reg_suggested_translation_input, reg_notes_input,
                reg_example_source_input, reg_example_wrong_input, reg_example_correct_input,
            ]
        )



        # 8. Update registered word -> modify in CSV, reload, update UI

        btn_update.click(

            fn=update_registered_word,

            inputs=[

                reg_word_input,

                reg_suggested_translation_input,

                reg_notes_input,

                reg_example_source_input,

                reg_example_wrong_input,

                reg_example_correct_input,

                dict_file_path
            ],

            outputs=[action_status, registered_word_dropdown, dict_view],

        ).then(fn=orchestrator.reload_onomatopoeia, inputs=None, outputs=None).then(
            fn=load_current_dictionary,
            inputs=[dict_file_path, dict_search_term, dict_page_state],
            outputs=[dict_view, dict_page_info, dict_page_state, dict_total_pages_state]
        )



        # 9. Delete registered word -> remove from CSV, reload, update UI

        btn_delete.click(

            fn=delete_registered_word,
            inputs=[reg_word_input, dict_file_path],
            outputs=[action_status, registered_word_dropdown, dict_view],

        ).then(fn=orchestrator.reload_onomatopoeia, inputs=None, outputs=None).then(
            fn=load_current_dictionary,
            inputs=[dict_file_path, dict_search_term, dict_page_state],
            outputs=[dict_view, dict_page_info, dict_page_state, dict_total_pages_state]
        )



        # 10. Click row in dict_view -> fill edit textboxes and switch to edit tab

        dict_view.select(

            fn=select_word_from_dict_view,
            inputs=[dict_file_path],
            outputs=[

                edit_tabs,

                registered_word_dropdown,

                reg_word_input,

                reg_suggested_translation_input,

                reg_notes_input,

                reg_example_source_input,

                reg_example_wrong_input,

                reg_example_correct_input,

            ]
        )
        
        # Dictionary Search and Pagination
        dict_search_button.click(
            fn=load_current_dictionary,
            inputs=[dict_file_path, dict_search_term],
            outputs=[dict_view, dict_page_info, dict_page_state, dict_total_pages_state]
        )
        dict_search_term.submit(
            fn=load_current_dictionary,
            inputs=[dict_file_path, dict_search_term],
            outputs=[dict_view, dict_page_info, dict_page_state, dict_total_pages_state]
        )
        
        def go_prev_page(file_path, search_term, current_page):
            return load_current_dictionary(file_path, search_term, max(1, current_page - 1))
        dict_prev_button.click(fn=go_prev_page, inputs=[dict_file_path, dict_search_term, dict_page_state], outputs=[dict_view, dict_page_info, dict_page_state, dict_total_pages_state])

        def go_next_page(file_path, search_term, current_page, total_pages):
            return load_current_dictionary(file_path, search_term, min(current_page + 1, total_pages))
        dict_next_button.click(fn=go_next_page, inputs=[dict_file_path, dict_search_term, dict_page_state, dict_total_pages_state], outputs=[dict_view, dict_page_info, dict_page_state, dict_total_pages_state])



        # ── Gnuboard Tab Event Wiring ──



        # 1. 검색 버튼 클릭 -> 검색 수행

        gb_btn_search.click(

            fn=on_search_click,

            inputs=[gb_board_select, gb_search_keyword, gb_sort_select, gb_rows_select],

            outputs=[gb_posts_json, gb_search_summary, gb_current_page, gb_max_page, gb_page_number_display],

        )



        # 엔터 키 입력 시에도 검색 동작

        gb_search_keyword.submit(

            fn=on_search_click,

            inputs=[gb_board_select, gb_search_keyword, gb_sort_select, gb_rows_select],

            outputs=[gb_posts_json, gb_search_summary, gb_current_page, gb_max_page, gb_page_number_display],

        )



        # 2. 이전 페이지 / 다음 페이지 버튼 클릭

        gb_btn_prev_page.click(

            fn=on_prev_page,

            inputs=[gb_board_select, gb_search_keyword, gb_sort_select, gb_rows_select, gb_current_page, gb_max_page],

            outputs=[gb_posts_json, gb_search_summary, gb_current_page, gb_max_page, gb_page_number_display],

        )

        gb_btn_next_page.click(

            fn=on_next_page,

            inputs=[gb_board_select, gb_search_keyword, gb_sort_select, gb_rows_select, gb_current_page, gb_max_page],

            outputs=[gb_posts_json, gb_search_summary, gb_current_page, gb_max_page, gb_page_number_display],

        )



        # 3. 번역기에 입력 버튼 클릭 -> 병합된 텍스트를 번역기 original_text_state 및 viewer_original 로딩

        gb_btn_merge_to_translator.click(

            fn=on_merge_to_translator,

            inputs=[gb_board_select, gb_selected_ids],

            outputs=[file_info, original_text_state, viewer_original, btn_translate, btn_extract, gb_selected_posts_state],

        ).then(

            fn=estimate_chunks,

            inputs=[original_text_state, source_lang, context_size],

            outputs=[chunk_estimate],

        )



        # 4. 병합 다운로드 버튼 클릭

        gb_btn_merge_download.click(

            fn=on_merge_download,

            inputs=[gb_board_select, gb_selected_ids],

            outputs=[download_file],

        )



        gb_btn_register_each.click(
            fn=on_register_each_to_trs,
            inputs=[
                gb_board_select,
                gb_selected_ids,
                source_lang,
                target_lang,
                context_size,
                api_url,
                api_key,
                glossary_file,
                temperature,
                enable_thinking,
            ],
            outputs=[progress_text, progress_bar, file_info, viewer_original, viewer_translated],
        )



        # ── Page Load Event ──

        app.load(

            fn=on_board_load,

            inputs=[],

            outputs=[gb_board_select, reg_board_select],

        )

        app.load(

            fn=check_active_translation,

            inputs=[],

            outputs=[

                progress_text, progress_bar,

                viewer_original, viewer_translated,

                download_file,

                viewer_reasoning,

                btn_translate

            ]

        )

        app.load(

            fn=get_pending_choices,
            inputs=[onomatopoeia_db_path_state],

            outputs=[pending_word_dropdown],

        )

        app.load(

            fn=get_registered_choices,
            inputs=[dict_file_path],
            outputs=[registered_word_dropdown],

        )

        app.load(

            fn=load_current_dictionary,
            inputs=[dict_file_path],
            outputs=[dict_view, dict_page_info, dict_page_state, dict_total_pages_state],
        )



    return app





# ─── Entry Point ────────────────────────────────────────────────────────



if __name__ == "__main__":

    app = create_ui()

    app.launch(

        server_name="127.0.0.1",

        server_port=7862,

        share=False,

        inbrowser=True,

        css=CUSTOM_CSS,

        theme=gr.themes.Base(

            primary_hue="slate",

            secondary_hue="gray",

            neutral_hue="slate",

            font=gr.themes.GoogleFont("Inter"),

        ),

    )
