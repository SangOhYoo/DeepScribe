# Set path to ui.py
$uiPath = "abyss_writer/ui.py"

# Read file contents using CP949/ANSI encoding to preserve Korean characters correctly
$enc = [System.Text.Encoding]::GetEncoding(949)
$content = [System.IO.File]::ReadAllText($uiPath, $enc)

# Define target corrupted string to replace
$target = @"
            strategy = stdef generate_novel_from_erotic_case(
    project_str,
    female_desc,
    male_desc,
    relations_desc,
    situation_desc,
    case_title,
    case_content,
    case_meta,
    user_instruction,
    system_prompt,
    positive_prompt,
    negative_prompt,
    target_node_id=None
):
    if not project_str:
        gr.Warning("선택한 프로젝트가 없습니다.")
        return "선택한 프로젝트가 없습니다."
    if not case_title or not case_title.strip() or not case_content or not case_content.strip():
        gr.Warning("작성할 대상 케이스를 먼저 선택해 주세요.")
        return "작성할 대상 케이스를 먼저 선택해 주세요."
        
    pid = parse_project_id(project_str)
    
    # Save a HistoryLog record for the novel generation audit trail.
    try:
        from models import db_session, HistoryLog
        history_log = HistoryLog(
            scenario_node_id=target_node_id,
            action_type="generate_novel_from_case",
            user_prompt=f"Case Title: {case_title}\n\nInstruction: {user_instruction}",
            before_content="",
            after_content="",
            created_at=datetime.utcnow()
        )
        db_session.add(history_log)
        db_session.commit()
    except Exception as e:
        print("Error saving pre-generation HistoryLog:", e)

    # Compile dynamic prompt variables
    prompt_variables = {
        "female_desc": female_desc or "정보 없음",
        "male_desc": male_desc or "정보 없음",
        "relations_desc": relations_desc or "정보 없음",
        "situation_desc": situation_desc or "정보 없음",
        "case_title": case_title,
        "case_content": case_content,
        "case_meta": case_meta or ""
    }
    
    # Resolve project-level fallbacks if prompt settings are blank
    resolved_sys = system_prompt if system_prompt and system_prompt.strip() else DEFAULT_SYSTEM_PROMPT
    resolved_pos = positive_prompt if positive_prompt and positive_prompt.strip() else ""
    resolved_neg = negative_prompt if negative_prompt and negative_prompt.strip() else ""
    
    # Construct final generation prompt
    formatted_user = f"""[등장인물 및 관계 설정]
여성: {female_desc or '정보 없음'}
남성: {male_desc or '정보 없음'}
관계성: {relations_desc or '정보 없음'}

[미션 상황 및 전개 조건]
상황: {situation_desc or '정보 없음'}

[개별 시나리오 케이스 정보]
제목: {case_title}
상황 요약: {case_content}
추가 메타데이터: {case_meta or '없음'}

[추가 작사 조건]
{user_instruction or '없음'}

위 정보를 바탕으로 한 편의 완성도 높은 관능 소설의 씬을 유려하고 상세하게 작성하라.
"""

    try:
        draft = llama_client.send_chat_completion(
            system_prompt=resolved_sys,
            user_prompt=formatted_user,
            temperature=0.85
        )
        
        final_scene = str(draft or "")
        
        # Update target ScenarioNode if it exists
        if target_node_id:
            node = db_session.query(ScenarioNode).filter(ScenarioNode.id == target_node_id).first()
            if node:
                node.content = final_scene
                db_session.commit()
                
        # Update the HistoryLog entry with the generated text after successful model return
        try:
            history_log.after_content = final_scene
            db_session.commit()
        except Exception as e:
            print("Error updating HistoryLog after generation:", e)
            
        gr.Info("소설 본문 작성이 완료되었습니다!")
        return final_scene
    except Exception as e:
        print("Error in generate_novel_from_erotic_case:", e)
        gr.Warning(f"본문 작성 중 오류가 발생했습니다: {str(e)}")
        return f"❌ 오류 발생: {str(e)}"음과 같은 '심리적 층위'에 따라 케이스를 나누어 작성하라.
"@

# Define correct replacement string
$replacement = @"
            strategy = strategy_match.group(1).strip()
            
        desc_match = re.search(r'상세 묘사\s*[\:\-]\s*(.*?)(?=\n\s*(?:심리적 전략|자극 포인트)|$)', case_body, re.DOTALL)
        if desc_match:
            description = desc_match.group(1).strip()
            
        trigger_match = re.search(r'자극 포인트\s*[\:\-]\s*(.*?)(?=\n\s*(?:심리적 전략|상세 묘사)|$)', case_body, re.DOTALL)
        if trigger_match:
            trigger = trigger_match.group(1).strip()
            
        if not description:
            description = case_body
            
        cases.append({
            "number": case_num,
            "title": case_title,
            "strategy": strategy,
            "description": description,
            "trigger": trigger
        })
        
    return cases

def generate_psychological_scenarios_stream(
    project_str, 
    female_desc, 
    male_desc, 
    relations_desc, 
    situation_desc,
    num_cases,
    sensory_enabled,
    contrast_enabled,
    buildup_enabled
):
    if not situation_desc.strip():
        yield "⚠️ 미션 상황을 입력해 주세요.", [], gr.update(choices=[], value=None)
        return
        
    system_prompt = (
        "역할: 당신은 인간의 복잡한 심리와 관능적 긴장감을 상세하게 묘사하는 전문 시나리오 작가이자 심리 분석가입니다. "
        "상황을 철저히 분석하고 관능적인 씬을 구성하는 능력이 매우 뛰어납니다."
    )
    
    user_prompt = f"""아래 설정을 바탕으로 상황을 여러 시나리오 케이스로 {num_cases}개로 분화하여 작성하라.

[대상 캐릭터 및 관계 설정]
- 여성 캐릭터: {female_desc}
- 남성 캐릭터: {male_desc}
- relations_desc: {relations_desc}

[미션 상황]
- 특정 상황: {situation_desc}

[시나리오 분화 가이드라인]
단순히 나열하지 말고, 다음과 같은 '심리적 층위'에 따라 케이스를 나누어 작성하라.
"@

# Replace
if ($content.Contains($target)) {
    Write-Host "Target content found, replacing..."
    $content = $content.Replace($target, $replacement)
    # Write back as UTF-8
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($uiPath, $content, $utf8NoBom)
    Write-Host "ui.py successfully repaired and saved as UTF-8!"
} else {
    Write-Host "Error: Target content not found in ui.py!"
}
