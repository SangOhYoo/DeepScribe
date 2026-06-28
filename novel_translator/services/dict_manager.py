import csv
import os
import gradio as gr
import sqlite3
from novel_translator.services.onomatopoeia_db import OnomatopoeiaDB


_csv_cache = {"mtime": 0, "rows": [], "header": [], "lookup": {}}

def _read_csv_cached(file_path):
    global _csv_cache
    if not os.path.exists(file_path):
        return [], [], {}
        
    mtime = os.path.getmtime(file_path)
    if mtime == _csv_cache["mtime"] and _csv_cache["rows"]:
        return _csv_cache["header"], _csv_cache["rows"], _csv_cache["lookup"]
        
    rows = []
    header = []
    lookup = {}
    content = None
    for encoding in ["utf-8-sig", "utf-8", "cp949", "shift_jis", "euc-kr"]:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()
            break
        except Exception:
            continue
            
    if content:
        reader = csv.reader(content.splitlines())
        for row_num, row in enumerate(reader, 1):
            if not row or len(row) < 2:
                continue
            if row_num == 1 and row[0].lower() in ("source", "원문", "원어"):
                header = row
                continue
            rows.append(row)
            source_word = row[0].strip()
            if source_word:
                lookup[source_word] = row
            
    _csv_cache["mtime"] = mtime
    _csv_cache["rows"] = rows
    _csv_cache["header"] = header
    _csv_cache["lookup"] = lookup
    return header, rows, lookup

def invalidate_csv_cache():
    global _csv_cache
    _csv_cache = {"mtime": 0, "rows": [], "header": [], "lookup": {}}

def load_current_dictionary(file_path, search_term="", page=1, page_size=100):
    import pandas as pd
    import math

    COLUMNS = ["원어", "추천 번역", "설명/문맥", "원어 예문", "기존 번역(오답)", "추천 번역(정답)"]
    _, all_rows, _ = _read_csv_cached(file_path)

    # 검색어가 없으면 초기 로딩으로 간주, 빈 테이블과 안내 메시지 반환
    if not search_term.strip() and not all_rows:
         return pd.DataFrame(columns=COLUMNS), "0 / 0 페이지 (총 0개)", 1, 1
    if not search_term.strip():
        df = pd.DataFrame([["", "상단 검색창에 검색어를 입력하고 '검색' 버튼을 누르세요.", "", "", "", ""]], columns=COLUMNS)
        total_rows = len(all_rows)
        return df, f"1 / ? 페이지 (총 {total_rows}개)", 1, 1

    # 검색어 필터링
    search_lower = search_term.strip().lower()
    filtered_rows = [
        r for r in all_rows if len(r) >= 2 and (search_lower in r[0].lower() or search_lower in r[1].lower())
    ]

    # 페이지네이션
    total_rows = len(filtered_rows)
    total_pages = max(1, math.ceil(total_rows / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_rows = filtered_rows[start_idx:end_idx]
    
    padded_rows = []
    for r in paginated_rows:
        padded = r + [""] * (6 - len(r))
        padded_rows.append(padded[:6])
        
    df = pd.DataFrame(padded_rows, columns=COLUMNS) if padded_rows else pd.DataFrame(columns=COLUMNS)
    page_info = f"{page} / {total_pages} 페이지 (총 {total_rows}개)"
    return df, page_info, page, total_pages

def get_pending_choices(db_path):
    """Fetch words that are pending review."""
    db = OnomatopoeiaDB(db_path)
    pending = db.get_pending_review()
    choices = [item["word"] for item in pending]
    return gr.update(choices=choices, value=choices[0] if choices else None)

def load_pending_word_details(word, db_path):
    """Load details of a selected pending word."""
    if not word:
        return "", "", "", "", "", ""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pending_words WHERE word = ?", (word,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return (
                row["word"],
                row["suggested_translation"] or "",
                row["notes"] or "",
                row["example_source"] or "",
                row["example_wrong"] or "",
                row["example_correct"] or "",
            )
    except Exception as e:
        print(f"Error loading pending word details: {e}")
    return "", "", "", "", "", ""

def reject_pending_word(word, db_path):
    """Reject a word: set DB status to rejected."""
    if not word:
        return "❌ 오류: 선택된 단어가 없습니다.", gr.update()
    try:
        db = OnomatopoeiaDB(db_path)
        db.set_status(word, "rejected")
        return f"❌ '{word}' 반려 완료.", get_pending_choices(db_path)
    except Exception as e:
        print(f"Error rejecting word '{word}': {e}")
        return f"❌ 반려 처리 오류: {e}", gr.update()

def get_registered_choices(file_path):
    import gradio as gr
    _, rows, _ = _read_csv_cached(file_path)
    choices = []
    for r in rows:
        if r and len(r) >= 2:
            word = r[0].strip()
            trans = r[1].strip()
            choices.append((f"{word} -> {trans}", word))
    return gr.update(choices=choices, value=choices[0][1] if choices else None)

def load_registered_word_details(word, file_path):
    import gradio as gr
    if not word:
        return gr.update(value=""), gr.update(value=""), gr.update(value=""), gr.update(value=""), gr.update(value=""), gr.update(value="")
        
    _, _, lookup = _read_csv_cached(file_path)
    r = lookup.get(word.strip())

    if r:
        padded = r + [""] * (7 - len(r))
        return (
            gr.update(value=padded[0]),
            gr.update(value=padded[1]),
            gr.update(value=padded[2]),
            gr.update(value=padded[4]),
            gr.update(value=padded[5]),
            gr.update(value=padded[6])
        )
    return gr.update(value=""), gr.update(value=""), gr.update(value=""), gr.update(value=""), gr.update(value=""), gr.update(value="")

def approve_pending_word(word, translation, notes, ex_src, ex_wrong, ex_correct, file_path):
    import gradio as gr
    from novel_translator.services.onomatopoeia_db import OnomatopoeiaDB
    
    if not word or not translation:
        return "❌ 오류: 단어와 추천 번역은 필수 입력 항목입니다.", gr.update(), [], gr.update()
        
    word_clean = word.strip()
    already_exists = False
    
    if os.path.exists(file_path):
        _, cached_rows, _ = _read_csv_cached(file_path)
        existing_words = {r[0].strip() for r in cached_rows if r}
        if word_clean in existing_words:
            already_exists = True
            
    try:
        if not already_exists:
            with open(file_path, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([word_clean, translation.strip(), notes.strip(), "의성어", ex_src.strip(), ex_wrong.strip(), ex_correct.strip()])
            invalidate_csv_cache()
        db_path = os.path.join(os.path.dirname(file_path), "novel_translator", "onomatopoeia.db")
        db_path = os.path.abspath(db_path)
        db = OnomatopoeiaDB(db_path)
        # 승인된 단어는 DB에서 삭제하여 'pending_words' 테이블이 불필요하게 커지는 것을 방지합니다.
        db.delete_word(word_clean)
        
        pending_choices = get_pending_choices(db_path)
        registered_choices_update = get_registered_choices(file_path)
        # dict_view_update는 이제 페이지네이션되므로, UI 업데이트가 필요합니다. 여기서는 비워둡니다.
        
        status_msg = f"✅ '{word_clean}'이(가) 승인 및 사전에 등록되었습니다." if not already_exists \
            else f"✅ '{word_clean}'이(가) 승인 처리되어 대기열에서 삭제되었습니다 (이미 사전에 등록된 단어)."
        return status_msg, registered_choices_update, pending_choices, gr.update()
        
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", gr.update(), [], gr.update()

def approve_all_pending_words(file_path):
    import gradio as gr
    from novel_translator.services.onomatopoeia_db import OnomatopoeiaDB
    
    db_path = os.path.join(os.path.dirname(file_path), "novel_translator", "onomatopoeia.db")
    db_path = os.path.abspath(db_path)
    db = OnomatopoeiaDB(db_path)
    pending = db.get_pending_review()
    if not pending:
        return "ℹ️ 승인 대기 중인 단어가 없습니다.", gr.update(), [], gr.update()
        
    try:
        _, cached_rows, _ = _read_csv_cached(file_path)
        existing_words = {r[0].strip() for r in cached_rows if r}
        
        added_count = 0
        with open(file_path, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            for item in pending:
                w = item["word"].strip()
                t = (item["suggested_translation"] or "").strip()
                n = (item["notes"] or "").strip()
                if w not in existing_words:
                    writer.writerow([w, t, n, "의성어", "", "", ""])
                    existing_words.add(w)
                    added_count += 1
                # 승인된 단어는 DB에서 삭제합니다.
                db.delete_word(w)
                
        invalidate_csv_cache()

        pending_choices = get_pending_choices(db_path)
        registered_choices_update = get_registered_choices(file_path)
        # dict_view_update는 이제 페이지네이션되므로, UI 업데이트가 필요합니다. 여기서는 비워둡니다.
        
        return f"✅ {len(pending)}개 대기 단어 승인 완료 (신규 사전 등록: {added_count}개)", registered_choices_update, pending_choices, gr.update()
        
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", gr.update(), [], gr.update()

def update_registered_word(word, translation, notes, ex_src, ex_wrong, ex_correct, file_path):
    import gradio as gr
    if not word:
        return "❌ 오류: 수정할 단어가 선택되지 않았습니다.", gr.update(), gr.update()
        
    try:
        header, cached_rows, _ = _read_csv_cached(file_path)
        rows = list(cached_rows)
        
        updated = False
        for idx, r in enumerate(rows):
            if r and r[0].strip() == word.strip():
                rows[idx] = [word.strip(), translation.strip(), notes.strip(), "의성어", ex_src.strip(), ex_wrong.strip(), ex_correct.strip()]
                updated = True
                break
                
        if not updated:
            return f"❌ 오류: 사전에서 '{word}'을(가) 찾을 수 없습니다.", gr.update(), gr.update()
            
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if header:
                writer.writerow(header)
            else:
                writer.writerow(["source", "target", "category", "notes", "example_source", "example_wrong", "example_correct"])
            writer.writerows(rows)
            
        invalidate_csv_cache()

        registered_choices_update = get_registered_choices(file_path)
        # dict_view_update는 이제 페이지네이션되므로, UI 업데이트가 필요합니다. 여기서는 비워둡니다.
        
        return f"✅ '{word}' 단어가 수정되었습니다.", registered_choices_update, gr.update()
        
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", gr.update(), gr.update()

def delete_registered_word(word, file_path):
    import gradio as gr
    if not word:
        return "❌ 오류: 삭제할 단어가 선택되지 않았습니다.", gr.update(), gr.update()
        
    try:
        header, cached_rows, _ = _read_csv_cached(file_path)
        rows = list(cached_rows)
        
        original_len = len(rows)
        rows = [r for r in rows if r and r[0].strip() != word.strip()]
        
        if len(rows) == original_len:
            return f"❌ 오류: 사전에서 '{word}'을(가) 찾을 수 없습니다.", gr.update(), gr.update()
            
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if header:
                writer.writerow(header)
            else:
                writer.writerow(["source", "target", "category", "notes", "example_source", "example_wrong", "example_correct"])
            writer.writerows(rows)
            
        invalidate_csv_cache()

        registered_choices_update = get_registered_choices(file_path)
        # dict_view_update는 이제 페이지네이션되므로, UI 업데이트가 필요합니다. 여기서는 비워둡니다.
        
        return f"✅ '{word}' 단어가 삭제되었습니다.", registered_choices_update, gr.update()
        
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", gr.update(), gr.update()
