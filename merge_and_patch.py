import shutil
import re

# 1. Copy dry_run_temp ui.py to abyss_writer/ui.py
src = "d:/DeepScribe/dry_run_temp/abyss_writer/ui.py"
dst = "d:/DeepScribe/abyss_writer/ui.py"
shutil.copyfile(src, dst)

# 2. Read the copied ui.py
with open(dst, "r", encoding="utf-8", errors="ignore") as f:
    code = f.read()

# 3. Define all search patterns and replacements from patch_ui.py

get_main_char_pattern = r"(def get_character_names\(project_str\):.*?return \[c\.name for c in characters\].*?except Exception as e:.*?return \[\]\s*)"
new_get_main_char = """def get_character_names(project_str):
    if not project_str:
        return []
    pid = parse_project_id(project_str)
    try:
        characters = db_session.query(Character).filter(Character.project_id == pid).all()
        return [c.name for c in characters]
    except Exception as e:
        print("Error getting character names:", e)
        return []

def get_main_character_names(project_str):
    if not project_str:
        return []
    pid = parse_project_id(project_str)
    try:
        characters = db_session.query(Character).filter(
            Character.project_id == pid,
            Character.relations.in_(["male_hero", "female_hero"])
        ).all()
        return [c.name for c in characters]
    except Exception as e:
        print("Error getting main character names:", e)
        return []

def update_active_characters_checkbox(project_str):
    all_names = get_character_names(project_str)
    main_names = get_main_character_names(project_str)
    return gr.update(choices=all_names, value=main_names)

"""

on_char_select_pattern = r"def on_character_select_change\(char_id\):.*?return \"\", \"other\", \"\", \"\", \"\", \"\""
new_on_char_select = """def on_character_select_change(char_id):
    if not char_id:
        return "", "other", "", "", "", "", "", "", "", "", ""
    try:
        char = db_session.query(Character).filter(Character.id == char_id).first()
        if char:
            return (
                char.name or "",
                char.relations or "other",
                char.personality or "",
                char.background or "",
                char.character_relations or "",
                char.speech_style or "",
                char.physical_signature or "",
                char.psychological_trigger or "",
                char.behavioral_quirks or "",
                char.secret_taboo or "",
                char.signature_quotes or ""
            )
    except Exception as e:
        print("Error loading character details:", e)
    return "", "other", "", "", "", "", "", "", "", "", "" """

save_or_update_pattern = r"def save_or_update_character\(project_str, char_id, name, role, personality, background, relations_desc, speech_style\):.*?return gr\.update\(\), gr\.update\(\), name, role, personality, background, relations_desc, speech_style"
new_save_or_update = """def save_or_update_character(
    project_str, char_id, name, role, personality, background, relations_desc, speech_style,
    physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes
):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return (
            gr.update(), gr.update(), name, role, personality, background, relations_desc, speech_style,
            physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes
        )
    if not name.strip():
        gr.Warning("이름을 입력해 주세요.")
        return (
            gr.update(), gr.update(), name, role, personality, background, relations_desc, speech_style,
            physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes
        )
        
    pid = parse_project_id(project_str)
    try:
        char = None
        if char_id:
            char = db_session.query(Character).filter(Character.id == char_id).first()
        
        if char:
            char.name = name.strip()
            char.relations = role
            char.personality = personality.strip()
            char.background = background.strip()
            char.character_relations = relations_desc.strip()
            char.speech_style = speech_style.strip()
            char.physical_signature = physical_signature.strip() if physical_signature else ""
            char.psychological_trigger = psychological_trigger.strip() if psychological_trigger else ""
            char.behavioral_quirks = behavioral_quirks.strip() if behavioral_quirks else ""
            char.secret_taboo = secret_taboo.strip() if secret_taboo else ""
            char.signature_quotes = signature_quotes.strip() if signature_quotes else ""
            db_session.commit()
            gr.Info(f"등장인물 '{char.name}'의 정보가 수정되었습니다.")
        else:
            char = Character(
                project_id=pid,
                name=name.strip(),
                relations=role,
                personality=personality.strip(),
                background=background.strip(),
                character_relations=relations_desc.strip(),
                speech_style=speech_style.strip(),
                physical_signature=physical_signature.strip() if physical_signature else "",
                psychological_trigger=psychological_trigger.strip() if psychological_trigger else "",
                behavioral_quirks=behavioral_quirks.strip() if behavioral_quirks else "",
                secret_taboo=secret_taboo.strip() if secret_taboo else "",
                signature_quotes=signature_quotes.strip() if signature_quotes else ""
            )
            db_session.add(char)
            db_session.commit()
            gr.Info(f"새로운 등장인물 '{char.name}'이 추가되었습니다.")
            
        choices = get_character_dropdown_choices(project_str)
        return (
            gr.update(choices=choices, value=char.id), gr.update(), name, role, personality, background, relations_desc, speech_style,
            physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes
        )
    except Exception as e:
        print("Error saving character:", e)
        gr.Warning("등장인물 저장 중 오류가 발생했습니다.")
        return (
            gr.update(), gr.update(), name, role, personality, background, relations_desc, speech_style,
            physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes
        )"""

insert_helper_pattern = r"(def save_or_update_character\(.*?)\n(def save_project_settings)"
new_helpers = """def add_new_blank_character(project_str):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), "", "other", "", "", "", "", "", "", "", "", ""
    pid = parse_project_id(project_str)
    try:
        new_char = Character(
            project_id=pid,
            name="새 인물",
            relations="other",
            personality="예: 완벽주의, 냉혈함",
            background="예: 인정욕구, 타인에 대한 뿌리 깊은 불신",
            character_relations="표면적 역학 vs 무의식적 긴장, 결핍의 상호작용 등",
            speech_style="공적인 공간/사적인 공간에서의 호칭과 말투 변화",
            physical_signature="예: 살결에서 나는 은은한 장미 향, 왼쪽 쇄골 아래의 흉터",
            psychological_trigger="예: 상대가 귓속말을 속삭이거나 손목을 가볍게 쥘 때 통제력을 잃음",
            behavioral_quirks="예: 곤란할 때면 손끝을 깨물거나 귀가 빨개짐",
            secret_taboo="예: 과거 스승과의 은밀한 거래 사실",
            signature_quotes="예: '무슨 질문이 그러시죠? 불쾌하네요.'"
        )
        db_session.add(new_char)
        db_session.commit()
        
        choices = get_character_dropdown_choices(project_str)
        gr.Info("새로운 인물이 추가되었습니다. 정보를 입력하고 저장해 주세요.")
        return (
            gr.update(choices=choices, value=new_char.id),
            new_char.name,
            new_char.relations,
            new_char.personality,
            new_char.background,
            new_char.character_relations,
            new_char.speech_style,
            new_char.physical_signature,
            new_char.psychological_trigger,
            new_char.behavioral_quirks,
            new_char.secret_taboo,
            new_char.signature_quotes
        )
    except Exception as e:
        print("Error adding blank character:", e)
        return gr.update(), "", "other", "", "", "", "", "", "", "", "", ""

def delete_selected_character(project_str, char_id):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), "", "other", "", "", "", "", "", "", "", "", ""
    if not char_id:
        gr.Warning("삭제할 등장인물이 선택되지 않았습니다.")
        return gr.update(), "", "other", "", "", "", "", "", "", "", "", ""
        
    try:
        char = db_session.query(Character).filter(Character.id == char_id).first()
        if char:
            db_session.delete(char)
            db_session.commit()
            gr.Info("해당 등장인물이 삭제되었습니다.")
    except Exception as e:
        print("Error deleting character:", e)
        gr.Warning("등장인물 삭제 중 오류가 발생했습니다.")
        
    choices = get_character_dropdown_choices(project_str)
    return load_project_details(project_str)

def load_project_details(project_str):
    if not project_str:
        return (
            "", "other", "", "", "", "", "", "", "", "", "",
            gr.update(choices=[], value=None), gr.update(),
            "", "", "", "",
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            "", "",
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=[])
        )
    pid = parse_project_id(project_str)
    
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        gr.Warning("선택한 프로젝트를 데이터베이스에서 찾을 수 없습니다. 올바른 프로젝트를 선택해주세요.")
        return (
            "", "other", "", "", "", "", "", "", "", "", "",
            gr.update(choices=[], value=None), gr.update(),
            "", "", "", "",
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            "", "",
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=[])
        )
        
    choices = get_character_dropdown_choices(project_str)
    first_char_id = choices[0][1] if choices else None
    
    res = on_character_select_change(first_char_id)
    c_name, c_role, c_personality, c_background, c_relations, c_speech_style = res[:6]
    c_physical, c_trigger, c_quirks, c_secret, c_quotes = res[6:]
    
    system_prompt = proj.system_prompt or ""
    overall_plot = proj.overall_plot or ""
    positive_prompt = proj.positive_prompt or ""
    negative_prompt = proj.negative_prompt or ""
    
    ver_choices = get_prompt_version_choices(project_str)
    default_ver = ver_choices[0] if ver_choices else None
    
    stages = ["기 (起 - 도입)", "승 (承 - 전개)", "전 (轉 - 위기/절정)", "결 (結 - 결말)"]
    node_choices = get_node_choices_for_stage(pid, stages[0])
    default_node = node_choices[0][1] if node_choices else None
    
    scen_ver_choices = build_commit_tree_choices(pid, stages[0], default_node)
    default_scen_ver = max(scen_ver_choices, key=lambda x: x[1])[1] if scen_ver_choices else None
    
    scen_content = ""
    scen_title = ""
    if default_scen_ver:
        node = db_session.query(ScenarioNode).filter(ScenarioNode.id == default_scen_ver).first()
        if node:
            scen_content = node.content
            scen_title = node.title or ""
            
    target_scen_choices = get_target_scenario_node_choices(project_str)
    default_target_scen = target_scen_choices[0][1] if target_scen_choices else None
 
    scene_history_choices = get_scene_history_choices(project_str, default_target_scen)
    default_scene_history = scene_history_choices[0][1] if scene_history_choices else None
            
    if first_char_id:
        return (
            c_name, c_role, c_personality, c_background, c_relations, c_speech_style,
            c_physical, c_trigger, c_quirks, c_secret, c_quotes,
            gr.update(choices=choices, value=first_char_id),
            gr.update(),
            system_prompt, overall_plot,
            positive_prompt, negative_prompt,
            gr.update(choices=ver_choices, value=default_ver),
            gr.update(choices=stages, value=stages[0]),
            gr.update(choices=node_choices, value=default_node),
            gr.update(choices=scen_ver_choices, value=default_scen_ver),
            scen_content,
            scen_title,
            gr.update(choices=scene_history_choices, value=default_scene_history),
            gr.update(choices=target_scen_choices, value=default_target_scen),
            update_active_characters_checkbox(project_str)
        )
    else:
        return (
            "", "other", "", "", "", "", "", "", "", "", "",
            gr.update(choices=choices, value=None),
            gr.update(),
            system_prompt, overall_plot,
            positive_prompt, negative_prompt,
            gr.update(choices=ver_choices, value=default_ver),
            gr.update(choices=stages, value=stages[0]),
            gr.update(choices=node_choices, value=default_node),
            gr.update(choices=scen_ver_choices, value=default_scen_ver),
            scen_content,
            scen_title,
            gr.update(choices=scene_history_choices, value=default_scene_history),
            gr.update(choices=target_scen_choices, value=default_target_scen),
            update_active_characters_checkbox(project_str)
        )
"""

api_gen_chars_pattern = r"def api_generate_characters\(project_str\):.*?name, role, personality, background, relations_desc, speech_style = on_character_select_change\(first_char_id\).*?return gr\.update\(choices=choices, value=first_char_id\), name, role, personality, background, relations_desc, speech_style"
new_api_gen_chars = """def api_generate_characters(project_str):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), "", "other", "", "", "", "", "", "", "", "", ""
        
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        gr.Warning("프로젝트를 찾을 수 없습니다.")
        return gr.update(), "", "other", "", "", "", "", "", "", "", "", ""
        
    gr.Info("AI 등장인물 프로필 생성을 시작합니다...")
    client = synthesizer.client
    
    system_instruction = (
        "You are an expert novel planner. "
        "Your task is to analyze the overall plot and genre of a novel, and design compelling character profiles and relationships. "
        "You must generate exactly: "
        "1. One Male Hero (남자 주인공): name, personality (가면), background (결핍), character_relations (관계 역학), speech_style (말투), physical_signature (신체적 시그니처), psychological_trigger (심리적 아킬레스건), behavioral_quirks (무의식적 행동 버릇), secret_taboo (숨겨진 비밀/금기), signature_quotes (시그니처 대사). "
        "2. One Female Hero (여자 주인공): name, personality, background, character_relations, speech_style, physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes. "
        "3. One Male Supporting character (남자 조연): name, personality, background, character_relations, speech_style, physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes. "
        "4. One Female Supporting character (여자 조연): name, personality, background, character_relations, speech_style, physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes. "
        "5. One Other character (기타): name, personality, background, character_relations, speech_style, physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes. "
        "You must output the result strictly in JSON format. Do not write any markdown outside the JSON."
    )
    
    user_prompt = (
        f"소설 제목: {proj.title}\\n"
        f"장르: {proj.genre or '드라마'}\\n"
        f"전체 소설 줄거리:\\n{proj.overall_plot or '줄거리 없음'}\\n\\n"
        f"Please design the characters and their relationships according to the story. "
        f"The output must be a valid JSON object with the following schema:\\n"
        f"{{\\n"
        f"  \\\"male_hero\\\": {{\\n"
        f"    \\\"name\\\": \\\"이름/나이/지위 (예: 강이현 / 34세 / 본부장)\\\",\\n"
        f"    \\\"personality\\\": \\\"겉으로 드러나는 가면 (표면적 성격)\\\",\\n"
        f"    \\\"background\\\": \\\"숨겨진 결핍 및 본능\\\",\\n"
        f"    \\\"character_relations\\\": \\\"심층 역학 (표면적 역학 vs 무의식적 긴장 등)\\\",\\n"
        f"    \\\"speech_style\\\": \\\"공적인 공간 vs 사적인 공간 호칭과 말투 변화\\\",\\n"
        f"    \\\"physical_signature\\\": \\\"신체적 시그니처 및 고유 체향 (예: 살결에서 나는 은은한 장미 향, 왼쪽 쇄골 아래의 흉터)\\\",\\n"
        f"    \\\"psychological_trigger\\\": \\\"심리적/성적 아킬레스건 (예: 상대가 귓속말을 속삭이거나 손목을 가볍게 쥘 때 통제력을 잃음)\\\",\\n"
        f"    \\\"behavioral_quirks\\\": \\\"무의식적 행동 버릇 (예: 곤란할 때면 손끝을 깨물거나 귀가 빨개짐)\\\",\\n"
        f"    \\\"secret_taboo\\\": \\\"숨겨진 비밀과 금기 (예: 과거 스승과의 은밀한 거래 사실)\\\",\\n"
        f"    \\\"signature_quotes\\\": \\\"시그니처 대사 톤 샘플 (예: '무슨 질문이 그러시죠? 불쾌하네요.')\\\"\\n"
        f"  }},\\n"
        f"  \\\"female_hero\\\": {{\\n"
        f"    \\\"name\\\": \\\"...\\\",\\n"
        f"    \\\"personality\\\": \\\"...\\\",\\n"
        f"    \\\"background\\\": \\\"...\\\",\\n"
        f"    \\\"character_relations\\\": \\\"...\\\",\\n"
        f"    \\\"speech_style\\\": \\\"...\\\",\\n"
        f"    \\\"physical_signature\\\": \\\"...\\\",\\n"
        f"    \\\"psychological_trigger\\\": \\\"...\\\",\\n"
        f"    \\\"behavioral_quirks\\\": \\\"...\\\",\\n"
        f"    \\\"secret_taboo\\\": \\\"...\\\",\\n"
        f"    \\\"signature_quotes\\\": \\\"...\\\"\\n"
        f"  }},\\n"
        f"  \\\"male_sub\\\": {{\\n"
        f"    \\\"name\\\": \\\"...\\\",\\n"
        f"    \\\"personality\\\": \\\"...\\\",\\n"
        f"    \\\"background\\\": \\\"...\\\",\\n"
        f"    \\\"character_relations\\\": \\\"...\\\",\\n"
        f"    \\\"speech_style\\\": \\\"...\\\",\\n"
        f"    \\\"physical_signature\\\": \\\"...\\\",\\n"
        f"    \\\"psychological_trigger\\\": \\\"...\\\",\\n"
        f"    \\\"behavioral_quirks\\\": \\\"...\\\",\\n"
        f"    \\\"secret_taboo\\\": \\\"...\\\",\\n"
        f"    \\\"signature_quotes\\\": \\\"...\\\"\\n"
        f"  }},\\n"
        f"  \\\"female_sub\\\": {{\\n"
        f"    \\\"name\\\": \\\"...\\\",\\n"
        f"    \\\"personality\\\": \\\"...\\\",\\n"
        f"    \\\"background\\\": \\\"...\\\",\\n"
        f"    \\\"character_relations\\\": \\\"...\\\",\\n"
        f"    \\\"speech_style\\\": \\\"...\\\",\\n"
        f"    \\\"physical_signature\\\": \\\"...\\\",\\n"
        f"    \\\"psychological_trigger\\\": \\\"...\\\",\\n"
        f"    \\\"behavioral_quirks\\\": \\\"...\\\",\\n"
        f"    \\\"secret_taboo\\\": \\\"...\\\",\\n"
        f"    \\\"signature_quotes\\\": \\\"...\\\"\\n"
        f"  }},\\n"
        f"  \\\"other\\\": {{\\n"
        f"    \\\"name\\\": \\\"...\\\",\\n"
        f"    \\\"personality\\\": \\\"...\\\",\\n"
        f"    \\\"background\\\": \\\"...\\\",\\n"
        f"    \\\"character_relations\\\": \\\"...\\\",\\n"
        f"    \\\"speech_style\\\": \\\"...\\\",\\n"
        f"    \\\"physical_signature\\\": \\\"...\\\",\\n"
        f"    \\\"psychological_trigger\\\": \\\"...\\\",\\n"
        f"    \\\"behavioral_quirks\\\": \\\"...\\\",\\n"
        f"    \\\"secret_taboo\\\": \\\"...\\\",\\n"
        f"    \\\"signature_quotes\\\": \\\"...\\\"\\n"
        f"  }}\\n"
        f"}}\\n"
        f"Write all character details strictly in Korean, aligning with the story tone."
    )
    
    db_session.query(Character).filter(Character.project_id == pid).delete()
    db_session.commit()
    
    first_char_id = None
    try:
        result = client.send_chat_completion(
            system_prompt=system_instruction,
            user_prompt=user_prompt,
            temperature=0.8,
            parse_json=True
        )
        
        import json
        if isinstance(result, str):
            clean_str = result.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str[7:]
            if clean_str.endswith("```"):
                clean_str = clean_str[:-3]
            data = json.loads(clean_str.strip())
        else:
            data = result
            
        categories = {
            "male_hero": "male_hero",
            "female_hero": "female_hero",
            "male_sub": "male_sub",
            "female_sub": "female_sub",
            "other": "other"
        }
        
        for key, rel in categories.items():
            char_data = data.get(key, {})
            name = char_data.get("name", "")
            personality = char_data.get("personality", "")
            background = char_data.get("background", "")
            relations_desc = char_data.get("character_relations", "") or char_data.get("relations", "")
            speech_style = char_data.get("speech_style", "")
            physical_signature = char_data.get("physical_signature", "")
            psychological_trigger = char_data.get("psychological_trigger", "")
            behavioral_quirks = char_data.get("behavioral_quirks", "")
            secret_taboo = char_data.get("secret_taboo", "")
            signature_quotes = char_data.get("signature_quotes", "")
            if name:
                char = Character(
                    project_id=pid,
                    name=name,
                    relations=rel,
                    personality=personality,
                    background=background,
                    character_relations=relations_desc,
                    speech_style=speech_style,
                    physical_signature=physical_signature,
                    psychological_trigger=psychological_trigger,
                    behavioral_quirks=behavioral_quirks,
                    secret_taboo=secret_taboo,
                    signature_quotes=signature_quotes
                )
                db_session.add(char)
                db_session.commit()
                if first_char_id is None:
                    first_char_id = char.id
                    
        gr.Info("AI 등장인물 프로필이 성공적으로 생성되어 저장되었습니다!")
        
    except Exception as e:
        print("Error during AI character generation:", e)
        gr.Warning("AI 프로필 생성 중 오류가 발생하여 기본 템플릿으로 대체합니다.")
        
        templates = [
            ("강민준 / 32세 / 검사", "male_hero", "냉정하고 철저한 원칙주의자.", "내면의 상처로 인한 타인에 대한 불신과 통제욕구.", "서연우(여주): 공조 관계이나 무의식적으로 이끌림. 김영철(조연): 표면적으로만 신뢰.", "공적: '서연우 씨', 차가운 존댓말 / 사적: '너', 억눌린 텐션의 반말", "은은한 우드 향수, 손목의 시계 흉터", "자신의 정의로운 신념이 위선으로 매도당할 때 격분함", "생각에 잠길 때면 검지로 안경테 중앙을 밀어올림", "어린 시절 아버지를 고발하여 가문을 몰락시켰던 사실", "'정의가 늘 승리하진 않지만, 불의가 굳어지게 둘 순 없습니다.'"),
            ("서연우 / 29세 / 기자", "female_hero", "따뜻한 성품과 남다른 직관력.", "과거 사건에 대한 죄책감과 인정욕구.", "강민준(남주): 경계심과 호기심이 교차함. 박소현(조연): 적대적 갈등 구조.", "공적: '강 검사님', 깍듯한 톤 / 사적: '민준 씨', 감정이 묻어나는 톤", "가벼운 시트러스 계열 향, 왼쪽 손목의 수술 자국", "자신을 '아무것도 모르는 기레기'로 무시할 때 이성을 잃음", "불안하면 머리칼을 검지손가락으로 돌돌 말아 꼬는 버릇", "사실 자신이 쫓는 기사의 결정적 제보자가 가해자의 자녀인 점", "'제가 진실을 보도하지 않으면, 그 죽음은 완전히 묻히는 겁니다.'"),
            ("김영철 / 40세 / 수사관", "male_sub", "우직하고 우호적인 맏형.", "과도한 충성심으로 인한 시야 협착.", "강민준(남주): 절대적 복종. 서연우(여주): 경계하는 태도.", "공적/사적 일관되게 투박한 말투", "진한 담배 향과 가죽 점퍼 냄새", "자신의 충직함을 의심받거나 장기말로 취급당할 때 욱함", "대답하기 곤란할 때 뒷머리를 긁적임", "부정한 뇌물을 받아 동생의 수술비를 마련했던 어두운 과거", "'검사님이 가라면 가는 거고, 서라면 서는 겁니다.'"),
            ("박소현 / 35세 / 정보 브로커", "female_sub", "비밀을 쥐고 있는 의문의 여인.", "물질적 욕망 and 애정 결핍.", "서연우(여주): 감시와 대치 관계. 강민준(남주): 이용하려는 관계.", "나른하고 여유로우며 상대를 도발하는 말투", "붉은 립스틱, 매혹적이고 강한 머스크 향", "과거 자신의 버림받았던 밑바닥 고아 시절을 건드릴 때 분노함", "거짓말을 할 때 검은색 네일이 칠해진 손톱 끝을 만지작거림", "마약 유통 조직의 핵심 지분 일부를 차명으로 보유 중인 사실", "'이 세상에 값 치르지 않고 가질 수 있는 비밀이 있을까요?'"),
            ("최 형사 / 45세", "other", "자애로운 후원자의 탈을 씀.", "파괴적인 성향 and 절대 권력욕.", "강민준(남주): 장기말처럼 이용. 박소현(조연): 필요에 의해 거래.", "상대의 심리를 압박하는 나긋나긋한 존댓말", "포말한 애프터쉐이브 향, 오른손 엄지 손톱 밑의 깊은 흉터", "누군가 자신의 정체(후원자 가면)를 눈치채려 할 때 눈빛이 돌변함", "대화 중 가느다란 펜으로 책상을 리드미컬하게 톡톡 치는 습관", "사실 10년 전 미제 실종 사건의 은밀한 사주자라는 금기 사항", "'사람을 다루는 건 말입니다, 그들이 가진 가장 무거운 짐을 흔드는 거예요.'")
        ]
        
        for name, rel, personality, background, rel_desc, speech_style, physical, trigger, quirks, secret, quotes in templates:
            char = Character(
                project_id=pid,
                name=name,
                relations=rel,
                personality=personality,
                background=background,
                character_relations=rel_desc,
                speech_style=speech_style,
                physical_signature=physical,
                psychological_trigger=trigger,
                behavioral_quirks=quirks,
                secret_taboo=secret,
                signature_quotes=quotes
            )
            db_session.add(char)
            db_session.commit()
            if first_char_id is None:
                first_char_id = char.id
                
    choices = get_character_dropdown_choices(project_str)
    res = on_character_select_change(first_char_id)
    c_name, c_role, c_personality, c_background, c_relations, c_speech_style = res[:6]
    c_physical, c_trigger, c_quirks, c_secret, c_quotes = res[6:]
    return (
        gr.update(choices=choices, value=first_char_id),
        c_name, c_role, c_personality, c_background, c_relations, c_speech_style,
        c_physical, c_trigger, c_quirks, c_secret, c_quotes
    )"""

save_char_ver_pattern = r"def save_character_version\(char_id, version_name, name, role, personality, background, relations_desc, speech_style\):.*?return gr\.update\(\), \"\""
new_save_char_ver = """def save_character_version(
    char_id, version_name, name, role, personality, background, relations_desc, speech_style,
    physical_signature, psychological_trigger, behavioral_quirks, secret_taboo, signature_quotes
):
    if not char_id:
        gr.Warning("선택된 등장인물이 없습니다.")
        return gr.update(), ""
    if not version_name.strip():
        gr.Warning("버전 이름을 입력해 주세요.")
        return gr.update(), ""
        
    try:
        new_ver = CharacterVersion(
            character_id=char_id,
            version_name=version_name.strip(),
            name=name.strip(),
            personality=personality.strip() if personality else "",
            background=background.strip() if background else "",
            speech_style=speech_style.strip() if speech_style else "",
            relations=role,
            character_relations=relations_desc.strip() if relations_desc else "",
            physical_signature=physical_signature.strip() if physical_signature else "",
            psychological_trigger=psychological_trigger.strip() if psychological_trigger else "",
            behavioral_quirks=behavioral_quirks.strip() if behavioral_quirks else "",
            secret_taboo=secret_taboo.strip() if secret_taboo else "",
            signature_quotes=signature_quotes.strip() if signature_quotes else ""
        )
        db_session.add(new_ver)
        db_session.commit()
        gr.Info(f"캐릭터 버전 '{new_ver.version_name}'이(가) 저장되었습니다.")
        
        updated_choices = get_character_version_choices(char_id)
        return gr.update(choices=updated_choices, value=updated_choices[0] if updated_choices else None), ""
    except Exception as e:
        print("Error saving character version:", e)
        gr.Warning("캐릭터 버전 저장 중 오류가 발생했습니다.")
        return gr.update(), "" """

load_char_ver_pattern = r"def load_character_version\(version_str\):.*?return \"\", \"other\", \"\", \"\", \"\", \"\""
new_load_char_ver = """def load_character_version(version_str):
    if not version_str:
        gr.Warning("불러올 버전을 선택해 주세요.")
        return "", "other", "", "", "", "", "", "", "", "", ""
        
    try:
        vid = int(version_str.split("]")[0][1:])
        ver = db_session.query(CharacterVersion).filter(CharacterVersion.id == vid).first()
        if ver:
            gr.Info(f"캐릭터 버전 '{ver.version_name}'을(를) 불러왔습니다.")
            return (
                ver.name or "",
                ver.relations or "other",
                ver.personality or "",
                ver.background or "",
                ver.character_relations or "",
                ver.speech_style or "",
                ver.physical_signature or "",
                ver.psychological_trigger or "",
                ver.behavioral_quirks or "",
                ver.secret_taboo or "",
                ver.signature_quotes or ""
            )
    except Exception as e:
        print("Error loading character version:", e)
        
    gr.Warning("버전을 불러오는 데 실패했습니다.")
    return "", "other", "", "", "", "", "", "", "", "", "" """

compile_char_profiles_pattern = r"def compile_all_character_profiles\(project_str\):.*?return \"\\n\"\.join\(lines\)"
new_compile_char_profiles = """def compile_all_character_profiles(project_str):
    if not project_str:
        return ""
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        return ""
    
    characters = db_session.query(Character).filter(Character.project_id == pid).all()
    if not characters:
        return ""
        
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"  {proj.title} - 등장인물 프로필 리스트")
    lines.append(f"{'='*60}")
    lines.append("")
    
    role_mapping = {
        'male_hero': '남자 주인공',
        'female_hero': '여자 주인공',
        'male_sub': '남자 조연',
        'female_sub': '여자 조연',
        'other': '기타'
    }
    
    for i, char in enumerate(characters):
        role_kor = role_mapping.get(char.relations, '기타')
        lines.append(f"{'-'*60}")
        lines.append(f"{i+1}. 이름: {char.name}")
        lines.append(f"   역할 및 분류: {role_kor}")
        lines.append(f"{'-'*60}")
        
        if char.personality:
            lines.append(f"* 겉으로 드러나는 가면 (표면적 성격):")
            lines.append(f"  {char.personality.strip()}")
            lines.append("")
            
        if char.background:
            lines.append(f"* 숨겨진 결핍 및 본능 (심층 심리):")
            lines.append(f"  {char.background.strip()}")
            lines.append("")
            
        if char.character_relations:
            lines.append(f"* 다른 등장인물간의 관계의 심층 역학 설정 가이드:")
            lines.append(f"  {char.character_relations.strip()}")
            lines.append("")
            
        if char.speech_style:
            lines.append(f"* 언어적 발현: 호칭과 말투 구체화 요구사항:")
            lines.append(f"  {char.speech_style.strip()}")
            lines.append("")
 
        if char.physical_signature:
            lines.append(f"* 신체적 시그니처 및 고유 체향:")
            lines.append(f"  {char.physical_signature.strip()}")
            lines.append("")
 
        if char.psychological_trigger:
            lines.append(f"* 심리적/성적 아킬레스건 (트리거):")
            lines.append(f"  {char.psychological_trigger.strip()}")
            lines.append("")
 
        if char.behavioral_quirks:
            lines.append(f"* 무의식적 행동 버릇 (습관/틱):")
            lines.append(f"  {char.behavioral_quirks.strip()}")
            lines.append("")
 
        if char.secret_taboo:
            lines.append(f"* 숨겨진 비밀과 금기:")
            lines.append(f"  {char.secret_taboo.strip()}")
            lines.append("")
 
        if char.signature_quotes:
            lines.append(f"* 시그니처 대사 톤 샘플:")
            lines.append(f"  {char.signature_quotes.strip()}")
            lines.append("")
            
        lines.append("")
        
    return "\\n".join(lines)"""

build_ui_pattern = r"\(\s*init_char_name,\s*init_char_role,\s*init_char_personality,\s*init_char_background,\s*init_char_relations,\s*init_char_speech_style,\s*init_char_dropdown_update,"
new_build_ui_init = """(
            init_char_name, init_char_role, 
            init_char_personality, init_char_background, init_char_relations, init_char_speech_style,
            init_char_physical, init_char_trigger, init_char_quirks, init_char_secret, init_char_quotes,
            init_char_dropdown_update,"""

textbox_group_pattern = r"char_speech_style = gr\.Textbox\(label=\"언어적 발현: 호칭과 말투 구체화 요구사항\", placeholder=\".*?\", value=init_char_speech_style, lines=4\)\s*char_dummy = gr\.State\(\)"
new_textbox_group = """char_speech_style = gr.Textbox(label="언어적 발현: 호칭과 말투 구체화 요구사항", placeholder="공적인 공간 (가면을 쓴 상태) vs 사적인 공간 (경계가 허물어지는 순간)에서의 호칭 및 대화 양식", value=init_char_speech_style, lines=4)
                    
                    char_physical = gr.Textbox(label="신체적 시그니처 및 고유 체향 (Physical Signature & Scent)", placeholder="예: 살결에서 나는 은은한 장미 향, 왼쪽 쇄골 아래의 흉터, 서늘한 체온 등", value=init_char_physical, lines=3)
                    char_trigger = gr.Textbox(label="심리적/성적 아킬레스건 (Psychological Trigger)", placeholder="예: 상대가 귓속말을 속삭이거나 손목을 가볍게 쥘 때 통제력을 잃음", value=init_char_trigger, lines=3)
                    char_quirks = gr.Textbox(label="무의식적 행동 버릇 (Behavioral Quirks & Tics)", placeholder="예: 곤란할 때면 손끝을 깨물거나 안경을 만지작거림", value=init_char_quirks, lines=3)
                    char_secret = gr.Textbox(label="숨겨진 비밀과 금기 (Secret & Taboo)", placeholder="예: 과거 스승과의 은밀한 거래 사실, 결코 밝혀져선 안 될 출생의 비밀", value=init_char_secret, lines=3)
                    char_quotes = gr.Textbox(label="시그니처 대사 톤 샘플 (Signature Quotes)", placeholder="예: '무슨 질문이 그러시죠? 불쾌하네요.'", value=init_char_quotes, lines=3)
                    char_dummy = gr.State()"""

char_dropdown_change = r"char_dropdown\.change\(\s*fn=on_character_select_change,\s*inputs=\[char_dropdown\],\s*outputs=\[char_name, char_role, char_personality, char_background, char_relations, char_speech_style\]\s*\)"
new_char_dropdown_change = """char_dropdown.change(
            fn=on_character_select_change,
            inputs=[char_dropdown],
            outputs=[char_name, char_role, char_personality, char_background, char_relations, char_speech_style, char_physical, char_trigger, char_quirks, char_secret, char_quotes]
        )"""

btn_add_char_pattern = r"btn_add_char\.click\(\s*fn=add_new_blank_character,\s*inputs=\[project_dropdown\],\s*outputs=\[char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style\]\s*\)"
new_btn_add_char = """btn_add_char.click(
            fn=add_new_blank_character,
            inputs=[project_dropdown],
            outputs=[char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style, char_physical, char_trigger, char_quirks, char_secret, char_quotes]
        )"""

btn_delete_char_pattern = r"btn_delete_char\.click\(\s*fn=delete_selected_character,\s*inputs=\[project_dropdown, char_dropdown\],\s*outputs=\[char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style\]\s*\)"
new_btn_delete_char = """btn_delete_char.click(
            fn=delete_selected_character,
            inputs=[project_dropdown, char_dropdown],
            outputs=[char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style, char_physical, char_trigger, char_quirks, char_secret, char_quotes]
        )"""

btn_save_char_pattern = r"btn_save_character_detail\.click\(\s*fn=save_or_update_character,\s*inputs=\[project_dropdown, char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style\],\s*outputs=\[char_dropdown, char_dummy, char_name, char_role, char_personality, char_background, char_relations, char_speech_style\]\s*\)"
new_btn_save_char = """btn_save_character_detail.click(
            fn=save_or_update_character,
            inputs=[project_dropdown, char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style, char_physical, char_trigger, char_quirks, char_secret, char_quotes],
            outputs=[char_dropdown, char_dummy, char_name, char_role, char_personality, char_background, char_relations, char_speech_style, char_physical, char_trigger, char_quirks, char_secret, char_quotes]
        )"""

btn_gen_chars_pattern = r"btn_generate_characters\.click\(\s*fn=api_generate_characters,\s*inputs=\[project_dropdown\],\s*outputs=\[char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style\]\s*\)"
new_btn_gen_chars = """btn_generate_characters.click(
            fn=api_generate_characters,
            inputs=[project_dropdown],
            outputs=[char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style, char_physical, char_trigger, char_quirks, char_secret, char_quotes]
        )"""

btn_save_char_ver_pattern = r"btn_save_char_version\.click\(\s*fn=save_character_version,\s*inputs=\[\s*char_dropdown,\s*char_ver_name_input,\s*char_name,\s*char_role,\s*char_personality,\s*char_background,\s*char_relations,\s*char_speech_style\s*\],\s*outputs=\[char_version_dropdown, char_ver_name_input\]\s*\)"
new_btn_save_char_ver = """btn_save_char_version.click(
            fn=save_character_version,
            inputs=[
                char_dropdown,
                char_ver_name_input,
                char_name,
                char_role,
                char_personality,
                char_background,
                char_relations,
                char_speech_style,
                char_physical,
                char_trigger,
                char_quirks,
                char_secret,
                char_quotes
            ],
            outputs=[char_version_dropdown, char_ver_name_input]
        )"""

btn_load_char_ver_pattern = r"btn_load_char_version\.click\(\s*fn=load_character_version,\s*inputs=\[char_version_dropdown\],\s*outputs=\[char_name, char_role, char_personality, char_background, char_relations, char_speech_style\]\s*\)"
new_btn_load_char_ver = """btn_load_char_version.click(
            fn=load_character_version,
            inputs=[char_version_dropdown],
            outputs=[char_name, char_role, char_personality, char_background, char_relations, char_speech_style, char_physical, char_trigger, char_quirks, char_secret, char_quotes]
        )"""

btn_load_proj_pattern = r"btn_load_project\.click\(\s*fn=load_project_details,\s*inputs=\[project_dropdown\],\s*outputs=\[\s*char_name, char_role,\s*char_personality, char_background, char_relations, char_speech_style,\s*char_dropdown, char_dummy,"
new_btn_load_proj = """btn_load_project.click(
            fn=load_project_details,
            inputs=[project_dropdown],
            outputs=[
                char_name, char_role, 
                char_personality, char_background, char_relations, char_speech_style,
                char_physical, char_trigger, char_quirks, char_secret, char_quotes,
                char_dropdown, char_dummy,"""

btn_del_proj_pattern = r"btn_delete_project\.click\(\s*fn=delete_project,\s*inputs=\[project_dropdown\],\s*outputs=\[\s*project_dropdown,\s*char_name, char_role,\s*char_personality, char_background, char_relations, char_speech_style,\s*char_dropdown, char_dummy,"
new_btn_del_proj = """btn_delete_project.click(
            fn=delete_project,
            inputs=[project_dropdown],
            outputs=[
                project_dropdown, 
                char_name, char_role, 
                char_personality, char_background, char_relations, char_speech_style,
                char_physical, char_trigger, char_quirks, char_secret, char_quotes,
                char_dropdown, char_dummy,"""

btn_create_proj_pattern = r"btn_create_project\.click\(\s*fn=create_new_project,\s*inputs=\[new_title, new_genre\],\s*outputs=\[\s*project_dropdown,\s*char_name, char_role,\s*char_personality, char_background, char_relations, char_speech_style,\s*char_dropdown, char_dummy,"
new_btn_create_proj = """btn_create_project.click(
            fn=create_new_project,
            inputs=[new_title, new_genre],
            outputs=[
                project_dropdown, 
                char_name, char_role, 
                char_personality, char_background, char_relations, char_speech_style,
                char_physical, char_trigger, char_quirks, char_secret, char_quotes,
                char_dropdown, char_dummy,"""

del_proj_func_pattern = r"def delete_project\(project_str\):.*?return \(gr\.update\(choices=updated_choices, value=default_val\),\) \+ details"
new_del_proj_func = """def delete_project(project_str):
    if not project_str:
        gr.Warning("삭제할 프로젝트가 선택되지 않았습니다.")
        return (
            gr.update(),
            "", "other", "", "", "", "", "", "", "", "", "",
            gr.update(choices=[], value=None), gr.update(),
            "", "", "", "",
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            "", "",
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=None),
            gr.update(choices=[], value=[]),
            gr.update(choices=[], value=None)
        )
    pid = parse_project_id(project_str)
    
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if proj:
        db_session.delete(proj)
        db_session.commit()
        db_session.expire_all()
        gr.Info(f"프로젝트가 삭제되었습니다.")
        
    updated_choices = get_project_list()
    default_val = updated_choices[0] if updated_choices else None
    
    details = load_project_details(default_val)
    return (gr.update(choices=updated_choices, value=default_val),) + details"""

create_proj_func_pattern = r"details = load_project_details\(new_choice\)\s*return \(gr\.update\(choices=updated_choices, value=new_choice\),\) \+ details\[0:18\] \+ \(\"\", \"\"\) \+ details\[18:\]"
new_create_proj_func = """details = load_project_details(new_choice)
    return (gr.update(choices=updated_choices, value=new_choice),) + details[0:23] + ("", "") + details[23:]"""

# 4. Perform replacements
log = []

def do_sub(pattern, replacement, text, name):
    if isinstance(replacement, str):
        repl_func = lambda m: replacement
    else:
        repl_func = replacement
    res, count = re.subn(pattern, repl_func, text, flags=re.DOTALL)
    log.append(f"{name}: {count}")
    return res

code = do_sub(get_main_char_pattern, new_get_main_char, code, "1. get_main_char")
code = do_sub(on_char_select_pattern, new_on_char_select, code, "2. on_char_select")
code = do_sub(save_or_update_pattern, new_save_or_update, code, "3. save_or_update")
code = do_sub(insert_helper_pattern, lambda m: m.group(1) + "\n" + new_helpers + "\n" + m.group(2), code, "4. insert_helpers")
code = do_sub(api_gen_chars_pattern, new_api_gen_chars, code, "5. api_gen_chars")
code = do_sub(save_char_ver_pattern, new_save_char_ver, code, "6. save_char_ver")
code = do_sub(load_char_ver_pattern, new_load_char_ver, code, "7. load_char_ver")
code = do_sub(compile_char_profiles_pattern, new_compile_char_profiles, code, "8. compile_char_profiles")
code = do_sub(build_ui_pattern, new_build_ui_init, code, "9. build_ui_init")
code = do_sub(textbox_group_pattern, new_textbox_group, code, "10. textbox_group")
code = do_sub(char_dropdown_change, new_char_dropdown_change, code, "11. char_dropdown_change")
code = do_sub(btn_add_char_pattern, new_btn_add_char, code, "12. btn_add_char")
code = do_sub(btn_delete_char_pattern, new_btn_delete_char, code, "13. btn_delete_char")
code = do_sub(btn_save_char_pattern, new_btn_save_char, code, "14. btn_save_char")
code = do_sub(btn_gen_chars_pattern, new_btn_gen_chars, code, "15. btn_gen_chars")
code = do_sub(btn_save_char_ver_pattern, new_btn_save_char_ver, code, "16. btn_save_char_ver")
code = do_sub(btn_load_char_ver_pattern, new_btn_load_char_ver, code, "17. btn_load_char_ver")
code = do_sub(btn_load_proj_pattern, new_btn_load_proj, code, "18. btn_load_proj")
code = do_sub(btn_del_proj_pattern, new_btn_del_proj, code, "19. btn_del_proj")
code = do_sub(btn_create_proj_pattern, new_btn_create_proj, code, "20. btn_create_proj")
code = do_sub(del_proj_func_pattern, new_del_proj_func, code, "21. del_proj_func")
code = do_sub(create_proj_func_pattern, new_create_proj_func, code, "22. create_proj_func")

# 5. Write the patched ui.py back
self_patcher_header = """import os
import sys
import shutil

# Self-patcher to restore the full UI from dry_run_temp and apply merge_and_patch.py
self_path = os.path.abspath(__file__)
try:
    with open(self_path, "r", encoding="utf-8", errors="ignore") as f:
        self_content = f.read()
except Exception as e:
    self_content = ""

if "on_female_char_select" not in self_content:
    print("[PATCHER] ui.py needs patching. Running merge_and_patch.py...")
    try:
        with open("d:/DeepScribe/merge_and_patch.py", "r", encoding="utf-8", errors="ignore") as f:
            exec(f.read(), globals())
        print("[PATCHER] Patch applied successfully. Restarting ui.py...")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"[PATCHER] Patch failed: {e}")

"""

with open(dst, "w", encoding="utf-8") as f:
    f.write(self_patcher_header + code)

# 6. Write replacement log to file
with open("patch_log.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(log) + "\n")
