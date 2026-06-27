import os
import json
import logging
import math
import time
from typing import Generator

logger = logging.getLogger("NovelTranslator.TranslationService")

def get_initial_table_html() -> str:
    return """
    <div style="text-align: center; padding: 20px; color: #a0aec0;">
        <p>검색 버튼을 눌러 그누보드 게시판 데이터를 불러오세요.</p>
    </div>
    """

def estimate_chunks(text: str, source_lang: str, context_size: int) -> tuple[str, str]:
    if not text:
        return "자수: 0자", "예상 청크: 0개"
    
    from novel_translator.services.chunker import SmartChunker
    chunker = SmartChunker(max_chunk_size=context_size, source_lang=source_lang)
    chunks = chunker.chunk_text(text)
    
    char_count = len(text)
    chunk_count = len(chunks)
    
    return f"자수: {char_count:,}자", f"예상 청크: {chunk_count}개"

def on_search_click(bo_table: str, stx: str, sort: str, page_rows: int, page: int = 1):
    import gradio as gr
    from novel_translator.services.gnuboard_db import GnuboardDB
    
    if not bo_table:
        return get_initial_table_html(), "1 / 1 페이지", 1, 1, '<h4>검색 결과: <span style="color:#e53e3e; font-weight:bold;">오류</span></h4><small>게시판 코드가 필요합니다.</small>', ""
        
    try:
        db = GnuboardDB()
        total_count = db.get_posts_count(bo_table, stx)
        max_page = max(1, math.ceil(total_count / page_rows))
        page = min(page, max_page)
        
        posts = db.search_posts(bo_table, stx, sort, page, page_rows)
        
        # HTML Table Construction
        html = """
        <table class="gb-table">
            <thead>
                <tr>
                    <th style="width: 40px; text-align: center;"><input type="checkbox" id="gb-select-all" onclick="toggleAllGbRows(this)"/></th>
                    <th style="width: 60px; text-align: center;">이동</th>
                    <th style="width: 80px; text-align: center;">ID</th>
                    <th style="text-align: left; padding-left: 10px;">원문 제목</th>
                    <th style="width: 100px; text-align: center;">작성자</th>
                    <th style="width: 120px; text-align: center;">작성일</th>
                </tr>
            </thead>
            <tbody id="gb-table-body">
        """
        
        for p in posts:
            wr_id = p.get('wr_id', '')
            subject = p.get('wr_subject', '')
            writer = p.get('wr_name', '')
            dt = p.get('wr_datetime', '')
            if isinstance(dt, str) and len(dt) > 10:
                dt = dt[:10] # YYYY-MM-DD
                
            html += f"""
            <tr class="gb-row" data-id="{wr_id}">
                <td style="text-align: center;"><input type="checkbox" class="gb-row-chk" value="{wr_id}" onclick="updateSelectedIds()"/></td>
                <td style="text-align: center; cursor: move;" class="drag-handle">☰</td>
                <td style="text-align: center;">{wr_id}</td>
                <td style="text-align: left; padding-left: 10px; font-weight: 500;">{subject}</td>
                <td style="text-align: center; color: #4a5568; font-size: 0.9em;">{writer}</td>
                <td style="text-align: center; color: #718096; font-size: 0.85em;">{dt}</td>
            </tr>
            """
            
        html += "</tbody></table>"
        
        page_display = f"{page} / {max_page} 페이지"
        summary = f'<h4>검색 결과: <span style="color:#3182ce; font-weight:bold;">{total_count}</span>건</h4><small style="color:#718096;">☰ 드래그하여 순서를 바꿀 수 있습니다.</small>'
        
        return html, page_display, page, max_page, summary, ""
        
    except Exception as e:
        logger.error(f"Error on_search_click: {e}")
        return f"<div style='color:red; padding:10px;'>오류 발생: {str(e)}</div>", "1 / 1 페이지", 1, 1, '<h4>검색 결과: <span style="color:#e53e3e; font-weight:bold;">오류</span></h4>', ""

def on_prev_page(bo_table, stx, sort, page_rows, cur_page, max_page):
    target = max(1, cur_page - 1)
    return on_search_click(bo_table, stx, sort, page_rows, target)

def on_next_page(bo_table, stx, sort, page_rows, cur_page, max_page):
    target = min(max_page, cur_page + 1)
    return on_search_click(bo_table, stx, sort, page_rows, target)

def on_merge_to_translator(bo_table: str, selected_ids_str: str) -> tuple[str, str]:
    if not bo_table or not selected_ids_str:
        return "", "❌ 그누보드 검색 결과에서 항목을 먼저 선택해주세요."
        
    try:
        from novel_translator.services.gnuboard_db import GnuboardDB
        db = GnuboardDB()
        
        # Convert selected IDs JSON string to list
        ids = json.loads(selected_ids_str)
        if not ids:
            return "", "❌ 선택된 항목이 없습니다."
            
        # Retrieve post contents in order
        posts = db.get_posts_details(bo_table, ids)
        
        merged_texts = []
        for p in posts:
            subject = p.get('wr_subject', '')
            content = p.get('wr_content', '')
            merged_texts.append(f"### {subject}\n\n{content}")
            
        final_text = "\n\n" + "\n\n========================================\n\n".join(merged_texts)
        return final_text, f"✅ 선택한 {len(posts)}개 포스트의 원문이 번역기 입력창에 입력되었습니다."
        
    except Exception as e:
        logger.error(f"Error on_merge_to_translator: {e}")
        return "", f"❌ 오류 발생: {str(e)}"

def on_input_to_queue(bo_table: str, selected_ids_str: str) -> tuple[list, str]:
    if not bo_table or not selected_ids_str:
        return [], "❌ 항목을 선택해 주십시오."
        
    try:
        from novel_translator.services.gnuboard_db import GnuboardDB
        db = GnuboardDB()
        
        ids = json.loads(selected_ids_str)
        if not ids:
            return [], "❌ 선택된 항목이 없습니다."
            
        posts = db.get_posts_details(bo_table, ids)
        queue_items = []
        for p in posts:
            queue_items.append({
                "id": p.get('wr_id'),
                "title": p.get('wr_subject'),
                "content": p.get('wr_content'),
                "wr_datetime": p.get('wr_datetime'),
                "wr_link1": p.get('wr_link1', ''),
                "wr_name": p.get('wr_name', ''),
                "bo_table": bo_table
            })
            
        return queue_items, f"✅ {len(queue_items)}개 게시물이 대기 큐에 추가되었습니다. '번역 시작'을 클릭하십시오."
        
    except Exception as e:
        logger.error(f"Error on_input_to_queue: {e}")
        return [], f"❌ 대기 큐 추가 중 오류 발생: {str(e)}"

def translate_title(title: str, api_url: str, api_key: str) -> str:
    if not title:
        return ""
        
    from client import LlamaAPIClient
    client = LlamaAPIClient(api_url=api_url, api_key=api_key)
    
    system_prompt = (
        "당신은 소설 번역가입니다. 소설의 소제목이나 장 제목을 자연스러운 한국어 장명(제목)으로 번역해 주세요. "
        "장식이나 해설 없이 순수한 한국어 번역 결과만 한 줄로 출력하십시오."
    )
    user_prompt = f"원문 제목: {title}\n번역된 제목:"
    
    try:
        translated = client.get_chat_completion(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.3)
        return str(translated).strip().strip('"').strip("'")
    except Exception as e:
        logger.error(f"Error translating title: {e}")
        return title

def register_to_gnuboard_event(translated_posts_list, target_bo_table, request=None):
    if not target_bo_table:
        return "❌ 오류: 등록 대상 게시판(bo_table)이 지정되지 않았습니다."
        
    if not translated_posts_list:
        return "❌ 오류: 그누보드에 등록할 번역 완료된 포스트가 존재하지 않습니다."
        
    try:
        from novel_translator.services.gnuboard_db import GnuboardDB
        db = GnuboardDB()
        
        success_count = 0
        ip_addr = request.client.host if request and request.client else "127.0.0.1"
        
        for post in translated_posts_list:
            original_url = post.get("wr_link1", "")
            if not original_url and post.get("wr_id") and post.get("bo_table"):
                original_url = f"/bbs/board.php?bo_table={post.get('bo_table')}&wr_id={post.get('wr_id')}"
                
            original_datetime = post.get("wr_datetime", "")
            
            # Format subject: 번역된 한글제목 - (일본제목 원문 - 작성자 )
            subject = post["translated_title"]
            orig_title = post.get("original_title", "")
            writer = post.get("wr_name", "")
            
            if orig_title and orig_title != "단일 텍스트 번역":
                if writer:
                    subject = f"{subject} - ({orig_title} - {writer})"
                else:
                    subject = f"{subject} - ({orig_title})"
            
            # Replicate PHP logic (insert or match existing)
            new_id = db.register_post_to_gnuboard(
                bo_table=target_bo_table,
                title=subject,
                content=post["translated_content"],
                original_url=original_url,
                original_datetime=original_datetime,
                ip=ip_addr
            )
            if new_id:
                success_count += 1
                
        return f"✅ 번역 완료 포스트 {success_count}개 그누보드 '{target_bo_table}' 게시판에 등록 성공!"
        
    except Exception as e:
        logger.error(f"Error register_to_gnuboard_event: {e}")
        return f"❌ 그누보드 등록 실패: {str(e)}"

def start_translation(
    text_input: str,
    source_lang: str,
    target_lang: str,
    api_url: str,
    api_key: str,
    context_size: int,
    temperature: float,
    enable_thinking: bool,
    custom_system_prompt: str,
    enable_glossary: bool,
    enable_fewshot: bool,
    translation_queue_state: list,
    translated_posts_state: list,
    request=None
) -> Generator:
    import gradio as gr
    from client import LlamaAPIClient
    from novel_translator.services.chunker import SmartChunker
    from novel_translator.services.glossary import GlossaryManager
    
    client = LlamaAPIClient(api_url=api_url, api_key=api_key)
    
    # 1. Check if queue translation is active
    queue_active = bool(translation_queue_state)
    posts_to_process = []
    
    if queue_active:
        posts_to_process = list(translation_queue_state)
    else:
        # Single Text Input Translation
        posts_to_process = [{
            "id": None,
            "title": "단일 텍스트 번역",
            "content": text_input,
            "wr_datetime": "",
            "wr_link1": "",
            "wr_name": "",
            "bo_table": ""
        }]
        
    # Glossary Preparation
    glossary_mgr = GlossaryManager()
    if enable_glossary or enable_fewshot:
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "japanese_erotic_onomatopoeia.csv")
        if os.path.exists(csv_path):
            glossary_mgr.load_from_csv(csv_path)
            
    total_posts = len(posts_to_process)
    translated_posts_accumulator = []
    
    for idx, post in enumerate(posts_to_process, 1):
        post_title = post.get("title", "단일 텍스트")
        post_content = post.get("content", "")
        
        if not post_content.strip():
            continue
            
        # Title translation if queued post
        translated_title = post_title
        if queue_active and post_title != "단일 텍스트":
            yield (
                gr.update(value=f"⏳ [{idx}/{total_posts}] '{post_title}' 제목 번역 중..."),
                "",
                translation_queue_state,
                translated_posts_accumulator,
                gr.update(visible=True),
                gr.update(interactive=False)
            )
            translated_title = translate_title(post_title, api_url, api_key)
            
        # Chunker initialization
        chunker = SmartChunker(max_chunk_size=context_size, source_lang=source_lang)
        chunks = chunker.chunk_text(post_content)
        total_chunks = len(chunks)
        
        post_translation_parts = []
        
        for c_idx, chunk in enumerate(chunks, 1):
            progress_msg = f"⏳ [{idx}/{total_posts}] '{post_title}' 번역 중... (청크 {c_idx}/{total_chunks})"
            yield (
                gr.update(value=progress_msg),
                "".join(post_translation_parts),
                translation_queue_state,
                translated_posts_accumulator,
                gr.update(visible=True),
                gr.update(interactive=False)
            )
            
            # Format Prompt
            sys_prompt = custom_system_prompt if custom_system_prompt.strip() else (
                "당신은 프로 소설 번역가입니다. 제공된 소설 텍스트를 자연스럽고 몰입감 높은 문체로 번역해 주십시오.\n"
                "기계적인 직역을 지양하고, 앞뒤 문맥에 맞게 구어체 및 소설적 연출을 살려 아름다운 문장으로 번역해야 합니다."
            )
            
            # Inject Glossary & Guide
            glossary_part = glossary_mgr.format_for_prompt(chunk) if enable_glossary else ""
            fewshot_part = glossary_mgr.format_few_shot_for_prompt(chunk) if enable_fewshot else ""
            
            full_sys_prompt = sys_prompt
            if glossary_part:
                full_sys_prompt += f"\n\n{glossary_part}"
            if fewshot_part:
                full_sys_prompt += f"\n\n{fewshot_part}"
                
            # Build query options
            opts = {"temperature": temperature}
            if enable_thinking:
                opts["extra_body"] = {"enable_thinking": True}
                
            # Execute Streaming
            chunk_translation = ""
            try:
                for token in client.stream_chat_completion(
                    system_prompt=full_sys_prompt,
                    user_prompt=chunk,
                    **opts
                ):
                    chunk_translation += token
                    temp_full = "".join(post_translation_parts) + chunk_translation
                    yield (
                        gr.update(value=progress_msg),
                        temp_full,
                        translation_queue_state,
                        translated_posts_accumulator,
                        gr.update(visible=True),
                        gr.update(interactive=False)
                    )
            except Exception as e:
                chunk_translation += f"\n[번역 오류: {str(e)}]\n"
                
            post_translation_parts.append(chunk_translation)
            
        full_translated_content = "".join(post_translation_parts)
        
        # Accumulate translated post data
        translated_post_record = {
            "wr_id": post.get("id"),
            "original_title": post_title,
            "translated_title": translated_title,
            "translated_content": full_translated_content,
            "wr_datetime": post.get("wr_datetime"),
            "wr_link1": post.get("wr_link1"),
            "wr_name": post.get("wr_name"),
            "bo_table": post.get("bo_table")
        }
        translated_posts_accumulator.append(translated_post_record)
        
    # Complete
    final_status = "✅ 모든 번역 작업 완료!"
        
    yield (
        gr.update(value=final_status),
        "".join(post_translation_parts) if not queue_active else "대기 큐의 모든 게시물이 번역 완료되었습니다.",
        [], # Reset queue state
        translated_posts_accumulator,
        gr.update(visible=False), # Hide queue progress row
        gr.update(interactive=True) if len(translated_posts_accumulator) > 0 else gr.update(interactive=False)
    )
