import csv
import os

_csv_cache = {"mtime": 0, "rows": [], "header": []}

def _read_csv_cached(file_path):
    global _csv_cache
    if not os.path.exists(file_path):
        return [], []
        
    mtime = os.path.getmtime(file_path)
    if mtime == _csv_cache["mtime"] and _csv_cache["rows"]:
        return _csv_cache["header"], _csv_cache["rows"]
        
    rows = []
    header = []
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
            
    _csv_cache["mtime"] = mtime
    _csv_cache["rows"] = rows
    _csv_cache["header"] = header
    return header, rows

def invalidate_csv_cache():
    global _csv_cache
    _csv_cache = {"mtime": 0, "rows": [], "header": []}

def load_current_dictionary(file_path):
    import pandas as pd
    _, rows = _read_csv_cached(file_path)
    if not rows:
        return pd.DataFrame(columns=["원어", "추천 번역", "설명/문맥", "원어 예문", "기존 번역(오답)", "추천 번역(정답)"])
    
    padded_rows = []
    for r in rows:
        padded = r + [""] * (6 - len(r))
        padded_rows.append(padded[:6])
        
    df = pd.DataFrame(padded_rows, columns=["원어", "추천 번역", "설명/문맥", "원어 예문", "기존 번역(오답)", "추천 번역(정답)"])
    return df

def get_registered_choices(file_path):
    import gradio as gr
    _, rows = _read_csv_cached(file_path)
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
        
    _, rows = _read_csv_cached(file_path)
    for r in rows:
        if r and r[0].strip() == word.strip():
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

def approve_pending_word(word, translation, notes, ex_src, ex_wrong, ex_correct, file_path, orchestrator):
    import gradio as gr
    from novel_translator.services.onomatopoeia_db import OnomatopoeiaDB
    
    if not word or not translation:
        return "❌ 오류: 단어와 추천 번역은 필수 입력 항목입니다.", gr.update(), [], gr.update()
        
    word_clean = word.strip()
    already_exists = False
    
    if os.path.exists(file_path):
        _, cached_rows = _read_csv_cached(file_path)
        existing_words = {r[0].strip() for r in cached_rows if r}
        if word_clean in existing_words:
            already_exists = True
            
    try:
        if not already_exists:
            with open(file_path, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([word_clean, translation.strip(), notes.strip(), "의성어", ex_src.strip(), ex_wrong.strip(), ex_correct.strip()])
            invalidate_csv_cache()
            if orchestrator:
                orchestrator.reload_onomatopoeia()
        db_path = os.path.join(os.path.dirname(file_path), "novel_translator", "onomatopoeia.db")
        db_path = os.path.abspath(db_path)
        db = OnomatopoeiaDB(db_path)
        db.set_status(word_clean, "approved")
        
        from novel_translator.app import get_pending_choices # lazy import
        pending_choices = get_pending_choices()
        registered_choices_update = get_registered_choices(file_path)
        dict_view_update = load_current_dictionary(file_path)
        
        status_msg = f"✅ '{word_clean}'이(가) 승인 및 등록되었습니다." if not already_exists else f"✅ '{word_clean}'의 DB 상태가 승인됨으로 변경되었습니다 (이미 사전에 등록되어 있음)."
        return status_msg, registered_choices_update, pending_choices, dict_view_update
        
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", gr.update(), [], gr.update()

def approve_all_pending_words(file_path, orchestrator):
    import gradio as gr
    from novel_translator.services.onomatopoeia_db import OnomatopoeiaDB
    
    db_path = os.path.join(os.path.dirname(file_path), "novel_translator", "onomatopoeia.db")
    db_path = os.path.abspath(db_path)
    db = OnomatopoeiaDB(db_path)
    pending = db.get_pending_review()
    if not pending:
        return "ℹ️ 승인 대기 중인 단어가 없습니다.", gr.update(), [], gr.update()
        
    try:
        _, cached_rows = _read_csv_cached(file_path)
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
                db.set_status(w, "approved")
                
        invalidate_csv_cache()
        if orchestrator:
            orchestrator.reload_onomatopoeia()
            
        from novel_translator.app import get_pending_choices
        pending_choices = get_pending_choices()
        registered_choices_update = get_registered_choices(file_path)
        dict_view_update = load_current_dictionary(file_path)
        
        return f"✅ {len(pending)}개 대기 단어 승인 완료 (신규 사전 등록: {added_count}개)", registered_choices_update, pending_choices, dict_view_update
        
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", gr.update(), [], gr.update()

def update_registered_word(word, translation, notes, ex_src, ex_wrong, ex_correct, file_path, orchestrator):
    import gradio as gr
    if not word:
        return "❌ 오류: 수정할 단어가 선택되지 않았습니다.", gr.update(), gr.update()
        
    try:
        header, cached_rows = _read_csv_cached(file_path)
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
        if orchestrator:
            orchestrator.reload_onomatopoeia()
            
        registered_choices_update = get_registered_choices(file_path)
        dict_view_update = load_current_dictionary(file_path)
        
        return f"✅ '{word}' 단어가 수정되었습니다.", registered_choices_update, dict_view_update
        
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", gr.update(), gr.update()

def delete_registered_word(word, file_path, orchestrator):
    import gradio as gr
    if not word:
        return "❌ 오류: 삭제할 단어가 선택되지 않았습니다.", gr.update(), gr.update()
        
    try:
        header, cached_rows = _read_csv_cached(file_path)
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
        if orchestrator:
            orchestrator.reload_onomatopoeia()
            
        registered_choices_update = get_registered_choices(file_path)
        dict_view_update = load_current_dictionary(file_path)
        
        return f"✅ '{word}' 단어가 삭제되었습니다.", registered_choices_update, dict_view_update
        
    except Exception as e:
        return f"❌ 오류 발생: {str(e)}", gr.update(), gr.update()
