import re
import os
import base64
import glob
import shutil
import gradio as gr
from client import LlamaAPIClient
from generator import NCSGenerator
import database

# Instantiate llama client and generator
llama_client = LlamaAPIClient()
ncs_generator = NCSGenerator(llama_client)

def copy_generated_illustration():
    """
    Finds and copies the latest generated illustration from AppData to the local folder,
    ensuring it is loaded correctly in the UI.
    """
    try:
        app_data_dir = r"C:\Users\SangO\.gemini\antigravity\brain\27935dfe-e066-4903-8314-dd62fb008d2b"
        search_pattern = os.path.join(app_data_dir, "ncs_training_illustration*.png")
        files = glob.glob(search_pattern)
        if files:
            files.sort(key=os.path.getmtime, reverse=True)
            latest_file = files[0]
            dst = r"d:\DeepScribe\ncs_writer\ncs_training_illustration.png"
            shutil.copy(latest_file, dst)
            print(f"[SYSTEM] Successfully copied generated illustration to: {dst}")
    except Exception as e:
        print(f"[WARNING] Failed to copy generated illustration on startup: {e}")

def get_base64_image():
    """
    Loads the local illustration image and encodes it as a base64 Data URL.
    """
    img_path = r"d:\DeepScribe\ncs_writer\ncs_training_illustration.png"
    if os.path.exists(img_path):
        try:
            with open(img_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
                return f"data:image/png;base64,{img_data}"
        except Exception as e:
            print(f"[WARNING] Error reading image: {e}")
    return ""

def get_clean_title(title):
    """
    Strips section numbering prefixes like '2-1. ' or '2-1 ' from titles.
    """
    if not title:
        return ""
    return re.sub(r'^[0-9]+-[0-9]+\.?\s*', '', title)

def render_table_rows_to_html(rows):
    """
    Converts markdown table rows into clean, styled HTML tables.
    """
    if not rows:
        return ""
    
    html = ['<table class="ncs-table">']
    has_header = False
    
    for row in rows:
        cells = [c.strip() for c in row.split("|")[1:-1]]
        # Skip markdown separator row (e.g. |---|---|)
        if all(re.match(r'^:?-+:?$', c) for c in cells):
            continue
            
        if not has_header:
            html.append("<thead><tr>")
            for cell in cells:
                html.append(f"<th>{cell}</th>")
            html.append("</tr></thead><tbody>")
            has_header = True
        else:
            html.append("<tr>")
            for cell in cells:
                html.append(f"<td>{cell}</td>")
            html.append("</tr>")
            
    if has_header:
        html.append("</tbody>")
    html.append("</table>")
    return "\n".join(html)

def parse_and_format_content(text):
    """
    Parses hierarchical lists and tables from raw generated markdown/text
    into structured HTML elements with appropriate CSS classes.
    """
    if not text:
        return ""
        
    # 1. Parse out markdown tables first to prevent mangling
    lines = text.split("\n")
    table_placeholders = {}
    table_index = 0
    
    processed_lines = []
    in_table = False
    table_rows = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table_rows.append(stripped)
        else:
            if in_table:
                html_table = render_table_rows_to_html(table_rows)
                placeholder = f"__TABLE_PLACEHOLDER_{table_index}__"
                table_placeholders[placeholder] = html_table
                table_index += 1
                processed_lines.append(placeholder)
                table_rows = []
                in_table = False
            processed_lines.append(line)
            
    if in_table and table_rows:
        html_table = render_table_rows_to_html(table_rows)
        placeholder = f"__TABLE_PLACEHOLDER_{table_index}__"
        table_placeholders[placeholder] = html_table
        processed_lines.append(placeholder)
        
    # 2. Run hierarchical line-by-line formatting
    formatted_html = []
    for line in processed_lines:
        stripped = line.strip()
        if stripped.startswith("__TABLE_PLACEHOLDER_"):
            formatted_html.append(stripped)
            continue
            
        if not stripped:
            continue
            
        # Level 1: [1] or [2]
        m1 = re.match(r'^\[([0-9]+)\]\s*(.*)$', stripped)
        if m1:
            num, content = m1.groups()
            formatted_html.append(f'<div class="hierarchy-l1"><span class="badge-l1">학습 {num}</span> {content}</div>')
            continue
            
        # Level 2: 1. or 2.
        m2 = re.match(r'^([0-9]+)\.\s*(.*)$', stripped)
        if m2:
            num, content = m2.groups()
            formatted_html.append(f'<div class="hierarchy-l2">{num}. {content}</div>')
            continue
            
        # Level 3: (1) or (2)
        m3 = re.match(r'^\(([0-9]+)\)\s*(.*)$', stripped)
        if m3:
            num, content = m3.groups()
            formatted_html.append(f'<div class="hierarchy-l3">({num}) {content}</div>')
            continue
            
        # Level 4: (가), (나)
        m4 = re.match(r'^\(([가-힣a-zA-Z])\)\s*(.*)$', stripped)
        if m4:
            char, content = m4.groups()
            formatted_html.append(f'<div class="hierarchy-l4">({char}) {content}</div>')
            continue
            
        # Level 5: 1) or 2)
        m5 = re.match(r'^([0-9]+)\)\s*(.*)$', stripped)
        if m5:
            num, content = m5.groups()
            formatted_html.append(f'<div class="hierarchy-l5">{num}) {content}</div>')
            continue
            
        # Level 6: 가) or 나)
        m6 = re.match(r'^([가-힣a-zA-Z])\)\s*(.*)$', stripped)
        if m6:
            char, content = m6.groups()
            formatted_html.append(f'<div class="hierarchy-l6">{char}) {content}</div>')
            continue
            
        # Level 7: ① or ②
        m7 = re.match(r'^(①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩)\s*(.*)$', stripped)
        if m7:
            sym, content = m7.groups()
            formatted_html.append(f'<div class="hierarchy-l7">{sym} {content}</div>')
            continue
            
        # Level 8: ㉮ or ㉯
        m8 = re.match(r'^(㉮|㉯|㉰|㉱|㉲|㉳|㉴|㉵|㉶|㉷|㉸|㉹|㉺|㉻)\s*(.*)$', stripped)
        if m8:
            sym, content = m8.groups()
            formatted_html.append(f'<div class="hierarchy-l8">{sym} {content}</div>')
            continue
            
        # Bullets
        if stripped.startswith("•") or stripped.startswith("*") or stripped.startswith("-"):
            content = stripped[1:].strip()
            formatted_html.append(f'<div class="hierarchy-body">• {content}</div>')
            continue
            
        # Normal paragraph
        formatted_html.append(f'<div class="hierarchy-body">{stripped}</div>')
        
    html_result = "\n".join(formatted_html)
    
    # 3. Restore table placeholders with actual HTML tables
    for placeholder, html_table in table_placeholders.items():
        html_result = html_result.replace(placeholder, html_table)
        
    return html_result

def parse_performance_content(text):
    """
    Separates the combined performance content input into materials, equipment, and safety.
    """
    if not text:
        return "", "", ""
        
    current_sec = None
    lines = text.split("\n")
    
    mat_lines = []
    eq_lines = []
    saf_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if "### 1. 재료" in stripped or "1. 재료" in stripped:
            current_sec = 1
            continue
        elif "### 2. 기기" in stripped or "2. 기기" in stripped or ("장비" in stripped and "###" in stripped):
            current_sec = 2
            continue
        elif "### 3. 안전" in stripped or "3. 안전" in stripped or ("유의 사항" in stripped and "###" in stripped):
            current_sec = 3
            continue
            
        if current_sec == 1:
            mat_lines.append(stripped)
        elif current_sec == 2:
            eq_lines.append(stripped)
        elif current_sec == 3:
            saf_lines.append(stripped)
            
    if not mat_lines and not eq_lines and not saf_lines:
        # Fallback if headings aren't matched
        mat_lines = [l.strip() for l in lines if l.strip()]
        
    mat_html = "".join([f"<li>{l.lstrip('*-•').strip()}</li>" for l in mat_lines if l])
    eq_html = "".join([f"<li>{l.lstrip('*-•').strip()}</li>" for l in eq_lines if l])
    saf_html = "".join([f"<li>{l.lstrip('*-•').strip()}</li>" for l in saf_lines if l])
    
    return mat_html, eq_html, saf_html

def parse_performance_tips(text):
    """
    Extracts structured tips and diagram details from the raw tips generation.
    """
    if not text:
        return "", "", "", ""
        
    tips = []
    img_num_title = "[그림 1-1] 침해사고 대응 개념도"
    img_desc = ""
    img_source = "출처: 교육부"
    
    current_sec = None
    lines = text.split("\n")
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if "### 1. 수행 tip" in stripped or "1. 수행 tip" in stripped:
            current_sec = 1
            continue
        elif "### 2. 그림" in stripped or "2. 그림" in stripped:
            current_sec = 2
            continue
            
        if current_sec == 1:
            tips.append(stripped.lstrip('*-•').strip())
        elif current_sec == 2:
            if "식별 번호" in stripped or "그림 식별" in stripped or "그림 제목" in stripped or "식별번호" in stripped or stripped.startswith("[그림"):
                img_num_title = stripped.split(":", 1)[-1].strip() if ":" in stripped else stripped
            elif "그림 설명" in stripped or "설명:" in stripped:
                img_desc = stripped.split(":", 1)[-1].strip() if ":" in stripped else stripped
            elif "그림 출처" in stripped or "출처:" in stripped:
                img_source = stripped.split(":", 1)[-1].strip() if ":" in stripped else stripped
            else:
                if not img_desc:
                    img_desc = stripped
                else:
                    img_source = stripped
                    
    tips_html = "".join([f"<li>{t}</li>" for t in tips if t])
    return tips_html, img_num_title, img_desc, img_source

def split_steps_text(steps_text):
    """
    Splits the steps content into two pages dynamically, or using manual tags.
    """
    if not steps_text:
        return "", ""
        
    if "[페이지 구분]" in steps_text:
        parts = steps_text.split("[페이지 구분]", 1)
        return parts[0], parts[1]
    elif "[pagebreak]" in steps_text:
        parts = steps_text.split("[pagebreak]", 1)
        return parts[0], parts[1]
        
    # Auto splitting logic
    lines = [l for l in steps_text.split("\n") if l.strip()]
    if len(lines) <= 8:
        return steps_text, ""
        
    mid = len(lines) // 2
    split_idx = mid
    for idx in range(max(0, mid - 2), min(mid + 3, len(lines))):
        if lines[idx].strip().startswith("["):
            split_idx = idx
            break
            
    p3 = "\n".join(lines[:split_idx])
    p4 = "\n".join(lines[split_idx:])
    return p3, p4

def extract_sources(steps_text):
    """
    Extracts bibliography sources from steps to render them inside absolute-positioned footers.
    """
    if not steps_text:
        return "", ""
        
    lines = steps_text.split("\n")
    sources = []
    remaining_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("출처:") or stripped.startswith("출처 ") or "출처: 교육부" in stripped:
            sources.append(stripped)
        else:
            remaining_lines.append(line)
            
    sources_html = ""
    if sources:
        sources_list = "".join([f"<div>{s}</div>" for s in sources])
        sources_html = f'<div class="sources-container">{sources_list}</div>'
        
    return "\n".join(remaining_lines), sources_html

def format_text_hierarchy(text, indent_chars="    "):
    """
    Formulates a clean hierarchical plain text indent based on hierarchical prefixes.
    """
    if not text:
        return ""
    lines = text.split("\n")
    formatted_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        # Level 1: [1]
        if re.match(r'^\[([0-9]+)\]', stripped):
            formatted_lines.append(stripped)
            continue
        # Level 2: 1.
        if re.match(r'^([0-9]+)\.', stripped):
            formatted_lines.append(indent_chars + stripped)
            continue
        # Level 3: (1)
        if re.match(r'^\(([0-9]+)\)', stripped):
            formatted_lines.append(indent_chars * 2 + stripped)
            continue
        # Level 4: (가)
        if re.match(r'^\(([가-힣a-zA-Z])\)', stripped):
            formatted_lines.append(indent_chars * 3 + stripped)
            continue
        # Level 5: 1)
        if re.match(r'^([0-9]+)\)', stripped):
            formatted_lines.append(indent_chars * 4 + stripped)
            continue
        # Level 6: 가)
        if re.match(r'^([가-힣a-zA-Z])\)', stripped):
            formatted_lines.append(indent_chars * 5 + stripped)
            continue
        # Level 7: ①
        if re.match(r'^(①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩)', stripped):
            formatted_lines.append(indent_chars * 6 + stripped)
            continue
        # Level 8: ㉮
        if re.match(r'^(㉮|㉯|㉰|㉱|㉲|㉳|㉴|㉵|㉶|㉷|㉸|㉹|㉺|㉻)', stripped):
            formatted_lines.append(indent_chars * 7 + stripped)
            continue
            
        # Bullets
        if stripped.startswith("•") or stripped.startswith("*") or stripped.startswith("-"):
            formatted_lines.append(stripped)
            continue
            
        # Default fallback
        formatted_lines.append(stripped)
        
    return "\n".join(formatted_lines)

def render_table_rows_to_ascii(rows):
    if not rows:
        return ""
    
    ascii_rows = []
    divider = "-" * 60
    
    for row in rows:
        cells = [c.strip() for c in row.split("|")[1:-1]]
        # Skip separator
        if all(re.match(r'^:?-+:?$', c) for c in cells):
            continue
        
        row_str = " | ".join(cells)
        ascii_rows.append(f" {row_str} ")
        
    # Build the final table structure
    if ascii_rows:
        res = [divider, ascii_rows[0], divider]
        for r in ascii_rows[1:]:
            res.append(r)
        res.append(divider)
        return "\n".join(res)
    return ""

def format_text_tables(text):
    if not text:
        return ""
    lines = text.split("\n")
    output_lines = []
    in_table = False
    table_rows = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table_rows.append(stripped)
        else:
            if in_table:
                # Format table to text
                ascii_table = render_table_rows_to_ascii(table_rows)
                output_lines.append(ascii_table)
                table_rows = []
                in_table = False
            output_lines.append(line)
            
    if in_table and table_rows:
        ascii_table = render_table_rows_to_ascii(table_rows)
        output_lines.append(ascii_table)
        
    return "\n".join(output_lines)

def parse_performance_content_text(text):
    if not text:
        return "", "", ""
        
    current_sec = None
    lines = text.split("\n")
    
    mat_lines = []
    eq_lines = []
    saf_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if "### 1. 재료" in stripped or "1. 재료" in stripped:
            current_sec = 1
            continue
        elif "### 2. 기기" in stripped or "2. 기기" in stripped or ("장비" in stripped and "###" in stripped):
            current_sec = 2
            continue
        elif "### 3. 안전" in stripped or "3. 안전" in stripped or ("유의 사항" in stripped and "###" in stripped):
            current_sec = 3
            continue
            
        if current_sec == 1:
            mat_lines.append(stripped)
        elif current_sec == 2:
            eq_lines.append(stripped)
        elif current_sec == 3:
            saf_lines.append(stripped)
            
    if not mat_lines and not eq_lines and not saf_lines:
        mat_lines = [l.strip() for l in lines if l.strip()]
        
    mat_txt = "\n".join([f"• {l.lstrip('*-•').strip()}" for l in mat_lines if l])
    eq_txt = "\n".join([f"• {l.lstrip('*-•').strip()}" for l in eq_lines if l])
    saf_txt = "\n".join([f"• {l.lstrip('*-•').strip()}" for l in saf_lines if l])
    
    return mat_txt, eq_txt, saf_txt

def extract_sources_txt(steps_text):
    if not steps_text:
        return "", ""
        
    lines = steps_text.split("\n")
    sources = []
    remaining_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("출처:") or stripped.startswith("출처 ") or "출처: 교육부" in stripped:
            sources.append(stripped)
        else:
            remaining_lines.append(line)
            
    sources_txt = "\n".join(sources)
    return "\n".join(remaining_lines), sources_txt

def compile_text_format(job_name, learning_no, learning_title, section_no, module_header, objectives, knowledge, perf_content, perf_steps, perf_tips):
    job_name = job_name or ""
    learning_no = learning_no or ""
    learning_title = learning_title or ""
    section_no = section_no or ""
    module_header = module_header or ""
    objectives = objectives or ""
    knowledge = knowledge or ""
    perf_content = perf_content or ""
    perf_steps = perf_steps or ""
    perf_tips = perf_tips or ""

    # Clean sections
    clean_section_title = get_clean_title(section_no)
    
    # 1. Objectives formatting
    obj_lines = [f"• {l.strip().lstrip('*-•').strip()}" for l in objectives.split("\n") if l.strip()]
    objectives_txt = "\n".join(obj_lines)
    
    # 2. Knowledge formatting
    knowledge_txt = format_text_hierarchy(knowledge)
    
    # 3. Performance Content formatting
    mat_txt, eq_txt, saf_txt = parse_performance_content_text(perf_content)
    
    # 4. Performance Steps formatting
    cleaned_steps, sources_txt = extract_sources_txt(perf_steps)
    steps_p3, steps_p4 = split_steps_text(cleaned_steps)
    
    steps_txt_p3 = format_text_hierarchy(format_text_tables(steps_p3))
    steps_txt_p4 = format_text_hierarchy(format_text_tables(steps_p4))
    
    # 5. Tips & Diagram formatting
    tips_html, img_num_title, img_desc, img_source = parse_performance_tips(perf_tips)
    tips_list = [t.strip().lstrip('*-•').strip() for t in perf_tips.split("\n") if t.strip() and not t.strip().startswith("###") and not "그림" in t and not "출처" in t]
    tips_txt = "\n".join([f"• {t}" for t in tips_list if t])

    # Construct document
    doc = []
    
    # Page 23
    doc.append("=" * 60)
    doc.append(f"[페이지 23] - {module_header}")
    doc.append("=" * 60)
    doc.append(f"[{learning_no}] {learning_title}")
    doc.append(f"단원: {section_no}")
    doc.append("")
    doc.append("[학습 목표]")
    doc.append(objectives_txt or "• 학습 목표 내용 없음")
    doc.append("")
    doc.append("[필요 지식]")
    doc.append(knowledge_txt or "필요 지식 내용 없음")
    doc.append("\n")
    
    # Page 24
    doc.append("=" * 60)
    doc.append(f"[페이지 24] - 수행 내용 / {clean_section_title}")
    doc.append("=" * 60)
    doc.append("[재료·자료]")
    doc.append(mat_txt or "• 재료/자료 내용 없음")
    doc.append("")
    doc.append("[기기(장비·공구)]")
    doc.append(eq_txt or "• 기기/장비 내용 없음")
    doc.append("")
    doc.append("[안전·유의 사항(필수작성)]")
    doc.append(saf_txt or "• 안전/유의 사항 내용 없음")
    doc.append("\n")
    
    # Page 25
    doc.append("=" * 60)
    doc.append(f"[페이지 25] - 수행 순서")
    doc.append("=" * 60)
    doc.append(steps_txt_p3 or "수행 순서 내용 없음")
    if sources_txt:
        doc.append("")
        doc.append("[출처 및 참고문헌]")
        doc.append(sources_txt)
    doc.append("\n")
    
    # Page 26
    doc.append("=" * 60)
    doc.append(f"[페이지 26] - 수행 순서 (계속)")
    doc.append("=" * 60)
    if steps_txt_p4:
        doc.append(steps_txt_p4)
        doc.append("")
    doc.append("[수행 tip]")
    doc.append(tips_txt or "• 수행 팁 내용 없음")
    doc.append("")
    doc.append(f"{img_num_title or '[그림 1-1] 그림 제목'}")
    doc.append(f"설명: {img_desc or '설명 없음'}")
    doc.append(f"출처: {img_source or '출처 없음'}")
    doc.append("=" * 60)
    
    return "\n".join(doc)

def save_and_download_txt(job_name, learning_no, learning_title, section_no, module_header, objectives, knowledge, perf_content, perf_steps, perf_tips):
    content = compile_text_format(
        job_name, learning_no, learning_title, section_no, module_header,
        objectives, knowledge, perf_content, perf_steps, perf_tips
    )
    
    os.makedirs("d:/DeepScribe/outputs", exist_ok=True)
    file_path = "d:/DeepScribe/outputs/ncs_learning_module.txt"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return file_path

def parse_word_hierarchy(text):
    if not text:
        return ""
    lines = text.split("\n")
    formatted_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Level 1: [1]
        if re.match(r'^\[([0-9]+)\]', stripped):
            formatted_lines.append(f'<div class="hierarchy-level-1">{stripped}</div>')
            continue
        # Level 2: 1.
        if re.match(r'^([0-9]+)\.', stripped):
            formatted_lines.append(f'<div class="hierarchy-level-2">{stripped}</div>')
            continue
        # Level 3: (1)
        if re.match(r'^\(([0-9]+)\)', stripped):
            formatted_lines.append(f'<div class="hierarchy-level-3">{stripped}</div>')
            continue
        # Level 4: (가)
        if re.match(r'^\(([가-힣a-zA-Z])\)', stripped):
            formatted_lines.append(f'<div class="hierarchy-level-4">{stripped}</div>')
            continue
        # Level 5: 1)
        if re.match(r'^([0-9]+)\)', stripped):
            formatted_lines.append(f'<div class="hierarchy-level-5">{stripped}</div>')
            continue
        # Level 6: 가)
        if re.match(r'^([가-힣a-zA-Z])\)', stripped):
            formatted_lines.append(f'<div class="hierarchy-level-6">{stripped}</div>')
            continue
        # Level 7: ①
        if re.match(r'^(①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩)', stripped):
            formatted_lines.append(f'<div class="hierarchy-level-7">{stripped}</div>')
            continue
        # Level 8: ㉮
        if re.match(r'^(㉮|㉯|㉰|㉱|㉲|㉳|㉴|㉵|㉶|㉷|㉸|㉹|㉺|㉻)', stripped):
            formatted_lines.append(f'<div class="hierarchy-level-8">{stripped}</div>')
            continue
        # Default
        formatted_lines.append(f'<div style="margin-left: 20px;">{stripped}</div>')
    return "\n".join(formatted_lines)

def parse_word_performance_content(text):
    mat_txt, eq_txt, saf_txt = parse_performance_content_text(text)
    mat_html = "".join([f"<li style='margin-bottom: 4px;'>{l.strip().lstrip('•*').strip()}</li>" for l in mat_txt.split("\n") if l.strip()])
    eq_html = "".join([f"<li style='margin-bottom: 4px;'>{l.strip().lstrip('•*').strip()}</li>" for l in eq_txt.split("\n") if l.strip()])
    saf_html = "".join([f"<li style='margin-bottom: 4px;'>{l.strip().lstrip('•*').strip()}</li>" for l in saf_txt.split("\n") if l.strip()])
    return mat_html, eq_html, saf_html

def extract_word_sources(steps_text):
    cleaned, sources_txt = extract_sources_txt(steps_text)
    sources_html = ""
    if sources_txt:
        sources_list = "".join([f"<div style='margin-bottom: 4px;'>{s}</div>" for s in sources_txt.split("\n") if s.strip()])
        sources_html = f"""
        <div style="margin-top: 20px; padding-top: 10px; border-top: 1px solid #cbd5e1; font-size: 12px; color: #64748b;">
            <strong>[출처 및 참고문헌]</strong>
            {sources_list}
        </div>
        """
    return cleaned, sources_html

def render_table_rows_to_word_html(rows):
    if not rows:
        return ""
    
    html = ["<table style='width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 15px;'>"]
    is_header = True
    
    for row in rows:
        cells = [c.strip() for c in row.split("|")[1:-1]]
        if all(re.match(r'^:?-+:?$', c) for c in cells):
            continue
        
        html.append("<tr>")
        for cell in cells:
            if is_header:
                html.append(f"<th style='border: 1px solid #cbd5e1; padding: 10px; background-color: #f1f5f9; font-weight: bold; color: #334155;'>{cell}</th>")
            else:
                html.append(f"<td style='border: 1px solid #cbd5e1; padding: 10px;'>{cell}</td>")
        html.append("</tr>")
        is_header = False
        
    html.append("</table>")
    return "\n".join(html)

def parse_word_tables(text):
    if not text:
        return ""
    lines = text.split("\n")
    output_lines = []
    in_table = False
    table_rows = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table_rows.append(stripped)
        else:
            if in_table:
                html_table = render_table_rows_to_word_html(table_rows)
                output_lines.append(html_table)
                table_rows = []
                in_table = False
            output_lines.append(line)
    if in_table and table_rows:
        html_table = render_table_rows_to_word_html(table_rows)
        output_lines.append(html_table)
    return "\n".join(output_lines)

def compile_word_html(job_name, learning_no, learning_title, section_no, module_header, objectives, knowledge, perf_content, perf_steps, perf_tips):
    job_name = job_name or ""
    learning_no = learning_no or ""
    learning_title = learning_title or ""
    section_no = section_no or ""
    module_header = module_header or ""
    objectives = objectives or ""
    knowledge = knowledge or ""
    perf_content = perf_content or ""
    perf_steps = perf_steps or ""
    perf_tips = perf_tips or ""

    clean_section_title = get_clean_title(section_no)
    
    # 1. Objectives
    obj_lines = [l.strip().lstrip('*-•').strip() for l in objectives.split("\n") if l.strip()]
    objectives_html = "".join([f"<li style='margin-bottom: 6px;'>{l}</li>" for l in obj_lines]) if obj_lines else "<li>학습 목표 내용 없음</li>"
    
    # 2. Knowledge
    knowledge_html = parse_word_hierarchy(knowledge)
    
    # 3. Performance Content
    mat_html, eq_html, saf_html = parse_word_performance_content(perf_content)
    
    # 4. Performance Steps
    cleaned_steps, sources_html = extract_word_sources(perf_steps)
    steps_p3, steps_p4 = split_steps_text(cleaned_steps)
    
    steps_html_p3 = parse_word_hierarchy(parse_word_tables(steps_p3))
    steps_html_p4 = parse_word_hierarchy(parse_word_tables(steps_p4))
    
    # 5. Tips & Diagrams
    tips_list = [t.strip().lstrip('*-•').strip() for t in perf_tips.split("\n") if t.strip() and not t.strip().startswith("###") and not "그림" in t and not "출처" in t]
    tips_html = "".join([f"<li style='margin-bottom: 6px;'>{t}</li>" for t in tips_list if t]) if tips_list else "<li>수행 팁 내용 없음</li>"
    
    tips_parsed_html, img_num_title, img_desc, img_source = parse_performance_tips(perf_tips)
    img_base64 = get_base64_image()
    
    img_html = ""
    if img_base64:
        img_html = f"""
        <div style="text-align: center; margin-top: 20px; margin-bottom: 20px;">
            <img src="data:image/png;base64,{img_base64}" alt="그림" style="max-width: 100%; height: auto; border: 1px solid #cbd5e1; border-radius: 4px;" />
            <div style="font-weight: bold; margin-top: 8px; font-size: 13px; color: #475569;">{img_num_title or '[그림 1-1] 그림 제목'}</div>
            <div style="font-size: 12px; color: #64748b; margin-top: 2px;">{img_source or '출처: 교육부'}</div>
        </div>
        """
    else:
        img_html = f"""
        <div style="text-align: center; margin-top: 20px; margin-bottom: 20px; background-color: #f3f4f6; border: 1px dashed #cbd5e1; padding: 30px; border-radius: 4px; color: #94a3b8;">
            <div style="font-weight: bold;">{img_num_title or '[그림 1-1] 그림 제목'}</div>
            <div style="font-size: 12px;">{img_source or '출처: 교육부'}</div>
        </div>
        """

    # Assemble HTML document
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>NCS 학습모듈 - {learning_title}</title>
<style>
    body {{
        font-family: 'Malgun Gothic', '맑은 고딕', Arial, sans-serif;
        line-height: 1.6;
        color: #333333;
        margin: 40px;
    }}
    h1 {{ color: #1e3a8a; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-top: 0; }}
    h2 {{ color: #2563eb; margin-top: 30px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
    h3 {{ color: #1e40af; margin-top: 20px; }}
    .page-break {{
        page-break-after: always;
        break-after: page;
        border-top: 1px dashed #94a3b8;
        margin-top: 40px;
        margin-bottom: 40px;
        padding-top: 10px;
        color: #64748b;
        font-size: 12px;
        text-align: right;
    }}
    .header-tag {{
        font-size: 12px;
        color: #64748b;
        text-align: right;
        margin-bottom: 20px;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 5px;
    }}
    .badge {{
        background-color: #fef08a;
        color: #854d0e;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 14px;
        display: inline-block;
        margin-right: 8px;
    }}
    .learning-title-box {{
        background-color: #eff6ff;
        border-left: 4px solid #3b82f6;
        padding: 15px;
        margin-bottom: 25px;
    }}
    .objectives-box {{
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 20px;
        border-radius: 6px;
        margin-bottom: 25px;
    }}
    .objectives-title {{
        font-weight: bold;
        color: #0f172a;
        font-size: 16px;
        margin-bottom: 10px;
    }}
    .tips-box {{
        background-color: #fffbeb;
        border-left: 4px solid #f59e0b;
        padding: 20px;
        margin-top: 25px;
        margin-bottom: 25px;
    }}
    .tips-title {{
        font-weight: bold;
        color: #b45309;
        font-size: 16px;
        margin-bottom: 10px;
    }}
    .safety-box {{
        background-color: #fef2f2;
        border-left: 4px solid #ef4444;
        padding: 15px;
        margin-top: 15px;
        margin-bottom: 15px;
    }}
    .safety-title {{
        font-weight: bold;
        color: #991b1b;
        font-size: 15px;
        margin-bottom: 8px;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 15px;
        margin-bottom: 15px;
    }}
    th, td {{
        border: 1px solid #cbd5e1;
        padding: 10px;
        text-align: left;
    }}
    th {{
        background-color: #f1f5f9;
        font-weight: bold;
        color: #334155;
    }}
    .hierarchy-level-1 {{ font-weight: bold; color: #1e3a8a; margin-top: 15px; margin-bottom: 8px; }}
    .hierarchy-level-2 {{ margin-left: 20px; font-weight: bold; color: #0f172a; margin-top: 10px; }}
    .hierarchy-level-3 {{ margin-left: 40px; margin-top: 6px; }}
    .hierarchy-level-4 {{ margin-left: 60px; margin-top: 4px; color: #334155; }}
    .hierarchy-level-5 {{ margin-left: 80px; margin-top: 4px; color: #475569; }}
    .hierarchy-level-6 {{ margin-left: 100px; margin-top: 2px; }}
    .hierarchy-level-7 {{ margin-left: 120px; margin-top: 2px; }}
    .hierarchy-level-8 {{ margin-left: 140px; margin-top: 2px; }}
</style>
</head>
<body>

    <!-- PAGE 23 -->
    <div class="header-tag">{module_header}</div>
    <div class="learning-title-box">
        <span class="badge">{learning_no}</span>
        <span style="font-size: 20px; font-weight: bold; color: #1e3a8a;">{learning_title}</span>
        <div style="font-size: 15px; color: #475569; margin-top: 8px; font-weight: bold;">{section_no}</div>
    </div>
    
    <div class="objectives-box">
        <div class="objectives-title">학습 목표</div>
        <ul style="margin: 0; padding-left: 20px;">
            {objectives_html}
        </ul>
    </div>
    
    <h3 style="border-bottom: 2px solid #1e3a8a; padding-bottom: 5px; color: #1e3a8a;">필요 지식</h3>
    <div style="margin-top: 15px; margin-bottom: 25px;">
        {knowledge_html}
    </div>
    
    <!-- PAGE 24 -->
    <div class="page-break">[페이지 구분 - 24페이지 수행 내용]</div>
    <div class="header-tag">수행 내용 / {clean_section_title}</div>
    
    <h3 style="color: #0f172a; border-left: 4px solid #10b981; padding-left: 10px;">재료 · 자료</h3>
    <ul style="padding-left: 20px; margin-bottom: 25px;">
        {mat_html or "<li>재료/자료 내용 없음</li>"}
    </ul>
    
    <h3 style="color: #0f172a; border-left: 4px solid #3b82f6; padding-left: 10px;">기기(장비 · 공구)</h3>
    <ul style="padding-left: 20px; margin-bottom: 25px;">
        {eq_html or "<li>기기/장비 내용 없음</li>"}
    </ul>
    
    <div class="safety-box">
        <div class="safety-title">안전 · 유의 사항(필수작성)</div>
        <ul style="padding-left: 20px; margin: 0;">
            {saf_html or "<li>안전/유의 사항 내용 없음</li>"}
        </ul>
    </div>
    
    <!-- PAGE 25 -->
    <div class="page-break">[페이지 구분 - 25페이지 수행 순서]</div>
    <div class="header-tag">수행 순서</div>
    <div style="margin-top: 15px; margin-bottom: 25px;">
        {steps_html_p3}
    </div>
    {sources_html}
    
    <!-- PAGE 26 -->
    <div class="page-break">[페이지 구분 - 26페이지 수행 순서 (계속)]</div>
    <div class="header-tag">수행 순서 (계속)</div>
    <div style="margin-top: 15px; margin-bottom: 25px;">
        {steps_html_p4 or "<div style='color: #94a3b8; font-style: italic;'>(수행 순서 종료)</div>"}
    </div>
    
    <div class="tips-box">
        <div class="tips-title">수행 tip</div>
        <ul style="margin: 0; padding-left: 20px;">
            {tips_html}
        </ul>
    </div>
    
    {img_html}

</body>
</html>
"""
    return html

def save_and_download_word_html(job_name, learning_no, learning_title, section_no, module_header, objectives, knowledge, perf_content, perf_steps, perf_tips):
    content = compile_word_html(
        job_name, learning_no, learning_title, section_no, module_header,
        objectives, knowledge, perf_content, perf_steps, perf_tips
    )
    
    os.makedirs("d:/DeepScribe/outputs", exist_ok=True)
    file_path = "d:/DeepScribe/outputs/ncs_learning_module_word.html"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return file_path

# --- Single Generators for Learning Module ---

def generate_obj_single(job, l_title, s_title, add_info):
    if not job.strip():
        gr.Warning("직무명을 먼저 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성 가능합니다."
        return
    gr.Info("학습 목표 생성을 시작합니다...")
    text = ""
    for chunk in ncs_generator.generate_learning_objectives_stream(job, l_title, s_title, add_info):
        if chunk:
            text += chunk
            yield text

def generate_know_single(job, l_title, s_title, add_info):
    if not job.strip():
        gr.Warning("직무명을 먼저 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성 가능합니다."
        return
    gr.Info("필요 지식 생성을 시작합니다...")
    text = ""
    for chunk in ncs_generator.generate_required_knowledge_stream(job, l_title, s_title, add_info):
        if chunk:
            text += chunk
            yield text

def generate_perf_content_single(job, l_title, s_title, add_info):
    if not job.strip():
        gr.Warning("직무명을 먼저 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성 가능합니다."
        return
    gr.Info("수행 내용(재료/안전) 생성을 시작합니다...")
    text = ""
    for chunk in ncs_generator.generate_performance_content_stream(job, l_title, s_title, add_info):
        if chunk:
            text += chunk
            yield text

def generate_perf_steps_single(job, l_title, s_title, add_info):
    if not job.strip():
        gr.Warning("직무명을 먼저 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성 가능합니다."
        return
    gr.Info("수행 순서 생성을 시작합니다...")
    text = ""
    for chunk in ncs_generator.generate_performance_steps_stream(job, l_title, s_title, add_info):
        if chunk:
            text += chunk
            yield text

def generate_perf_tips_single(job, l_title, s_title, add_info):
    if not job.strip():
        gr.Warning("직무명을 먼저 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성 가능합니다."
        return
    gr.Info("수행 팁 및 그림 설명 생성을 시작합니다...")
    text = ""
    for chunk in ncs_generator.generate_performance_tips_stream(job, l_title, s_title, add_info):
        if chunk:
            text += chunk
            yield text

def generate_all_module_stream(job, l_no, l_title, s_title, m_header, add_info):
    if not job.strip():
        gr.Warning("직무명을 먼저 입력해 주세요.")
        yield "대기 중...", "대기 중...", "대기 중...", "대기 중...", "대기 중..."
        return
        
    obj_text = ""
    know_text = ""
    perf_content_text = ""
    perf_steps_text = ""
    perf_tips_text = ""
    
    # 1. Objectives
    gr.Info("[Step 1/5] 학습 목표 도출 중...")
    yield "🔄 학습 목표 생성 중...", "대기 중...", "대기 중...", "대기 중...", "대기 중..."
    for chunk in ncs_generator.generate_learning_objectives_stream(job, l_title, s_title, add_info):
        if chunk:
            obj_text += chunk
            yield obj_text, "대기 중...", "대기 중...", "대기 중...", "대기 중..."
            
    # 2. Knowledge
    gr.Info("[Step 2/5] 필요 지식 도출 중...")
    yield obj_text, "🔄 필요 지식 생성 중...", "대기 중...", "대기 중...", "대기 중..."
    for chunk in ncs_generator.generate_required_knowledge_stream(job, l_title, s_title, add_info):
        if chunk:
            know_text += chunk
            yield obj_text, know_text, "대기 중...", "대기 중...", "대기 중..."
            
    # 3. Performance Content
    gr.Info("[Step 3/5] 수행 내용(재료/안전) 도출 중...")
    yield obj_text, know_text, "🔄 수행 내용 생성 중...", "대기 중...", "대기 중..."
    for chunk in ncs_generator.generate_performance_content_stream(job, l_title, s_title, add_info):
        if chunk:
            perf_content_text += chunk
            yield obj_text, know_text, perf_content_text, "대기 중...", "대기 중..."
            
    # 4. Performance Steps
    gr.Info("[Step 4/5] 수행 순서(순서/표) 도출 중...")
    yield obj_text, know_text, perf_content_text, "🔄 수행 순서 생성 중...", "대기 중..."
    for chunk in ncs_generator.generate_performance_steps_stream(job, l_title, s_title, add_info):
        if chunk:
            perf_steps_text += chunk
            yield obj_text, know_text, perf_content_text, perf_steps_text, "대기 중..."
            
    # 5. Tips & Diagrams
    gr.Info("[Step 5/5] 수행 팁 및 그림설명 도출 중...")
    yield obj_text, know_text, perf_content_text, perf_steps_text, "🔄 수행 팁 및 그림 설명 생성 중..."
    for chunk in ncs_generator.generate_performance_tips_stream(job, l_title, s_title, add_info):
        if chunk:
            perf_tips_text += chunk
            yield obj_text, know_text, perf_content_text, perf_steps_text, perf_tips_text
            
    gr.Info("🎉 NCS 학습모듈 교재 구성 요소 일괄 생성이 완료되었습니다!")

# --- Existing NCS Standards (KSA/Assessment) Generators ---

def generate_ksa_single(job_name, additional_info):
    if not job_name.strip():
        gr.Warning("NCS 직무명을 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성이 가능합니다."
        return
    gr.Info("KSA (지식/기술/태도) 생성을 시작합니다...")
    ksa_text = ""
    for chunk in ncs_generator.generate_ksa_stream(job_name, additional_info):
        if chunk:
            ksa_text += chunk
            yield ksa_text

def generate_range_single(job_name, additional_info):
    if not job_name.strip():
        gr.Warning("NCS 직무명을 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성이 가능합니다."
        return
    gr.Info("적용범위 및 작업상황 생성을 시작합니다...")
    range_text = ""
    for chunk in ncs_generator.generate_range_of_variables_stream(job_name, additional_info):
        if chunk:
            range_text += chunk
            yield range_text

def generate_assessment_single(job_name, additional_info):
    if not job_name.strip():
        gr.Warning("NCS 직무명을 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성이 가능합니다."
        return
    gr.Info("평가방법 및 지침 생성을 시작합니다...")
    assessment_text = ""
    for chunk in ncs_generator.generate_assessment_guidelines_stream(job_name, additional_info):
        if chunk:
            assessment_text += chunk
            yield assessment_text

def generate_all_ncs_stream(job_name, additional_info):
    if not job_name.strip():
        gr.Warning("NCS 직무명을 입력해 주세요.")
        yield "⚠️ 직무명을 입력해야 생성이 가능합니다.", "대기 중...", "대기 중..."
        return
        
    ksa_text = ""
    range_text = ""
    assessment_text = ""
    
    gr.Info("[Step 1/3] KSA 지식/기술/태도 도출 중...")
    yield "🔄 지식/기술/태도(KSA) 생성 중...", "대기 중...", "대기 중..."
    for chunk in ncs_generator.generate_ksa_stream(job_name, additional_info):
        if chunk:
            ksa_text += chunk
            yield ksa_text, "대기 중...", "대기 중..."
            
    gr.Info("[Step 2/3] 적용범위 및 작업상황 도출 중...")
    yield ksa_text, "🔄 적용범위/작업상황 생성 중...", "대기 중..."
    for chunk in ncs_generator.generate_range_of_variables_stream(job_name, additional_info):
        if chunk:
            range_text += chunk
            yield ksa_text, range_text, "대기 중..."
            
    gr.Info("[Step 3/3] 평가방법 및 지침 도출 중...")
    yield ksa_text, range_text, "🔄 평가방법/지침 생성 중..."
    for chunk in ncs_generator.generate_assessment_guidelines_stream(job_name, additional_info):
        if chunk:
            assessment_text += chunk
            yield ksa_text, range_text, assessment_text
            
    gr.Info("🎉 NCS 직무 표준서 일괄 작성이 완료되었습니다!")


def build_ui():
    # Attempt to copy illustration from AppData if it exists
    copy_generated_illustration()
    
    custom_css = """
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    .ncs-title {
        display: none !important;
    }
    .ncs-header-row {
        background-color: white !important;
        padding: 12px 20px !important;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        margin-bottom: 20px !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05) !important;
    }
    .ncs-title-compact {
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 100%;
    }
    
    /* A4 CSS Layout Preview styling */
    .ncs-page-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        background-color: #f1f5f9;
        padding: 24px;
        border-radius: 8px;
        gap: 32px;
        max-height: 85vh;
        overflow-y: auto;
        border: 1px solid #e2e8f0;
    }
    
    .ncs-page {
        background: white !important;
        color: #1e293b !important;
        width: 210mm;
        min-height: 297mm;
        padding: 20mm 15mm;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        position: relative;
        box-sizing: border-box;
        text-align: left;
        display: flex;
        flex-direction: column;
        font-family: 'Inter', 'Outfit', 'Malgun Gothic', sans-serif;
    }
    
    .page-header {
        display: flex;
        justify-content: space-between;
        border-bottom: 2px solid #cbd5e1;
        padding-bottom: 6px;
        font-size: 11px;
        color: #64748b;
        margin-bottom: 24px;
        font-weight: 500;
    }
    
    .lesson-header {
        background-color: #fffbeb;
        border-radius: 6px;
        padding: 18px 24px;
        display: flex;
        align-items: center;
        margin-bottom: 24px;
        border: 1px solid #fde68a;
    }
    
    .lesson-badge {
        background-color: #1e3a8a;
        color: white;
        font-weight: 800;
        padding: 6px 14px;
        border-radius: 4px;
        margin-right: 18px;
        font-size: 16px;
        letter-spacing: -0.3px;
    }
    
    .lesson-title {
        font-size: 24px;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.5px;
    }
    
    .section-title {
        font-size: 20px;
        font-weight: 700;
        color: #1d4ed8;
        margin-top: 16px;
        margin-bottom: 20px;
        border-left: 5px solid #1d4ed8;
        padding-left: 12px;
    }
    
    .objectives-box {
        border: 1px solid #e2e8f0;
        border-top: 4px solid #2563eb;
        background-color: #f8fafc;
        padding: 20px;
        border-radius: 6px;
        margin-bottom: 28px;
    }
    
    .objectives-title {
        font-size: 15px;
        font-weight: 700;
        color: #1e40af;
        margin-bottom: 10px;
    }
    
    .objectives-list {
        margin: 0;
        padding-left: 20px;
        font-size: 13.5px;
        line-height: 1.7;
        color: #334155;
    }
    
    .section-subtitle-knowledge {
        font-size: 17px;
        font-weight: 700;
        color: #0f172a;
        border-bottom: 2px solid #f59e0b;
        padding-bottom: 4px;
        margin-top: 16px;
        margin-bottom: 20px;
        display: inline-block;
    }
    
    /* Hierarchical structures */
    .hierarchy-l1 {
        font-size: 15px;
        font-weight: 700;
        color: #0f172a;
        margin-top: 20px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
    }
    
    .badge-l1 {
        background-color: #f1f5f9;
        color: #475569;
        padding: 3px 8px;
        border-radius: 4px;
        margin-right: 10px;
        font-size: 12.5px;
        font-weight: 700;
        border: 1px solid #cbd5e1;
    }
    
    .hierarchy-l2 {
        font-size: 14.5px;
        font-weight: 700;
        color: #334155;
        padding-left: 18px;
        margin-top: 14px;
        margin-bottom: 6px;
    }
    
    .hierarchy-l3 {
        font-size: 13.5px;
        font-weight: 600;
        color: #475569;
        padding-left: 36px;
        margin-top: 10px;
        margin-bottom: 4px;
    }
    
    .hierarchy-l4 {
        font-size: 13.5px;
        font-weight: 500;
        color: #475569;
        padding-left: 54px;
        margin-top: 6px;
        margin-bottom: 4px;
    }
    
    .hierarchy-l5 {
        font-size: 13px;
        color: #64748b;
        padding-left: 72px;
        margin-top: 6px;
    }
    
    .hierarchy-l6 {
        font-size: 13px;
        color: #64748b;
        padding-left: 90px;
        margin-top: 6px;
    }
    
    .hierarchy-l7 {
        font-size: 13px;
        color: #64748b;
        padding-left: 108px;
        margin-top: 6px;
    }
    
    .hierarchy-l8 {
        font-size: 13px;
        color: #64748b;
        padding-left: 126px;
        margin-top: 6px;
    }
    
    .hierarchy-body {
        font-size: 13.5px;
        color: #64748b;
        padding-left: 18px;
        margin-top: 4px;
        margin-bottom: 12px;
        line-height: 1.6;
    }
    
    .hierarchy-l1 + .hierarchy-body { padding-left: 18px; }
    .hierarchy-l2 + .hierarchy-body { padding-left: 36px; }
    .hierarchy-l3 + .hierarchy-body { padding-left: 54px; }
    .hierarchy-l4 + .hierarchy-body { padding-left: 72px; }
    
    /* Performance Materials & Equipment styling */
    .section-subtitle-materials {
        font-size: 17px;
        font-weight: 700;
        color: #0f172a;
        border-left: 5px solid #10b981;
        padding-left: 12px;
        margin-top: 24px;
        margin-bottom: 14px;
    }
    .materials-list, .equipment-list, .safety-list {
        margin: 0 0 20px 0;
        padding-left: 24px;
        font-size: 13.5px;
        line-height: 1.7;
        color: #334155;
    }
    
    .section-subtitle-equipment {
        font-size: 17px;
        font-weight: 700;
        color: #0f172a;
        border-left: 5px solid #3b82f6;
        padding-left: 12px;
        margin-top: 24px;
        margin-bottom: 14px;
    }
    
    .section-subtitle-safety {
        font-size: 17px;
        font-weight: 700;
        color: #ef4444;
        border-left: 5px solid #ef4444;
        padding-left: 12px;
        margin-top: 24px;
        margin-bottom: 14px;
    }
    
    .safety-box {
        background-color: #fef2f2;
        border: 1px solid #fee2e2;
        border-radius: 6px;
        padding: 16px;
        margin-top: 8px;
    }
    .safety-list {
        margin: 0;
        color: #991b1b;
    }
    
    /* Table inside 수행 순서 */
    .ncs-table {
        width: 100%;
        border-collapse: collapse;
        margin: 18px 0;
        font-size: 12.5px;
    }
    .ncs-table th {
        background-color: #f1f5f9;
        border-top: 2px solid #475569;
        border-bottom: 1px solid #cbd5e1;
        padding: 10px;
        font-weight: 700;
        color: #1e293b;
        text-align: center;
    }
    .ncs-table td {
        border-bottom: 1px dashed #cbd5e1;
        padding: 10px;
        color: #475569;
        text-align: center;
    }
    
    .sources-container {
        position: absolute;
        bottom: 20mm;
        left: 15mm;
        right: 15mm;
        border-top: 1px solid #e2e8f0;
        padding-top: 10px;
        font-size: 10px;
        color: #94a3b8;
        line-height: 1.5;
    }
    
    /* Tips & Illustrations Page */
    .tips-box {
        border: 1px solid #fcd34d;
        border-top: 4px solid #d97706;
        background-color: #fffdf5;
        padding: 20px;
        border-radius: 6px;
        margin-top: 24px;
        margin-bottom: 28px;
    }
    
    .tips-title {
        font-size: 15px;
        font-weight: 700;
        color: #b45309;
        margin-bottom: 10px;
    }
    
    .tips-list {
        margin: 0;
        padding-left: 20px;
        font-size: 13px;
        color: #451a03;
        line-height: 1.7;
    }
    
    .image-box {
        margin-top: auto;
        padding: 20px;
        border: 1px solid #e2e8f0;
        background-color: #f8fafc;
        border-radius: 6px;
        display: flex;
        flex-direction: column;
        align-items: center;
        margin-bottom: 12px;
    }
    .illust-img {
        max-width: 70%;
        max-height: 140px;
        object-fit: contain;
        margin-bottom: 12px;
        border-radius: 4px;
        border: 1px solid #e2e8f0;
    }
    .image-caption {
        font-size: 12.5px;
        font-weight: 700;
        color: #334155;
        text-align: center;
    }
    .image-source {
        font-size: 10.5px;
        color: #94a3b8;
        text-align: center;
        margin-top: 4px;
    }
    
    .page-footer {
        position: absolute;
        bottom: 12mm;
        left: 15mm;
        right: 15mm;
        display: flex;
        font-size: 12.5px;
        color: #475569;
        font-weight: 700;
        border-top: 1px solid #cbd5e1;
        padding-top: 8px;
    }
    
    .page-footer.odd {
        justify-content: flex-end;
    }
    
    .page-footer.even {
        justify-content: flex-start;
    }
    
    /* Action & Print styling */
    .print-btn-container {
        display: flex;
        justify-content: flex-end;
        width: 100%;
        margin-bottom: 10px;
    }
    
    .print-btn {
        background-color: #4f46e5 !important;
        color: white !important;
        border: none !important;
        padding: 10px 18px !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        font-size: 13.5px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2) !important;
    }
    .print-btn:hover {
        background-color: #4338ca !important;
        transform: translateY(-1px) !important;
    }
    
    /* Print Layout Media Query Styles */
    @media print {
        body, html {
            background: white !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        
        /* Hide everything else except the print area */
        .gradio-container {
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100% !important;
        }
        
        /* Hide the left editor completely */
        .gradio-container > div:first-child,
        .gradio-container .tabs,
        .gradio-container .tab-nav,
        .ncs-title,
        .no-print {
            display: none !important;
        }
        
        .ncs-preview-col {
            width: 100% !important;
            max-width: 100% !important;
            flex-grow: 1 !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        
        .ncs-page-container {
            background: white !important;
            padding: 0 !important;
            margin: 0 !important;
            box-shadow: none !important;
            border: none !important;
            max-height: none !important;
            overflow: visible !important;
            display: block !important;
        }
        
        .ncs-page {
            margin: 0 !important;
            box-shadow: none !important;
            border: none !important;
            width: 210mm !important;
            height: 297mm !important;
            page-break-after: always !important;
            display: flex !important;
            box-sizing: border-box !important;
        }
    }
    """
    
    from gradio import __version__ as gradio_version
    is_gradio_6 = int(gradio_version.split(".")[0]) >= 6
    
    blocks_kwargs = {
        "title": "NCS 직무 및 학습모듈 집필 지원 시스템",
        "theme": gr.themes.Soft(primary_hue="indigo", secondary_hue="slate", neutral_hue="slate")
    }
    if not is_gradio_6:
        blocks_kwargs["css"] = custom_css
        
    with gr.Blocks(**blocks_kwargs) as app:
        if is_gradio_6:
            gr.HTML(f"<style>{custom_css}</style>")
            
        with gr.Row(elem_classes=["ncs-header-row"]):
            with gr.Column(scale=4):
                gr.HTML("""
                    <div class="ncs-title-compact">
                        <h2 style="margin: 0; font-size: 18px; font-weight: 800; color: #1e3c72; display: flex; align-items: center; gap: 8px;">
                            📋 NCS 집필 지원 엔진
                        </h2>
                        <p style="margin: 4px 0 0 0; font-size: 12px; color: #64748b;">NCS 국가직무능력표준 & 학습모듈 AI 고속 집필 도구</p>
                    </div>
                """)
            with gr.Column(scale=8):
                with gr.Row():
                    project_dd = gr.Dropdown(
                        label="📁 프로젝트 선택",
                        choices=database.get_project_list(),
                        value=database.get_project_list()[0] if database.get_project_list() else None,
                        interactive=True,
                        scale=2
                    )
                    version_dd = gr.Dropdown(
                        label="⏳ 버전 이력 선택",
                        choices=[],
                        interactive=True,
                        scale=3
                    )
                with gr.Row():
                    new_proj_name = gr.Textbox(
                        label="➕ 신규 프로젝트명",
                        placeholder="이름 입력...",
                        lines=1,
                        scale=2
                    )
                    btn_new_proj = gr.Button("🆕 신규", variant="secondary", scale=1)
                    btn_save_proj = gr.Button("💾 저장", variant="primary", scale=1)
                    btn_delete_proj = gr.Button("❌ 삭제", variant="stop", scale=1)
        
        with gr.Tabs() as main_tabs:
            
            # TAB 1: NEW NCS LEARNING MODULE WRITER (양식에 맞춘 교재 집필)
            with gr.Tab("📖 NCS 학습모듈 집필 (교재 양식)"):
                with gr.Row():
                    
                    # Left side: Editor & Controls
                    with gr.Column(scale=11):
                        gr.Markdown("### ⚙️ 교재 단원 및 집필 설정")
                        
                        with gr.Group():
                            with gr.Row():
                                job_name_mod = gr.Textbox(
                                    label="🏷️ NCS 직무명 (세분류)",
                                    value="침해사고 분석대응",
                                    placeholder="예: 침해사고 분석대응, 빅데이터 분석 등",
                                    scale=2
                                )
                                learning_no_mod = gr.Textbox(
                                    label="📘 학습 번호",
                                    value="학습 2",
                                    placeholder="예: 학습 2",
                                    scale=1
                                )
                            
                            with gr.Row():
                                learning_title_mod = gr.Textbox(
                                    label="📖 학습명",
                                    value="침해사고정보 수집하기",
                                    placeholder="예: 침해사고정보 수집하기",
                                    scale=1
                                )
                                section_no_mod = gr.Textbox(
                                    label="📑 단원명 (소주제)",
                                    value="2-1. 현장 보존 후 대상별 정보 확보",
                                    placeholder="예: 2-1. 현장 보존 후 대상별 정보 확보",
                                    scale=1
                                )
                                
                            module_header_mod = gr.Textbox(
                                label="📰 교재 상단 머리글",
                                value="학습 1 침해사고정보 수집 준비하기",
                                placeholder="예: 학습 1 침해사고정보 수집 준비하기"
                            )
                            
                            additional_info_mod = gr.Textbox(
                                label="📝 추가 개발 조건 및 참고 지시사항 (선택)",
                                placeholder="예: 포렌식 증거 보존 원칙 포함, 또는 클라우드 보안 환경 위주 기술 등",
                                lines=2
                            )
                        
                        btn_gen_all_mod = gr.Button("🪄 학습모듈 교재 전체 일괄 생성", variant="primary")
                        
                        gr.Markdown("### ✍️ 교재 세부 내용 편집기 (수정 가능)")
                        with gr.Tabs() as editor_tabs:
                            with gr.Tab("1. 학습 목표"):
                                out_objectives = gr.Textbox(
                                    label="학습 목표 목록 (글머리기호 사용)",
                                    lines=6,
                                    interactive=True,
                                    placeholder="• 침해사고 대상별 수집 도구를 활용하여 정보를 확보할 수 있다."
                                )
                                btn_gen_obj = gr.Button("🎯 학습 목표 단독 생성/갱신", variant="secondary")
                                
                            with gr.Tab("2. 필요 지식"):
                                out_knowledge = gr.Textbox(
                                    label="필요 지식 상세 목록 (계층형 양식)",
                                    lines=12,
                                    interactive=True,
                                    placeholder="[1] 대분류 제목\n설명\n1. 중분류 제목\n(1) 소분류 제목"
                                )
                                btn_gen_know = gr.Button("📚 필요 지식 단독 생성/갱신", variant="secondary")
                                
                            with gr.Tab("3. 수행 내용 (재료/기기/안전)"):
                                out_perf_content = gr.Textbox(
                                    label="재료, 기기 및 안전사항",
                                    lines=10,
                                    interactive=True,
                                    placeholder="### 1. 재료·자료\n* 내용...\n### 2. 기기(장비·공구)\n* 내용...\n### 3. 안전·유의 사항\n* 내용..."
                                )
                                btn_gen_content = gr.Button("🛠️ 수행 내용 세트 단독 생성/갱신", variant="secondary")
                                
                            with gr.Tab("4. 수행 순서 (순서/표)"):
                                out_perf_steps = gr.Textbox(
                                    label="수행 순서 상세 및 표/출처",
                                    lines=14,
                                    interactive=True,
                                    placeholder="[1] 수행 순서 제목\n1. 세부 단계...\n\n| 구분 | 내용 |\n|---|---|\n\n출처: 교육부..."
                                )
                                btn_gen_steps = gr.Button("🏃 수행 순서 단독 생성/갱신", variant="secondary")
                                
                            with gr.Tab("5. 수행 tip & 그림"):
                                out_perf_tips = gr.Textbox(
                                    label="수행 팁 및 그림/출처 설명",
                                    lines=10,
                                    interactive=True,
                                    placeholder="### 1. 수행 tip\n* 내용...\n### 2. 그림 제목 및 설명\n식별 번호: [그림 1-1] 침해사고 대응 개념도"
                                )
                                btn_gen_tips = gr.Button("💡 수행 팁/그림 설명 단독 생성/갱신", variant="secondary")
                                
                    # Right side: TXT & Word HTML File Compiler & Downloader
                    with gr.Column(scale=10):
                        gr.Markdown("### 💾 완성된 NCS 교재 다운로드 (MS Word 호환 / 일반 텍스트)")
                        
                        with gr.Row():
                            btn_download_txt = gr.Button("💾 TXT 포맷 파일 다운로드", variant="secondary")
                            btn_download_html = gr.Button("📄 Word용 HTML 파일 다운로드", variant="primary")
                        
                        with gr.Row():
                            out_file_txt = gr.File(label="일반 텍스트 파일 (.txt)", interactive=False)
                            out_file_html = gr.File(label="Word용 HTML 파일 (.html)", interactive=False)
                        
                        gr.Markdown("#### 📄 다운로드 파일 본문 실시간 미리보기 (일반 텍스트)")
                        out_text_preview = gr.Textbox(
                            label="텍스트 미리보기",
                            placeholder="왼쪽 에디터에서 내용을 수정하거나 생성 버튼을 클릭하면 실시간으로 변환됩니다.",
                            lines=28,
                            interactive=False
                        )
            
            # TAB 2: ORIGINAL NCS STANDARD WRITER (직무 표준서)
            with gr.Tab("📋 NCS 직무 표준서 (KSA/적용범위/평가)"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### ⚙️ 직무 정의 및 지시사항")
                        job_name = gr.Textbox(
                            label="🏷️ NCS 직무명 (세분류)",
                            placeholder="예: 빅데이터 분석, 정보보안 감리",
                            lines=1,
                            value="침해사고 분석대응",
                            interactive=True
                        )
                        
                        additional_info = gr.Textbox(
                            label="📝 추가 개발 조건 및 지시사항 (선택)",
                            placeholder="예: 클라우드 기반 환경 중심 등",
                            lines=4,
                            interactive=True
                        )
                        
                        with gr.Accordion("⚙️ 고급 설정", open=False):
                            api_status = gr.Textbox(
                                label="Llama API 상태",
                                value=f"연결 대상: {llama_client.api_url}",
                                interactive=False
                            )
                        
                        btn_gen_all = gr.Button("🪄 NCS 표준 직무서 일괄 생성", variant="primary")
                        
                    with gr.Column(scale=2):
                        gr.Markdown("### 📄 표준 직무 능력 명세서 결과")
                        
                        with gr.Tabs():
                            with gr.Tab("📚 지식 / 기술 / 태도 (KSA)"):
                                with gr.Row():
                                    btn_gen_ksa = gr.Button("📚 KSA 단독 생성/갱신", variant="secondary")
                                out_ksa = gr.Textbox(
                                    label="지식(K), 기술(S), 태도(A) 목록",
                                    placeholder="NCS 표준 문체로 도출됩니다.",
                                    lines=18,
                                    interactive=True
                                )
                                
                            with gr.Tab("🔍 적용범위 및 작업상황"):
                                with gr.Row():
                                    btn_gen_range = gr.Button("🔍 적용범위/작업상황 단독 생성/갱신", variant="secondary")
                                out_range = gr.Textbox(
                                    label="적용 범위 및 작업 상황 고지",
                                    placeholder="도구, 환경, 법률 양식이 작성됩니다.",
                                    lines=18,
                                    interactive=True
                                )
                                
                            with gr.Tab("📝 평가방법 및 지침"):
                                with gr.Row():
                                    btn_gen_assessment = gr.Button("📝 평가방법/지침 단독 생성/갱신", variant="secondary")
                                out_assessment = gr.Textbox(
                                    label="직무 능력 평가 지침 및 주의사항",
                                    placeholder="검증 항목 및 채점 가이드라인이 작성됩니다.",
                                    lines=18,
                                    interactive=True
                                )
                                
            # TAB 3: AI PROMPT TEMPLATE VIEW
            with gr.Tab("🤖 AI 생성 프롬프트 템플릿"):
                gr.Markdown("### 🤖 NCS 집필 엔진 AI 생성 프롬프트 템플릿 목록")
                gr.Markdown("AI가 교재 및 직무 표준서를 작성할 때 전달하는 프롬프트(System 및 User Prompt)의 전체 명세입니다.")
                
                prompts_dict = ncs_generator.get_prompts()
                for key, info in prompts_dict.items():
                    with gr.Accordion(info["title"], open=False):
                        gr.Textbox(
                            label="🖥️ System Prompt",
                            value=info["system"],
                            lines=8,
                            interactive=False
                        )
                        gr.Textbox(
                            label="👤 User Prompt Template",
                            value=info["user"],
                            lines=10,
                            interactive=False
                        )
        
        # --- TAB 1 Bindings (NCS Learning Module) ---
        
        # 1. Update Preview Event Bindings
        preview_inputs = [
            job_name_mod, learning_no_mod, learning_title_mod, section_no_mod, module_header_mod,
            out_objectives, out_knowledge, out_perf_content, out_perf_steps, out_perf_tips
        ]
        
        # Trigger preview updates dynamically as editors change
        for component in preview_inputs:
            component.change(
                fn=compile_text_format,
                inputs=preview_inputs,
                outputs=out_text_preview
            )
            
        # Download button actions
        btn_download_txt.click(
            fn=save_and_download_txt,
            inputs=preview_inputs,
            outputs=out_file_txt
        )
        btn_download_html.click(
            fn=save_and_download_word_html,
            inputs=preview_inputs,
            outputs=out_file_html
        )
            
        # Define state_fields list for project state management
        state_fields = [
            job_name_mod, learning_no_mod, learning_title_mod, section_no_mod, module_header_mod, additional_info_mod,
            out_objectives, out_knowledge, out_perf_content, out_perf_steps, out_perf_tips,
            job_name, additional_info, out_ksa, out_range, out_assessment
        ]

        # --- Project & Version History Helper Functions ---
        def load_project_state(project_name):
            if not project_name:
                return [gr.update() for _ in range(16)] + [gr.update(choices=[], value=None)]
            
            versions = database.get_project_versions(project_name)
            if not versions:
                return [gr.update() for _ in range(16)] + [gr.update(choices=[], value=None)]
                
            latest_rev = versions[0][1]
            state = database.load_version(project_name, latest_rev)
            if not state:
                return [gr.update() for _ in range(16)] + [gr.update(choices=versions, value=latest_rev)]
                
            return [
                state.get("job_name_mod", ""),
                state.get("learning_no_mod", ""),
                state.get("learning_title_mod", ""),
                state.get("section_no_mod", ""),
                state.get("module_header_mod", ""),
                state.get("additional_info_mod", ""),
                state.get("out_objectives", ""),
                state.get("out_knowledge", ""),
                state.get("out_perf_content", ""),
                state.get("out_perf_steps", ""),
                state.get("out_perf_tips", ""),
                state.get("job_name", ""),
                state.get("additional_info", ""),
                state.get("out_ksa", ""),
                state.get("out_range", ""),
                state.get("out_assessment", "")
            ] + [gr.update(choices=versions, value=latest_rev)]

        def load_version_state(project_name, revision):
            if not project_name or not revision:
                return [gr.update() for _ in range(16)]
            
            state = database.load_version(project_name, revision)
            if not state:
                return [gr.update() for _ in range(16)]
                
            return [
                state.get("job_name_mod", ""),
                state.get("learning_no_mod", ""),
                state.get("learning_title_mod", ""),
                state.get("section_no_mod", ""),
                state.get("module_header_mod", ""),
                state.get("additional_info_mod", ""),
                state.get("out_objectives", ""),
                state.get("out_knowledge", ""),
                state.get("out_perf_content", ""),
                state.get("out_perf_steps", ""),
                state.get("out_perf_tips", ""),
                state.get("job_name", ""),
                state.get("additional_info", ""),
                state.get("out_ksa", ""),
                state.get("out_range", ""),
                state.get("out_assessment", "")
            ]

        def handle_new_project(name):
            if not name or not name.strip():
                gr.Warning("프로젝트 이름을 입력해주세요.")
                return [gr.update() for _ in range(19)]
                
            success, msg = database.create_project(name)
            if not success:
                gr.Warning(msg)
                return [gr.update() for _ in range(19)]
                
            gr.Info(msg)
            projects = database.get_project_list()
            new_val = name.strip()
            
            state_updates = load_project_state(new_val)
            return [gr.update(choices=projects, value=new_val), ""] + state_updates

        def handle_delete_project(project_name):
            if not project_name:
                gr.Warning("삭제할 프로젝트가 선택되지 않았습니다.")
                return [gr.update() for _ in range(18)]
                
            success, msg = database.delete_project(project_name)
            if success:
                gr.Info(msg)
            else:
                gr.Warning(msg)
                
            projects = database.get_project_list()
            new_val = projects[0] if projects else None
            
            state_updates = load_project_state(new_val)
            return [gr.update(choices=projects, value=new_val)] + state_updates

        def handle_save_project(project_name, *fields_values):
            if not project_name:
                gr.Warning("선택된 프로젝트가 없습니다.")
                return gr.update()
                
            keys = [
                "job_name_mod", "learning_no_mod", "learning_title_mod", "section_no_mod", "module_header_mod", "additional_info_mod",
                "out_objectives", "out_knowledge", "out_perf_content", "out_perf_steps", "out_perf_tips",
                "job_name", "additional_info", "out_ksa", "out_range", "out_assessment"
            ]
            fields_dict = dict(zip(keys, fields_values))
            success, msg = database.save_version(project_name, "사용자 수동 저장", fields_dict)
            
            if success:
                gr.Info(msg)
            else:
                gr.Warning(msg)
                
            versions = database.get_project_versions(project_name)
            latest_rev = versions[0][1] if versions else None
            return gr.update(choices=versions, value=latest_rev)

        def auto_save_after_gen(project_name, description, *fields_values):
            if not project_name:
                return gr.update()
            
            keys = [
                "job_name_mod", "learning_no_mod", "learning_title_mod", "section_no_mod", "module_header_mod", "additional_info_mod",
                "out_objectives", "out_knowledge", "out_perf_content", "out_perf_steps", "out_perf_tips",
                "job_name", "additional_info", "out_ksa", "out_range", "out_assessment"
            ]
            fields_dict = dict(zip(keys, fields_values))
            database.save_version(project_name, description, fields_dict)
            
            versions = database.get_project_versions(project_name)
            latest_rev = versions[0][1] if versions else None
            return gr.update(choices=versions, value=latest_rev)

        def auto_save_obj(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 생성: 학습 목표", *fields_values)
            
        def auto_save_know(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 생성: 필요 지식", *fields_values)
            
        def auto_save_content(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 생성: 수행 내용", *fields_values)
            
        def auto_save_steps(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 생성: 수행 순서", *fields_values)
            
        def auto_save_tips(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 생성: 수행 팁", *fields_values)
            
        def auto_save_all_mod(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 일괄 생성: 학습모듈", *fields_values)
            
        def auto_save_all_ncs(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 일괄 생성: 직무 표준서", *fields_values)
            
        def auto_save_ksa(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 생성: KSA", *fields_values)
            
        def auto_save_range(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 생성: 적용범위", *fields_values)
            
        def auto_save_assessment(project_name, *fields_values):
            return auto_save_after_gen(project_name, "AI 생성: 평가방법", *fields_values)

        # 2. Individual generation buttons
        btn_gen_obj.click(
            fn=generate_obj_single,
            inputs=[job_name_mod, learning_title_mod, section_no_mod, additional_info_mod],
            outputs=[out_objectives]
        ).then(
            fn=auto_save_obj,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )
        
        btn_gen_know.click(
            fn=generate_know_single,
            inputs=[job_name_mod, learning_title_mod, section_no_mod, additional_info_mod],
            outputs=[out_knowledge]
        ).then(
            fn=auto_save_know,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )
        
        btn_gen_content.click(
            fn=generate_perf_content_single,
            inputs=[job_name_mod, learning_title_mod, section_no_mod, additional_info_mod],
            outputs=[out_perf_content]
        ).then(
            fn=auto_save_content,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )
        
        btn_gen_steps.click(
            fn=generate_perf_steps_single,
            inputs=[job_name_mod, learning_title_mod, section_no_mod, additional_info_mod],
            outputs=[out_perf_steps]
        ).then(
            fn=auto_save_steps,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )
        
        btn_gen_tips.click(
            fn=generate_perf_tips_single,
            inputs=[job_name_mod, learning_title_mod, section_no_mod, additional_info_mod],
            outputs=[out_perf_tips]
        ).then(
            fn=auto_save_tips,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )
        
        # 3. All-in-one module generator
        btn_gen_all_mod.click(
            fn=generate_all_module_stream,
            inputs=[job_name_mod, learning_no_mod, learning_title_mod, section_no_mod, module_header_mod, additional_info_mod],
            outputs=[out_objectives, out_knowledge, out_perf_content, out_perf_steps, out_perf_tips]
        ).then(
            fn=auto_save_all_mod,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )

        # --- TAB 2 Bindings (NCS Standards) ---
        
        btn_gen_all.click(
            fn=generate_all_ncs_stream,
            inputs=[job_name, additional_info],
            outputs=[out_ksa, out_range, out_assessment]
        ).then(
            fn=auto_save_all_ncs,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )
        
        btn_gen_ksa.click(
            fn=generate_ksa_single,
            inputs=[job_name, additional_info],
            outputs=[out_ksa]
        ).then(
            fn=auto_save_ksa,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )
        
        btn_gen_range.click(
            fn=generate_range_single,
            inputs=[job_name, additional_info],
            outputs=[out_range]
        ).then(
            fn=auto_save_range,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )
        
        btn_gen_assessment.click(
            fn=generate_assessment_single,
            inputs=[job_name, additional_info],
            outputs=[out_assessment]
        ).then(
            fn=auto_save_assessment,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )

        # --- Project Selector Event Bindings ---
        project_dd.change(
            fn=load_project_state,
            inputs=[project_dd],
            outputs=state_fields + [version_dd]
        )
        
        version_dd.change(
            fn=load_version_state,
            inputs=[project_dd, version_dd],
            outputs=state_fields
        )
        
        btn_new_proj.click(
            fn=handle_new_project,
            inputs=[new_proj_name],
            outputs=[project_dd, new_proj_name] + state_fields + [version_dd]
        )
        
        btn_delete_proj.click(
            fn=handle_delete_project,
            inputs=[project_dd],
            outputs=[project_dd] + state_fields + [version_dd]
        )
        
        btn_save_proj.click(
            fn=handle_save_project,
            inputs=[project_dd] + state_fields,
            outputs=[version_dd]
        )

        # --- App Load Initializer ---
        def init_app_state():
            projects = database.get_project_list()
            active_proj = projects[0] if projects else None
            return load_project_state(active_proj)
            
        app.load(
            fn=init_app_state,
            inputs=[],
            outputs=state_fields + [version_dd]
        )
        
    return app
