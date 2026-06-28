import gradio as gr
import tempfile
import os
import inspect
import functools
from datetime import datetime, timedelta
from difflib import ndiff
from models import init_db, Project, Character, ScenarioNode, HistoryLog, PromptVersion, CharacterVersion, EroticScenarioVersion
from client import LlamaAPIClient, optimize_prompt
from engine.context_router import ContextRouter
from engine.synthesizer import MultiPOVSynthesizer
from engine.filter import StyleRhythmFilter
from engine.fact_checker import FactChecker
from engine.tracker import TimelineTracker

# Initialize Engine Components
db_session = init_db()

# Database correction for project 8 mismatch
try:
    from models import Project
    proj8 = db_session.query(Project).filter(Project.id == 8).first()
    if proj8 and proj8.overall_plot and "남편의 빚" in proj8.overall_plot:
        proj8.overall_plot = (
            "30대 중반 미망인 스미래의 집으로 20대 초반 대학생 히로시가 하숙생으로 들어오며 벌어지는 관능적인 로맨스 소설입니다. "
            "정숙한 미망인의 가면 속에 숨겨진 스미래의 강렬한 성적 결핍과, 순진하지만 거부할 수 없는 본능에 흔들리는 하숙생 히로시 "
            "사이의 위태로운 관계가 폭우 속에서 점차 파국으로 치달으며 전개됩니다."
        )
        db_session.commit()
        print("[DATABASE CORRECTION] Fixed overall plot for project 8 (동정-스미래)")
except Exception as e:
    print("[DATABASE CORRECTION] Error correcting database:", e)

# Automatically update Project.updated_at when modifications are made to child elements
from sqlalchemy import event
from sqlalchemy.orm import Session

@event.listens_for(Session, 'before_flush')
def before_flush(session, flush_context, instances):
    from datetime import datetime
    from models import Project, Character, ScenarioNode, PromptVersion, CharacterVersion, EroticScenarioVersion
    project_ids = set()
    for obj in session.new.union(session.dirty):
        if isinstance(obj, Project):
            pass
        elif isinstance(obj, Character):
            project_ids.add(obj.project_id)
        elif isinstance(obj, ScenarioNode):
            project_ids.add(obj.project_id)
        elif isinstance(obj, PromptVersion):
            project_ids.add(obj.project_id)
        elif isinstance(obj, EroticScenarioVersion):
            project_ids.add(obj.project_id)
        elif isinstance(obj, CharacterVersion):
            if obj.character:
                project_ids.add(obj.character.project_id)
            elif obj.character_id:
                with session.no_autoflush:
                    char = session.query(Character).filter(Character.id == obj.character_id).first()
                    if char:
                        project_ids.add(char.project_id)
                        
    for obj in session.deleted:
        if isinstance(obj, Character):
            project_ids.add(obj.project_id)
        elif isinstance(obj, ScenarioNode):
            project_ids.add(obj.project_id)
        elif isinstance(obj, PromptVersion):
            project_ids.add(obj.project_id)
        elif isinstance(obj, EroticScenarioVersion):
            project_ids.add(obj.project_id)
            
    if project_ids:
        with session.no_autoflush:
            for pid in project_ids:
                if pid:
                    proj = session.query(Project).filter(Project.id == pid).first()
                    if proj:
                        proj.updated_at = datetime.utcnow()

llama_client = LlamaAPIClient()
router = ContextRouter(db_session)
synthesizer = MultiPOVSynthesizer(llama_client)
style_filter = StyleRhythmFilter(llama_client)
fact_checker = FactChecker()
tracker = TimelineTracker(llama_client)

# Helper functions for project management
def format_local_time(dt):
    if not dt:
        return ""
    local_dt = dt + timedelta(hours=9)
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')

def parse_project_id(project_str: str) -> int:
    try:
        if project_str and project_str.startswith("[") and "]" in project_str:
            return int(project_str.split("]")[0][1:])
    except Exception:
        pass
    return 1

def get_project_list():
    try:
        projects = db_session.query(Project).order_by(Project.updated_at.desc(), Project.id.desc()).all()
        if not projects:
            default_proj = Project(title="기본 프로젝트", genre="드라마", status="Draft")
            db_session.add(default_proj)
            db_session.commit()
            projects = [default_proj]
        return [f"[{p.id}] {p.title} ({p.genre or '장르 없음'})" for p in projects]
    except Exception as e:
        print("Error fetching projects:", e)
        return ["[1] 기본 프로젝트 (드라마)"]

def load_project_character_data(project_str):
    if not project_str:
        return "", "", "", "", "", ""
    pid = parse_project_id(project_str)
    
    characters = db_session.query(Character).filter(Character.project_id == pid).all()
    
    male_name = ""
    male_profile = ""
    female_name = ""
    female_profile = ""
    other_names = []
    other_profiles = []
    
    for char in characters:
        if char.relations == 'male_hero':
            male_name = char.name
            male_profile = char.personality or ""
        elif char.relations == 'female_hero':
            female_name = char.name
            female_profile = char.personality or ""
        elif char.relations == 'other':
            other_names.append(char.name)
            if char.personality:
                other_profiles.append(f"{char.name}: {char.personality}")
                
    other_name_str = ", ".join(other_names)
    other_profile_str = "\n".join(other_profiles)
    
    return male_name, male_profile, female_name, female_profile, other_name_str, other_profile_str

def get_node_choices_for_stage(project_id, stage):
    if not project_id:
        return []
    try:
        from sqlalchemy import func
        subq = db_session.query(
            ScenarioNode.node_index,
            func.max(ScenarioNode.id).label('max_id')
        ).filter(
            ScenarioNode.project_id == project_id,
            ScenarioNode.stage == stage
        ).group_by(ScenarioNode.node_index).subquery()
        
        latest_nodes = db_session.query(ScenarioNode).join(
            subq,
            (ScenarioNode.node_index == subq.c.node_index) &
            (ScenarioNode.id == subq.c.max_id)
        ).filter(
            ScenarioNode.project_id == project_id,
            ScenarioNode.stage == stage
        ).order_by(ScenarioNode.node_index).all()
        
        return [(f"[{n.node_index}] {n.title}", n.node_index) for n in latest_nodes]
    except Exception as e:
        print("Error fetching node choices:", e)
        return []

def build_commit_tree_choices(project_id, stage, node_index):
    if not project_id or not stage or node_index is None:
        return []
    try:
        nodes = db_session.query(ScenarioNode).filter(
            ScenarioNode.project_id == project_id,
            ScenarioNode.stage == stage,
            ScenarioNode.node_index == node_index
        ).all()
    except Exception as e:
        print("Error fetching scenario nodes:", e)
        return []
        
    if not nodes:
        return []
        
    nodes_by_id = {n.id: n for n in nodes}
    children_by_parent = {}
    roots = []
    
    for n in nodes:
        if n.parent_id is None or n.parent_id not in nodes_by_id:
            roots.append(n)
        else:
            if n.parent_id not in children_by_parent:
                children_by_parent[n.parent_id] = []
            children_by_parent[n.parent_id].append(n)
            
    roots.sort(key=lambda x: x.created_at)
    for pid in children_by_parent:
        children_by_parent[pid].sort(key=lambda x: x.created_at)
        
    sorted_nodes = sorted(nodes, key=lambda x: x.created_at)
    version_map = {n.id: f"v{i+1}" for i, n in enumerate(sorted_nodes)}

    choices = []
    
    def traverse(node, depth):
        prefix = "  " * depth
        if depth > 0:
            prefix += "└─ "
        time_str = format_local_time(node.created_at)
        ver_str = version_map[node.id]
        label = f"{prefix}[{ver_str}] {node.commit_message or 'No message'} ({time_str})"
        choices.append((label, node.id))
        
        children = children_by_parent.get(node.id, [])
        for child in children:
            traverse(child, depth + 1)
            
    for root in roots:
        traverse(root, 0)
        
    return choices

def get_character_dropdown_choices(project_str):
    if not project_str:
        return []
    pid = parse_project_id(project_str)
    try:
        characters = db_session.query(Character).filter(Character.project_id == pid).all()
        choices = []
        for char in characters:
            role_kor = {
                'male_hero': '남자 주인공',
                'female_hero': '여자 주인공',
                'male_sub': '남자 조연',
                'female_sub': '여자 조연',
                'other': '기타'
            }.get(char.relations, '기타')
            choices.append((f"[{role_kor}] {char.name}", char.id))
        return choices
    except Exception as e:
        print("Error getting character dropdown choices:", e)
        return []

def get_character_names(project_str):
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

def on_character_select_change(char_id):
    if not char_id:
        return "", "other", "", "", "", ""
    try:
        char = db_session.query(Character).filter(Character.id == char_id).first()
        if char:
            return char.name or "", char.relations or "other", char.personality or "", char.background or "", char.character_relations or "", char.speech_style or ""
    except Exception as e:
        print("Error loading character details:", e)
    return "", "other", "", "", "", ""

def save_or_update_character(project_str, char_id, name, role, personality, background, relations_desc, speech_style):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), gr.update(), name, role, personality, background, relations_desc, speech_style
    if not name.strip():
        gr.Warning("이름을 입력해 주세요.")
        return gr.update(), gr.update(), name, role, personality, background, relations_desc, speech_style
        
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
                speech_style=speech_style.strip()
            )
            db_session.add(char)
            db_session.commit()
            gr.Info(f"새로운 등장인물 '{char.name}'이 추가되었습니다.")
            
        choices = get_character_dropdown_choices(project_str)
        return gr.update(choices=choices, value=char.id), gr.update(), name, role, personality, background, relations_desc, speech_style
    except Exception as e:
        print("Error saving character:", e)
        gr.Warning("등장인물 저장 중 오류가 발생했습니다.")
        return gr.update(), gr.update(), name, role, personality, background, relations_desc, speech_style

def add_new_blank_character(project_str):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), "", "other", "", "", "", ""
    pid = parse_project_id(project_str)
    try:
        new_char = Character(
            project_id=pid,
            name="새 인물",
            relations="other",
            personality="예: 완벽주의, 냉혈함",
            background="예: 인정욕구, 타인에 대한 뿌리 깊은 불신",
            character_relations="표면적 역학 vs 무의식적 긴장, 결핍의 상호작용 등",
            speech_style="공적인 공간/사적인 공간에서의 호칭과 말투 변화"
        )
        db_session.add(new_char)
        db_session.commit()
        
        choices = get_character_dropdown_choices(project_str)
        gr.Info("새로운 인물이 추가되었습니다. 정보를 입력하고 저장해 주세요.")
        return gr.update(choices=choices, value=new_char.id), new_char.name, new_char.relations, new_char.personality, new_char.background, new_char.character_relations, new_char.speech_style
    except Exception as e:
        print("Error adding blank character:", e)
        return gr.update(), "", "other", "", "", "", ""

def delete_selected_character(project_str, char_id):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), "", "other", "", "", "", ""
    if not char_id:
        gr.Warning("삭제할 등장인물이 선택되지 않았습니다.")
        return gr.update(), "", "other", "", "", "", ""
    try:
        db_session.query(Character).filter(Character.id == char_id).delete()
        db_session.commit()
        db_session.expire_all()
        gr.Info("선택된 등장인물이 삭제되었습니다.")
        
        choices = get_character_dropdown_choices(project_str)
        next_val = choices[0][1] if choices else None
        
        name, role, personality, background, relations_desc, speech_style = on_character_select_change(next_val)
        return gr.update(choices=choices, value=next_val), name, role, personality, background, relations_desc, speech_style
    except Exception as e:
        print("Error deleting character:", e)
        return gr.update(), "", "other", "", "", "", ""

def auto_save_erotic_version(project_str, female_desc, male_desc, relations_desc, situation_desc, sensory_enabled, contrast_enabled, buildup_enabled, num_cases, generated_markdown, parsed_cases):
    if not project_str:
        return gr.update()
    time_str = format_local_time(datetime.utcnow())
    version_name = f"AI 생성 ({time_str})"
    pid = parse_project_id(project_str)
    
    import json
    parsed_cases_json = ""
    try:
        if parsed_cases:
            parsed_cases_json = json.dumps(parsed_cases)
    except Exception as e:
        print("Error serializing parsed cases:", e)
        
    new_ver = EroticScenarioVersion(
        project_id=pid,
        version_name=version_name,
        female_desc=female_desc,
        male_desc=male_desc,
        relations_desc=relations_desc,
        situation_desc=situation_desc,
        sensory_enabled=1 if sensory_enabled else 0,
        contrast_enabled=1 if contrast_enabled else 0,
        buildup_enabled=1 if buildup_enabled else 0,
        num_cases=num_cases,
        generated_markdown=generated_markdown,
        parsed_cases_json=parsed_cases_json
    )
    
    try:
        db_session.add(new_ver)
        db_session.commit()
        db_session.expire_all()
    except Exception as e:
        db_session.rollback()
        print("Error auto-saving erotic version:", e)
        
    choices = get_erotic_version_choices(project_str)
    default_val = choices[0][1] if choices else None
    return gr.update(choices=choices, value=default_val)

def get_erotic_version_choices(project_str):
    if not project_str:
        return []
    pid = parse_project_id(project_str)
    try:
        versions = db_session.query(EroticScenarioVersion).filter(EroticScenarioVersion.project_id == pid).order_by(EroticScenarioVersion.created_at.desc()).all()
        return [(f"{v.version_name} ({format_local_time(v.created_at)})", v.id) for v in versions]
    except Exception as e:
        print("Error fetching erotic version choices:", e)
        return []

def save_erotic_version(project_str, version_name, female_desc, male_desc, relations_desc, situation_desc, sensory_enabled, contrast_enabled, buildup_enabled, num_cases, generated_markdown, parsed_cases):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), gr.update()
    if not version_name or not version_name.strip():
        gr.Warning("이력 버전 이름을 입력해주세요.")
        return gr.update(), gr.update()
        
    pid = parse_project_id(project_str)
    
    import json
    parsed_cases_json = ""
    try:
        if parsed_cases:
            parsed_cases_json = json.dumps(parsed_cases)
    except Exception as e:
        print("Error serializing parsed cases:", e)
        
    new_ver = EroticScenarioVersion(
        project_id=pid,
        version_name=version_name.strip(),
        female_desc=female_desc,
        male_desc=male_desc,
        relations_desc=relations_desc,
        situation_desc=situation_desc,
        sensory_enabled=1 if sensory_enabled else 0,
        contrast_enabled=1 if contrast_enabled else 0,
        buildup_enabled=1 if buildup_enabled else 0,
        num_cases=num_cases,
        generated_markdown=generated_markdown,
        parsed_cases_json=parsed_cases_json
    )
    
    try:
        db_session.add(new_ver)
        db_session.commit()
        db_session.expire_all()
        gr.Info("관능 시나리오 이력이 성공적으로 저장되었습니다.")
    except Exception as e:
        db_session.rollback()
        print("Error saving erotic version:", e)
        gr.Warning("이력 저장 중 오류가 발생했습니다.")
        
    choices = get_erotic_version_choices(project_str)
    default_val = choices[0][1] if choices else None
    return gr.update(choices=choices, value=default_val), gr.update(value="")

def load_erotic_version(version_id):
    if not version_id:
        gr.Warning("불러올 이력을 선택해주세요.")
        return (
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update()
        )
    try:
        v = db_session.query(EroticScenarioVersion).filter(EroticScenarioVersion.id == int(version_id)).first()
        if not v:
            gr.Warning("선택한 이력을 데이터베이스에서 찾을 수 없습니다.")
            return (
                gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update()
            )
            
        import json
        parsed_cases = []
        if v.parsed_cases_json:
            try:
                parsed_cases = json.loads(v.parsed_cases_json)
            except Exception as e:
                print("Error parsing parsed_cases_json:", e)
                
        case_choices = []
        if parsed_cases:
            for case in parsed_cases:
                title = case.get("title", "")
                case_choices.append(title)
        
        gr.Info(f"이력 '{v.version_name}'을 성공적으로 불러왔습니다.")
        return (
            v.female_desc or "",
            v.male_desc or "",
            v.relations_desc or "",
            v.situation_desc or "",
            True if v.sensory_enabled else False,
            True if v.contrast_enabled else False,
            True if v.buildup_enabled else False,
            v.num_cases or 3,
            v.generated_markdown or "",
            parsed_cases,
            gr.update(choices=case_choices, value=case_choices[0] if case_choices else None)
        )
    except Exception as e:
        print("Error loading erotic version:", e)
        gr.Warning("이력 불러오기 중 오류가 발생했습니다.")
        return (
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update(), gr.update(),
            gr.update(), gr.update(), gr.update()
        )

def delete_erotic_version(version_id, project_str):
    if not version_id:
        gr.Warning("삭제할 이력을 선택해주세요.")
        return gr.update()
    try:
        v = db_session.query(EroticScenarioVersion).filter(EroticScenarioVersion.id == int(version_id)).first()
        if v:
            db_session.delete(v)
            db_session.commit()
            gr.Info("해당 이력이 삭제되었습니다.")
    except Exception as e:
        db_session.rollback()
        print("Error deleting erotic version:", e)
        gr.Warning("이력 삭제 중 오류가 발생했습니다.")
        
    choices = get_erotic_version_choices(project_str)
    default_val = choices[0][1] if choices else None
    return gr.update(choices=choices, value=default_val)

def on_page_load():
    db_session.expire_all()
    updated_choices = get_project_list()
    default_val = updated_choices[0] if updated_choices else None
    return gr.update(choices=updated_choices, value=default_val)

def load_project_details(project_str):
    if not project_str:
        return (
            "", "other", "", "", "", "", gr.update(choices=[], value=None), gr.update(),
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
    if not proj:
        gr.Warning("선택한 프로젝트를 데이터베이스에서 찾을 수 없습니다. 올바른 프로젝트를 선택해주세요.")
        return (
            "", "other", "", "", "", "", gr.update(choices=[], value=None), gr.update(),
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
        
    choices = get_character_dropdown_choices(project_str)
    first_char_id = choices[0][1] if choices else None
    c_name, c_role, c_personality, c_background, c_relations, c_speech_style = on_character_select_change(first_char_id)
    
    system_prompt = proj.system_prompt or ""
    overall_plot = proj.overall_plot or ""
    positive_prompt = proj.positive_prompt or ""
    negative_prompt = proj.negative_prompt or ""
    
    # Version choices
    ver_choices = get_prompt_version_choices(project_str)
    default_ver = ver_choices[0] if ver_choices else None
    
    # Scenario tab defaults
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
            
    # Target scenario choices
    target_scen_choices = get_target_scenario_node_choices(project_str)
    default_target_scen = target_scen_choices[0][1] if target_scen_choices else None

    # Scene generation history defaults
    scene_history_choices = get_scene_history_choices(project_str, default_target_scen)
    default_scene_history = scene_history_choices[0][1] if scene_history_choices else None
            
    erotic_choices = get_erotic_version_choices(project_str)
    default_erotic = erotic_choices[0][1] if erotic_choices else None

    return (
        c_name, c_role, c_personality, c_background, c_relations, c_speech_style,
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
        update_active_characters_checkbox(project_str),
        gr.update(choices=erotic_choices, value=default_erotic)
    )

def save_project_settings(project_str, system_prompt, overall_plot, positive_prompt, negative_prompt):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if proj:
        proj.system_prompt = system_prompt
        proj.overall_plot = overall_plot
        proj.positive_prompt = positive_prompt
        proj.negative_prompt = negative_prompt
        db_session.commit()
        gr.Info("소설 줄거리 및 프롬프트 설정이 저장되었습니다.")

def create_new_project(title, genre):
    if not title.strip():
        title = "제목 없는 프로젝트"
    new_proj = Project(
        title=title.strip(), 
        genre=genre.strip() if genre else "장르 없음", 
        status="Draft",
        system_prompt="",
        overall_plot="",
        positive_prompt="",
        negative_prompt=""
    )
    db_session.add(new_proj)
    db_session.commit()
    
    # Create default characters for the new project
    templates = [
        ("강민준", "male_hero", f"냉정하고 철저한 성격의 소유자. {new_proj.title}의 소용돌이 속에서 진실을 밝히기 위해 투쟁한다."),
        ("서연우", "female_hero", f"따뜻한 성품과 남다른 직관력을 지닌 인물. {new_proj.title}의 진실을 마주하고 갈등과 성장을 겪는다.")
    ]
    for name, rel, personality in templates:
        db_session.add(Character(
            project_id=new_proj.id,
            name=name,
            relations=rel,
            personality=personality
        ))
    db_session.commit()
    db_session.expire_all()
    
    updated_choices = get_project_list()
    new_choice = f"[{new_proj.id}] {new_proj.title} ({new_proj.genre})"
    gr.Info(f"새 프로젝트 '{new_proj.title}'가 생성되었습니다.")
    
    details = load_project_details(new_choice)
    return (gr.update(choices=updated_choices, value=new_choice),) + details[0:18] + ("", "") + details[18:]

def delete_project(project_str):
    if not project_str:
        gr.Warning("삭제할 프로젝트가 선택되지 않았습니다.")
        return (
            gr.update(),
            "", "other", "", "", "", "",
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
    if proj:
        db_session.delete(proj)
        db_session.commit()
        db_session.expire_all()
        gr.Info(f"프로젝트가 삭제되었습니다.")
        
    updated_choices = get_project_list()
    default_val = updated_choices[0] if updated_choices else None
    
    details = load_project_details(default_val)
    return (gr.update(choices=updated_choices, value=default_val),) + details

# Version history functions
def get_prompt_version_choices(project_str):
    if not project_str:
        return []
    pid = parse_project_id(project_str)
    try:
        versions = db_session.query(PromptVersion).filter(PromptVersion.project_id == pid).order_by(PromptVersion.created_at.desc()).all()
        return [f"[{v.id}] {v.version_name} ({format_local_time(v.created_at)})" for v in versions]
    except Exception as e:
        print("Error fetching prompt versions:", e)
        return []

def save_prompt_version(project_str, version_name, system_prompt, overall_plot, positive_prompt, negative_prompt):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), ""
    if not version_name.strip():
        gr.Warning("버전 이름을 입력해 주세요.")
        return gr.update(), ""
        
    pid = parse_project_id(project_str)
    
    # Save a new version record
    new_ver = PromptVersion(
        project_id=pid,
        version_name=version_name.strip(),
        system_prompt=system_prompt,
        overall_plot=overall_plot,
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt
    )
    db_session.add(new_ver)
    db_session.commit()
    gr.Info(f"버전 '{new_ver.version_name}'이(가) 저장되었습니다.")
    
    updated_choices = get_prompt_version_choices(project_str)
    return gr.update(choices=updated_choices, value=updated_choices[0] if updated_choices else None), ""

def load_prompt_version(version_str):
    if not version_str:
        gr.Warning("불러올 버전을 선택해 주세요.")
        return "", "", "", ""
        
    try:
        vid = int(version_str.split("]")[0][1:])
        ver = db_session.query(PromptVersion).filter(PromptVersion.id == vid).first()
        if ver:
            gr.Info(f"버전 '{ver.version_name}'을(를) 불러왔습니다.")
            return ver.system_prompt or "", ver.overall_plot or "", ver.positive_prompt or "", ver.negative_prompt or ""
    except Exception as e:
        print("Error loading version:", e)
        
    gr.Warning("버전을 불러오는 데 실패했습니다.")
    return "", "", "", ""

def delete_prompt_version(version_str, project_str):
    if not version_str:
        gr.Warning("삭제할 버전을 선택해 주세요.")
        return gr.update()
        
    try:
        vid = int(version_str.split("]")[0][1:])
        ver = db_session.query(PromptVersion).filter(PromptVersion.id == vid).first()
        if ver:
            db_session.delete(ver)
            db_session.commit()
            gr.Info("해당 버전이 삭제되었습니다.")
    except Exception as e:
        print("Error deleting version:", e)
        
    updated_choices = get_prompt_version_choices(project_str)
    return gr.update(choices=updated_choices, value=updated_choices[0] if updated_choices else None)

def edit_prompt_version(version_str, new_version_name, project_str):
    if not version_str:
        gr.Warning("수정할 버전을 선택해 주세요.")
        return gr.update(), ""
    if not new_version_name.strip():
        gr.Warning("새로운 버전 이름을 입력해 주세요.")
        return gr.update(), ""
        
    try:
        vid = int(version_str.split("]")[0][1:])
        ver = db_session.query(PromptVersion).filter(PromptVersion.id == vid).first()
        if ver:
            old_name = ver.version_name
            ver.version_name = new_version_name.strip()
            db_session.commit()
            gr.Info(f"버전명이 '{old_name}'에서 '{ver.version_name}'(으)로 수정되었습니다.")
    except Exception as e:
        print("Error editing version name:", e)
        
    updated_choices = get_prompt_version_choices(project_str)
    updated_val = [c for c in updated_choices if c.startswith(f"[{vid}]")]
    new_val = updated_val[0] if updated_val else (updated_choices[0] if updated_choices else None)
    return gr.update(choices=updated_choices, value=new_val), ""

def get_character_version_choices(char_id):
    if not char_id:
        return []
    try:
        versions = db_session.query(CharacterVersion).filter(CharacterVersion.character_id == char_id).order_by(CharacterVersion.created_at.desc()).all()
        return [f"[{v.id}] {v.version_name} ({format_local_time(v.created_at)})" for v in versions]
    except Exception as e:
        print("Error fetching character versions:", e)
        return []

def get_character_version_choices_update(char_id):
    choices = get_character_version_choices(char_id)
    return gr.update(choices=choices, value=choices[0] if choices else None)

def save_character_version(char_id, version_name, name, role, personality, background, relations_desc, speech_style):
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
            character_relations=relations_desc.strip() if relations_desc else ""
        )
        db_session.add(new_ver)
        db_session.commit()
        gr.Info(f"캐릭터 버전 '{new_ver.version_name}'이(가) 저장되었습니다.")
        
        updated_choices = get_character_version_choices(char_id)
        return gr.update(choices=updated_choices, value=updated_choices[0] if updated_choices else None), ""
    except Exception as e:
        print("Error saving character version:", e)
        gr.Warning("캐릭터 버전 저장 중 오류가 발생했습니다.")
        return gr.update(), ""

def load_character_version(version_str):
    if not version_str:
        gr.Warning("불러올 버전을 선택해 주세요.")
        return "", "other", "", "", "", ""
        
    try:
        vid = int(version_str.split("]")[0][1:])
        ver = db_session.query(CharacterVersion).filter(CharacterVersion.id == vid).first()
        if ver:
            gr.Info(f"캐릭터 버전 '{ver.version_name}'을(를) 불러왔습니다.")
            return ver.name or "", ver.relations or "other", ver.personality or "", ver.background or "", ver.character_relations or "", ver.speech_style or ""
    except Exception as e:
        print("Error loading character version:", e)
        
    gr.Warning("버전을 불러오는 데 실패했습니다.")
    return "", "other", "", "", "", ""

def delete_character_version(version_str, char_id):
    if not version_str:
        gr.Warning("삭제할 버전을 선택해 주세요.")
        return gr.update()
        
    try:
        vid = int(version_str.split("]")[0][1:])
        ver = db_session.query(CharacterVersion).filter(CharacterVersion.id == vid).first()
        if ver:
            db_session.delete(ver)
            db_session.commit()
            gr.Info("해당 캐릭터 버전이 삭제되었습니다.")
    except Exception as e:
        print("Error deleting character version:", e)
        
    updated_choices = get_character_version_choices(char_id)
    return gr.update(choices=updated_choices, value=updated_choices[0] if updated_choices else None)

def edit_character_version(version_str, new_version_name, char_id):
    if not version_str:
        gr.Warning("수정할 버전을 선택해 주세요.")
        return gr.update(), ""
    if not new_version_name.strip():
        gr.Warning("새로운 버전 이름을 입력해 주세요.")
        return gr.update(), ""
        
    try:
        vid = int(version_str.split("]")[0][1:])
        ver = db_session.query(CharacterVersion).filter(CharacterVersion.id == vid).first()
        if ver:
            old_name = ver.version_name
            ver.version_name = new_version_name.strip()
            db_session.commit()
            gr.Info(f"버전명이 '{old_name}'에서 '{ver.version_name}'(으)로 수정되었습니다.")
    except Exception as e:
        print("Error editing character version name:", e)
        
    updated_choices = get_character_version_choices(char_id)
    updated_val = [c for c in updated_choices if c.startswith(f"[{vid}]")]
    new_val = updated_val[0] if updated_val else (updated_choices[0] if updated_choices else None)
    return gr.update(choices=updated_choices, value=new_val), ""

def diff_texts(text1: str, text2: str):
    """
    Generate diff format for UI. 
    Returns list of tuples [(text, label), ...] for gr.HighlightedText.
    """
    diff_result = list(ndiff(text1.split(), text2.split()))
    output = []
    for token in diff_result:
        code = token[0]
        word = token[2:]
        if code == ' ':
            output.append((word + ' ', None))
        elif code == '-':
            output.append((word + ' ', '교정 전 (삭제됨)'))
        elif code == '+':
            output.append((word + ' ', '교정 후 (추가됨)'))
    return output

def refine_scene_with_prompt(project_str, current_scene, user_refine_prompt, system_prompt, target_node_id):
    """사용자가 입력한 프롬프트로 현재 씬을 수정/보완합니다."""
    if not current_scene or not user_refine_prompt:
        gr.Warning("수정할 씬 내용과 사용자 프롬프트를 모두 입력해주세요.")
        return current_scene, []
    
    try:
        sys_prompt = system_prompt.strip() if system_prompt.strip() else "당신은 전문 소설 작가입니다."
        user_prompt = (
            f"아래는 현재 작성된 소설의 씬입니다:\n\n"
            f"---\n{current_scene}\n---\n\n"
            f"사용자 지시사항: {user_refine_prompt}\n\n"
            f"위 지시사항에 따라 씬을 수정하여 전체 완성된 텍스트로 반환해주세요. "
            f"수정 설명 없이 수정된 씬 본문만 출력하세요."
        )
        
        refined = llama_client.send_chat_completion(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            temperature=0.75
        )
        if not refined:
            gr.Warning("AI 수정 요청이 빈 결과를 반환했습니다.")
            return current_scene, []
        
        # Style filter 적용
        filter_result = style_filter.process(refined)
        final_refined = filter_result["corrected"]
        
        # 변경 전후 diff 생성
        diff_output = diff_texts(current_scene, final_refined)
        
        # DB에 이력 저장
        if project_str:
            project_id = parse_project_id(project_str)
            new_node = ScenarioNode(
                project_id=project_id,
                stage="Development",
                parent_id=target_node_id if target_node_id else None,
                content=final_refined,
                commit_message=f"사용자 프롬프트 수정: {user_refine_prompt[:50]}"
            )
            db_session.add(new_node)
            db_session.commit()
            
            history_log = HistoryLog(
                scenario_node_id=new_node.id,
                action_type="REFINE_WITH_PROMPT",
                before_content=current_scene,
                after_content=final_refined,
                user_prompt=user_refine_prompt
            )
            db_session.add(history_log)
            db_session.commit()
        
        gr.Info("씬이 성공적으로 수정되었습니다.")
        return final_refined, diff_output
    except Exception as e:
        print("Error refining scene:", e)
        gr.Warning(f"씬 수정 중 오류가 발생했습니다: {str(e)}")
        return current_scene, []

def autofill_characters_from_project(project_str):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return "", "", ""
    pid = parse_project_id(project_str)
    try:
        characters = db_session.query(Character).filter(Character.project_id == pid).all()
        female_text = ""
        male_text = ""
        relations_text = ""
        
        female_char = None
        male_char = None
        
        for c in characters:
            if c.relations == "female_hero":
                female_char = c
            elif c.relations == "male_hero":
                male_char = c
                
        if female_char:
            female_text = f"[{female_char.name}]: {female_char.personality or ''}"
            if female_char.background:
                female_text += f"\n배경: {female_char.background}"
        else:
            female_text = "스미래: [30대 중반 미망인, 겉으로는 정숙하나 내면에는 강렬한 성적 결핍과 탐욕이 있음. 연하남을 유혹할 때 노련하게 수치심 및 도발을 혼합하여 사용하는 전략적 성격]"
            
        if male_char:
            male_text = f"[{male_char.name}]: {male_char.personality or ''}"
            if male_char.background:
                male_text += f"\n배경: {male_char.background}"
        else:
            male_text = "히로시: [20대 초반 대학생, 성실하지만 본능에 흔들리는 순진한 청년]"
            
        rel_parts = []
        if female_char and male_char:
            rel_parts.append(f"{female_char.name}(연상녀)-{male_char.name}(연하남)")
        else:
            rel_parts.append("연상녀-연하남")
            
        if female_char and female_char.character_relations:
            rel_parts.append(female_char.character_relations)
        elif male_char and male_char.character_relations:
            rel_parts.append(male_char.character_relations)
        else:
            rel_parts.append("금기된 관계 / 유혹하는 자와 함락되는 자")
            
        relations_text = " / ".join(rel_parts)
        
        gr.Info("프로젝트 캐릭터 정보를 성공적으로 불러왔습니다.")
        return female_text, male_text, relations_text
    except Exception as e:
        print("Error autofilling characters:", e)
        gr.Warning("캐릭터 정보를 불러오는 데 실패했습니다.")
        return "", "", ""

def parse_scenario_cases(text: str) -> list[dict]:
    import re
    if not text:
        return []
    
    cases = []
    pattern = r'(?:^|\n)Case\s*(\d+)\s*[\.\:]?\s*([^\n]+)'
    matches = list(re.finditer(pattern, text))
    
    for i, match in enumerate(matches):
        case_num = int(match.group(1))
        case_title = match.group(2).strip()
        
        start_idx = match.end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        case_body = text[start_idx:end_idx].strip()
        
        strategy = ""
        description = ""
        trigger = ""
        
        strategy_match = re.search(r'심리적 전략\s*:\s*(.*?)(?=\n\s*(?:상세 묘사|자극 포인트)|$)', case_body, re.DOTALL)
        if strategy_match:
            strategy = strategy_match.group(1).strip()
            
        desc_match = re.search(r'상세 묘사\s*:\s*(.*?)(?=\n\s*(?:심리적 전략|자극 포인트)|$)', case_body, re.DOTALL)
        if desc_match:
            description = desc_match.group(1).strip()
            
        trigger_match = re.search(r'자극 포인트\s*:\s*(.*?)(?=\n\s*(?:심리적 전략|상세 묘사)|$)', case_body, re.DOTALL)
        if trigger_match:
            trigger = trigger_match.group(1).strip()
            
        if not description:
            description = case_body
            
        cases.append({
            "number": case_num,
            "title": case_title,
            "strategy": strategy,
            "description": description,
            "trigger": trigger,
            "full_text": f"Case {case_num}. {case_title}\n\n" + case_body
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
        "역할: 당신은 인간의 복잡한 심리와 관능적 긴장감을 섬세하게 묘사하는 전문 시나리오 작가이자 심리 분석가입니다. "
        "대상을 철저히 분석하고 관능적인 씬을 작성하는 능력이 매우 뛰어납니다."
    )
    
    user_prompt = f"""아래 설정을 바탕으로 상황에 대한 시나리오 케이스를 {num_cases}개로 분화하여 작성하라.

[대상 캐릭터 및 관계 설정]
- 여성 캐릭터: {female_desc}
- 남성 캐릭터: {male_desc}
- 관계성: {relations_desc}

[미션 상황]
- 특정 상황: {situation_desc}

[시나리오 분화 가이드라인]
단순한 나열이 아니라, 다음과 같은 '심리적 층위'에 따라 케이스를 나누어 작성하라.
1. 심리적 기제: 이 행동을 하는 캐릭터의 내면 심리를 먼저 정의할 것. (출력 시 '심리적 전략'으로 표시)
2. 외적 행동: 구체적인 제스처, 시선 처리, 호흡의 변화를 묘사할 것. (출력 시 '상세 묘사'에 대사와 함께 포함)
3. 대사: 캐릭터의 성격이 드러나는 노련하고 관능적인 대사를 작성할 것. (출력 시 '상세 묘사'에 행동과 함께 포함)
4. 결과적 자극: 이 행동이 상대방(남성)에게 어떤 심리적/육체적 자극을 주는지 명시할 것. (출력 시 '자극 포인트'로 표시)
"""

    reqs = []
    if sensory_enabled:
        reqs.append("- 시각, 청각, 후각, 촉각 중 최소 3가지 이상의 감각 묘사를 매 케이스마다 포함해줘.")
    if contrast_enabled:
        reqs.append("- 여주인공의 '사회적 신분(예: 정숙한 미망인)'과 '현재의 도발적인 행동' 사이의 간극이 극명하게 드러나도록 작성해줘.")
    if buildup_enabled:
        reqs.append(f"- 케이스 1번부터 {num_cases}번으로 갈수록 유혹의 강도와 노골적인 수위가 점점 높아지는 계단식 구성으로 작성해줘.")
        
    if reqs:
        user_prompt += "\n[추가 조건]\n" + "\n".join(reqs) + "\n"
        
    user_prompt += """
[출력 형식]
매 케이스는 정확히 다음의 형식을 준수하여 출력할 것:

Case [번호]. [케이스의 명칭/테마]
심리적 전략: (여주인공이 어떤 심리로 이 행동을 하는가)
상세 묘사: (행동과 대사가 포함된 관능적인 시나리오 텍스트)
자극 포인트: (남주인공이 느끼게 될 심리적 타격점)

설명이나 주석 없이 위의 케이스들만 순서대로 출력해 주세요.
"""

    accumulated = ""
    yield "⏳ 생성 시작 중...", [], gr.update(choices=[], value=[])
    
    try:
        for token in llama_client.stream_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.85
        ):
            accumulated += token
            yield accumulated, [], gr.update(choices=[], value=[])
            
        cases = parse_scenario_cases(accumulated)
        choices = [f"Case {c['number']}. {c['title']}" for c in cases]
        default_choice = [choices[0]] if choices else []
        
        yield accumulated, cases, gr.update(choices=choices, value=default_choice)
    except Exception as e:
        print("Error in generating cases:", e)
        yield f"⚠️ 오류가 발생했습니다: {str(e)}", [], gr.update(choices=[], value=[])

def load_selected_case_details(selected_cases, parsed_cases):
    if not selected_cases or not parsed_cases:
        return "", "", ""
        
    if isinstance(selected_cases, str):
        selected_cases = [selected_cases]
        
    import re
    titles = []
    contents = []
    metas = []
    
    for case_str in selected_cases:
        if not case_str:
            continue
        match = re.search(r'Case\s*(\d+)', case_str)
        if not match:
            titles.append(case_str)
            contents.append(case_str)
            continue
            
        case_num = int(match.group(1))
        for c in parsed_cases:
            if c["number"] == case_num:
                titles.append(c["title"])
                contents.append(c["description"])
                metas.append(f"[{c['number']}번 케이스 - {c['title']}]\n심리적 전략: {c['strategy']}\n자극 포인트: {c['trigger']}")
                break
                
    joined_title = " / ".join(titles)
    joined_content = "\n\n".join(contents)
    joined_meta = "\n\n".join(metas)
    
    return joined_title, joined_content, joined_meta

def insert_case_to_scenario_node(project_str, stage, insert_position, current_node_index, case_title, case_content):
    if not project_str or not stage:
        gr.Warning("프로젝트와 플롯 단계를 먼저 선택해 주세요.")
        return gr.update(), gr.update(), "", ""
    if not case_content.strip():
        gr.Warning("시나리오 노드에 삽입할 내용이 없습니다.")
        return gr.update(), gr.update(), "", ""
        
    pid = parse_project_id(project_str)
    try:
        try:
            current_node_index = int(current_node_index)
        except (TypeError, ValueError):
            current_node_index = None

        existing = db_session.query(ScenarioNode).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage == stage
        ).order_by(ScenarioNode.node_index).all()
        
        existing_indices = sorted(set(n.node_index for n in existing if n.node_index is not None))
        max_index = max(existing_indices) if existing_indices else 0
        
        if insert_position == "end" or current_node_index is None or not existing_indices:
            new_index = max_index + 1
        elif insert_position == "before":
            new_index = current_node_index
        else:  # "after"
            new_index = current_node_index + 1
            
        if insert_position != "end" and current_node_index is not None:
            for node in existing:
                if node.node_index is not None and node.node_index >= new_index:
                    node.node_index += 1
            db_session.flush()
            
        stage_short = stage.split()[0] if stage else "기"
        
        new_node = ScenarioNode(
            project_id=pid,
            stage=stage,
            node_index=new_index,
            title=f"{stage_short}-{new_index}: {case_title.strip() or '관능 케이스'}",
            content=case_content.strip(),
            commit_message=f"심리 시나리오 분화 삽입: {case_title.strip()}"
        )
        db_session.add(new_node)
        db_session.commit()
        db_session.expire_all()
        
        node_choices = get_node_choices_for_stage(pid, stage)
        ver_choices = build_commit_tree_choices(pid, stage, new_index)
        default_ver = max(ver_choices, key=lambda x: x[1])[1] if ver_choices else None
        
        pos_label = {"before": "앞에", "after": "뒤에", "end": "맨 끝"}.get(insert_position, "")
        gr.Info(f"성공: {stage_short}-{new_index} 노드로 케이스가 {pos_label} 삽입되었습니다!")
        
        return (
            gr.update(choices=node_choices, value=new_index),
            gr.update(choices=node_choices, value=new_index),
            gr.update(choices=ver_choices, value=default_ver),
            f"{stage_short}-{new_index}: {case_title.strip()}",
            case_content.strip()
        )
    except Exception as e:
        print("Error inserting case scenario node:", e)
        gr.Warning(f"시나리오 노드 삽입 실패: {str(e)}")
        return gr.update(), gr.update(), gr.update(), "", ""

def generate_scene(project_str, system_prompt, overall_plot, positive_prompt, negative_prompt, scene_instruction, selected_chars, target_node_id):
    if not project_str:
        yield "프로젝트를 먼저 생성하거나 선택하세요.", [], "변경사항 없음", "설정 충돌 없음", gr.update()
        return
        
    project_id = parse_project_id(project_str)
    
    try:
        proj = db_session.query(Project).filter(Project.id == project_id).first()
        if proj:
            proj.system_prompt = system_prompt
            proj.overall_plot = overall_plot
            proj.positive_prompt = positive_prompt
            proj.negative_prompt = negative_prompt
            db_session.commit()
            db_session.expire_all()
    except Exception as e:
        print("Error saving settings before generation:", e)
        
    # Fetch all characters from DB
    characters = db_session.query(Character).filter(Character.project_id == project_id).all()
    
    # If selected_chars is empty or None, fallback to all characters
    if not selected_chars:
        selected_chars = [c.name for c in characters]
        
    char_list = [c.name for c in characters if c.name in selected_chars]
    char_profiles_text = "[현재 씬 등장인물 프로필]\n"
    
    for char in characters:
        if char.name not in selected_chars:
            continue
        role_label = {
            'male_hero': '남자 주인공',
            'female_hero': '여자 주인공',
            'male_sub': '남자 조연',
            'female_sub': '여자 조연',
            'other': '기타'
        }.get(char.relations, '기타')
        char_list.append(char.name)
        char_profiles_text += f"- {char.name} ({role_label}): {char.personality or ''}\n"
        if char.character_relations:
            char_profiles_text += f"  (다른 인물과의 관계: {char.character_relations})\n"
    
    # 중복 제거 (append가 두 번 될 수 있으므로 set 변환 후 정렬하거나 위에서 append 한 것 제거)
    char_list = list(set(char_list))
    # DB 조회 순서 유지를 위해 정렬 또는 원래 characters 순서대로 필터링
    char_list = [c.name for c in characters if c.name in selected_chars]
    
    # 1. Context Routing
    context = router.build_context(project_id, scene_instruction, target_node_id=target_node_id)
    overall_plot_text = f"[소설 전체 줄거리]\n{overall_plot.strip()}\n" if overall_plot.strip() else ""
    full_context = f"{char_profiles_text}\n{overall_plot_text}\n{context}"
    
    # 2. Multi-POV Synthesizer (스트리밍)
    accumulated_text = ""
    for event_type, content in synthesizer.run_pipeline_streaming(
        context=full_context, 
        scene_instruction=scene_instruction, 
        characters=char_list,
        system_prompt=system_prompt.strip() if system_prompt.strip() else None,
        positive=positive_prompt.strip() if positive_prompt.strip() else None,
        negative=negative_prompt.strip() if negative_prompt.strip() else None
    ):
        if event_type == "status":
            # 상태 메시지를 본문 영역에 노출하지 않고 화면을 깔끔하게 유지 (사용자 피드백 반영)
            yield accumulated_text, [], "🔍 검증 대기 중... (검증 실행 버튼을 눌러주세요)", "🔍 검증 대기 중... (검증 실행 버튼을 눌러주세요)", gr.update()
        elif event_type == "text":
            accumulated_text += content
            yield accumulated_text, [], "🔍 검증 대기 중... (검증 실행 버튼을 눌러주세요)", "🔍 검증 대기 중... (검증 실행 버튼을 눌러주세요)", gr.update()
    
    raw_scene = accumulated_text
    
    # 검증 단계는 씬 생성에서 제외하여 속도 최적화 (수동 실행으로 이관)
    tracker_msg = "🔍 검증 대기 중... (오른쪽 하단의 '정합성 & 팩트 검증 실행' 버튼을 눌러주세요)"
    fact_msg = "🔍 검증 대기 중... (오른쪽 하단의 '정합성 & 팩트 검증 실행' 버튼을 눌러주세요)"
    
    # 5. Style & Rhythm Filter
    yield raw_scene, [], fact_msg, tracker_msg, gr.update()
    filter_result = style_filter.process(raw_scene)
    final_scene = filter_result["corrected"]
    
    # 6. Save to Database (Scenario Node & History Log)
    new_node = ScenarioNode(
        project_id=project_id,
        stage="Development",
        parent_id=target_node_id if target_node_id else None,
        content=final_scene,
        commit_message="AI 자동 생성 씬"
    )
    db_session.add(new_node)
    db_session.commit()
    
    history_log = HistoryLog(
        scenario_node_id=new_node.id,
        action_type="CREATE_WITH_FILTER",
        before_content=raw_scene,
        after_content=final_scene,
        tracker_result=tracker_msg,
        fact_result=fact_msg,
        user_prompt=scene_instruction
    )
    db_session.add(history_log)
    db_session.commit()

    # Create diff for UI
    diff_output = diff_texts(raw_scene, final_scene)
    
    choices = get_scene_history_choices(project_str, target_node_id)
    yield final_scene, diff_output, fact_msg, tracker_msg, gr.update(choices=choices, value=new_node.id)

def verify_generated_scene(project_str, scene_content, target_node_id=None):
    if not project_str:
        yield "⚠️ 프로젝트를 선택해주세요.", "⚠️ 프로젝트를 선택해주세요."
        return
    if not scene_content or not scene_content.strip():
        yield "⚠️ 검증할 소설 내용이 없습니다.", "⚠️ 검증할 소설 내용이 없습니다."
        return
        
    yield "⏳ [1/2] 팩트 vs 허구 교차 고증 검증 중...", "⏳ [1/2] 타임라인 정합성 LLM 검증 대기 중..."
    
    project_id = parse_project_id(project_str)
    
    # 1. 팩트 체커 실행 (로컬 사전식 분석이므로 즉시 완료)
    fact_result = fact_checker.check_facts(scene_content)
    warning_yn = "예 (주의 필요)" if fact_result.get('has_warnings') else "아니오 (팩트 이상 없음)"
    fact_msg = f"팩트 경고 감지: {warning_yn}\n관련 법리/팩트 데이터: {fact_result.get('facts', {})}"
    
    yield fact_msg, "⏳ [2/2] 타임라인 정합성 LLM 검증 중 (이전 시나리오 맥락 대조)..."
    
    # 2. 컨텍스트 수집 및 타임라인 검증 (LLM 호출)
    characters = db_session.query(Character).filter(Character.project_id == project_id).all()
    char_profiles_text = "[현재 씬 등장인물 프로필]\n"
    for char in characters:
        role_label = {
            'male_hero': '남자 주인공',
            'female_hero': '여자 주인공',
            'male_sub': '남자 조연',
            'female_sub': '여자 조연',
            'other': '기타'
        }.get(char.relations, '기타')
        char_profiles_text += f"- {char.name} ({role_label}): {char.personality or ''}\n"
        if char.character_relations:
            char_profiles_text += f"  (다른 인물과의 관계: {char.character_relations})\n"
            
    proj = db_session.query(Project).filter(Project.id == project_id).first()
    if not proj:
        yield fact_msg, "⚠️ 프로젝트가 존재하지 않습니다."
        return
    overall_plot = proj.overall_plot or ""
    overall_plot_text = f"[소설 전체 줄거리]\n{overall_plot.strip()}\n" if overall_plot.strip() else ""
    
    context = router.build_context(project_id, "", target_node_id=target_node_id)
    full_context = f"{char_profiles_text}\n{overall_plot_text}\n{context}"
    
    # 타임라인 정합성 LLM 검증 실행
    tracker_result = tracker.validate_logic(full_context, scene_content)
    conflict_yn = "예 (충돌 발견)" if tracker_result.get('conflict_found') else "아니오 (충돌 없음)"
    tracker_msg = f"충돌 감지 여부: {conflict_yn}\n상세 이유: {tracker_result.get('reason', '')}"
    
    # 3. 최신 HistoryLog DB 기록 업데이트
    try:
        latest_log = db_session.query(HistoryLog)\
            .join(ScenarioNode)\
            .filter(ScenarioNode.project_id == project_id)\
            .order_by(HistoryLog.id.desc())\
            .first()
        if latest_log:
            latest_log.tracker_result = tracker_msg
            latest_log.fact_result = fact_msg
            db_session.commit()
    except Exception as e:
        print("Error updating history log with verification results:", e)
        
    yield fact_msg, tracker_msg

def get_fallback_scenario(project_title, genre):
    fallback = {}
    stages = ["기", "승", "전", "결"]
    for s in stages:
        fallback[s] = []
        for i in range(1, 6):
            fallback[s].append({
                "title": f"{s}-{i}: {project_title}의 에피소드 {i}",
                "content": f"{project_title}의 {genre or '드라마'} 장르에 맞춘 {s} 단계의 {i}번째 세부 에피소드입니다. 갈등과 서사가 점진적으로 고조됩니다."
            })
    return fallback

def api_generate_scenario_nodes(project_str):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), gr.update(), gr.update()
        
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        gr.Warning("프로젝트를 찾을 수 없습니다.")
        return gr.update(), gr.update(), gr.update()
        
    # Get characters profile string
    characters_str = ""
    characters = db_session.query(Character).filter(Character.project_id == pid).all()
    for char in characters:
        relation_kor = "남자 주인공" if char.relations == "male_hero" else ("여자 주인공" if char.relations == "female_hero" else "조연")
        characters_str += f"- {char.name} ({relation_kor}): {char.personality or ''}\n"
        
    try:
        gr.Info("기승전결 시나리오 자동 생성을 시작합니다... (이 작업은 약 20~30초 소요될 수 있습니다)")
        client = synthesizer.client
        
        system_instruction = (
            "You are an expert novel planner. "
            "Your task is to generate a detailed 4-stage narrative outline based on the Korean plot structure '기-승-전-결' (起-承-轉-結). "
            "For each stage ('기', '승', '전', '결'), you MUST generate exactly 4 to 5 sequential, detailed scenario nodes. "
            "You must output the result strictly in JSON format. Do not write any markdown outside the JSON."
        )
        
        user_prompt = (
            f"소설 제목: {proj.title}\n"
            f"장르: {proj.genre or '드라마'}\n"
            f"전체 소설 줄거리:\n{proj.overall_plot or '줄거리 없음'}\n\n"
            f"등장인물 정보:\n{characters_str}\n\n"
            f"Please generate exactly 4 to 5 scenario nodes for each of '기', '승', '전', '결'. "
            f"The output must be a valid JSON object with the following schema:\n"
            f"{{\n"
            f"  \"기\": [\n"
            f"    {{\"title\": \"씬 제목\", \"content\": \"상세 씬 설명 및 플롯 지침 (3-4문장)\"}},\n"
            f"    ...\n"
            f"  ],\n"
            f"  \"승\": [...],\n"
            f"  \"전\": [...],\n"
            f"  \"결\": [...]\n"
            f"}}\n"
            f"Write all scenario titles and content strictly in Korean, aligning with the story tone and characters."
        )
        
        result = client.send_chat_completion(
            system_prompt=system_instruction,
            user_prompt=user_prompt,
            temperature=0.8,
            parse_json=True
        )
        
        if not result or not isinstance(result, dict):
            print("Failed to generate JSON scenario, using fallback...")
            result = get_fallback_scenario(proj.title, proj.genre)
    except Exception as e:
        print("Error during LLM scenario generation:", e)
        result = get_fallback_scenario(proj.title, proj.genre)
        
    stages_mapping = {
        "기": "기 (起 - 도입)",
        "승": "승 (承 - 전개)",
        "전": "전 (轉 - 위기/절정)",
        "결": "결 (結 - 결말)"
    }
    
    existing_count = db_session.query(ScenarioNode).filter(ScenarioNode.project_id == pid).count()
    commit_msg = "자동 생성 시나리오" if existing_count == 0 else f"자동 생성 시나리오 (재생성)"
    
    # Save to DB
    for key, stage_name in stages_mapping.items():
        items = result.get(key, [])
        if not items:
            eng_key = {"기": "Introduction", "승": "Development", "전": "Turn", "결": "Conclusion"}[key]
            items = result.get(eng_key, [])
        if not items:
            items = get_fallback_scenario(proj.title, proj.genre).get(key, [])
            
        for i, item in enumerate(items):
            title = item.get("title", f"{key}-{i+1} 씬")
            content = item.get("content", "내용 없음")
            
            node = ScenarioNode(
                project_id=pid,
                stage=stage_name,
                node_index=i+1,
                title=title,
                parent_id=None,
                content=content,
                commit_message=commit_msg
            )
            db_session.add(node)
            
    db_session.commit()
    gr.Info("기승전결 시나리오가 성공적으로 자동 생성되었습니다!")
    
    stage_choices = list(stages_mapping.values())
    default_stage = stage_choices[0]
    
    node_choices = get_node_choices_for_stage(pid, default_stage)
    default_node = node_choices[0][1] if node_choices else None
    
    ver_choices = build_commit_tree_choices(pid, default_stage, default_node)
    default_ver = max(ver_choices, key=lambda x: x[1])[1] if ver_choices else None
    
    return (
        gr.update(choices=stage_choices, value=default_stage),
        gr.update(choices=node_choices, value=default_node),
        gr.update(choices=ver_choices, value=default_ver)
    )

def on_case_stage_change(project_str, stage):
    if not project_str or not stage:
        return gr.update(choices=[], value=None), gr.update(choices=[], value=None), "", ""
    pid = parse_project_id(project_str)
    node_choices = get_node_choices_for_stage(pid, stage)
    default_node = node_choices[0][1] if node_choices else None
    
    ver_choices = []
    default_ver = None
    content = ""
    title = ""
    if default_node is not None:
        ver_choices = build_commit_tree_choices(pid, stage, default_node)
        default_ver = max(ver_choices, key=lambda x: x[1])[1] if ver_choices else None
        if default_ver:
            node = db_session.query(ScenarioNode).filter(ScenarioNode.id == default_ver).first()
            if node:
                content = node.content or ""
                title = node.title or ""
                
    return (
        gr.update(choices=node_choices, value=default_node),
        gr.update(choices=ver_choices, value=default_ver),
        content,
        title
    )

def on_case_node_change(project_str, stage, node_index):
    if not project_str or not stage or node_index is None:
        return gr.update(choices=[], value=None), "", ""
    pid = parse_project_id(project_str)
    ver_choices = build_commit_tree_choices(pid, stage, node_index)
    default_ver = max(ver_choices, key=lambda x: x[1])[1] if ver_choices else None
    
    content = ""
    title = ""
    if default_ver:
        node = db_session.query(ScenarioNode).filter(ScenarioNode.id == default_ver).first()
        if node:
            content = node.content or ""
            title = node.title or ""
            
    return (
        gr.update(choices=ver_choices, value=default_ver),
        content,
        title
    )

def on_case_ver_change(ver_id):
    if not ver_id:
        return "", ""
    try:
        node = db_session.query(ScenarioNode).filter(ScenarioNode.id == ver_id).first()
        if node:
            return node.content or "", node.title or ""
    except Exception as e:
        print("Error in on_case_ver_change:", e)
    return "", ""

def on_case_save_ver(project_str, stage, node_index, ver_id, title, content):
    ret = save_current_scenario_version(project_str, stage, node_index, ver_id, title, content, "")
    ver_choices_update, node_choices_update, target_scenario_choices_update, content, title = ret
    return (
        ver_choices_update,
        ver_choices_update,
        node_choices_update,
        node_choices_update,
        target_scenario_choices_update,
        content,
        content,
        title,
        title
    )

def on_case_delete_ver(project_str, stage, node_index, ver_id):
    ret = delete_scenario_version(project_str, stage, node_index, ver_id)
    ver_choices_update, node_choices_update, content, title = ret
    
    target_scenario_choices = get_target_scenario_node_choices(project_str)
    default_target_scen = target_scenario_choices[0][1] if target_scenario_choices else None
    target_scenario_choices_update = gr.update(choices=target_scenario_choices, value=default_target_scen)
    
    return (
        ver_choices_update,
        ver_choices_update,
        node_choices_update,
        node_choices_update,
        target_scenario_choices_update,
        content,
        content,
        title,
        title
    )

def on_case_commit_ver(project_str, stage, node_index, title, content, commit_msg, ver_id):
    ret = commit_new_scenario_version(project_str, stage, node_index, title, content, commit_msg, ver_id, "")
    ver_choices_update, node_choices_update, _ = ret
    
    target_scenario_choices = get_target_scenario_node_choices(project_str)
    default_target_scen = target_scenario_choices[0][1] if target_scenario_choices else None
    target_scenario_choices_update = gr.update(choices=target_scenario_choices, value=default_target_scen)
    
    return (
        ver_choices_update,
        ver_choices_update,
        node_choices_update,
        node_choices_update,
        target_scenario_choices_update,
        content,
        content,
        title,
        title,
        ""
    )

def update_erotic_char_dropdowns(project_str):
    if not project_str:
        return gr.update(choices=[], value=None), gr.update(choices=[], value=None)
    choices = get_character_dropdown_choices(project_str)
    pid = parse_project_id(project_str)
    try:
        characters = db_session.query(Character).filter(Character.project_id == pid).all()
    except Exception as e:
        print("Error fetching characters for erotic dropdowns:", e)
        characters = []
        
    default_female = None
    default_male = None
    for c in characters:
        if c.relations == "female_hero":
            default_female = c.id
        elif c.relations == "male_hero":
            default_male = c.id
            
    if not default_female and choices:
        for label, cid in choices:
            if "여자" in label:
                default_female = cid
                break
    if not default_male and choices:
        for label, cid in choices:
            if "남자" in label:
                default_male = cid
                break

    return (
        gr.update(choices=choices, value=default_female),
        gr.update(choices=choices, value=default_male)
    )

def on_female_char_select(char_id):
    if not char_id:
        return ""
    try:
        char = db_session.query(Character).filter(Character.id == char_id).first()
        if char:
            desc = f"[{char.name}]: {char.personality or ''}"
            if char.background:
                desc += f"\n배경: {char.background}"
            return desc
    except Exception as e:
        print("Error on female character select:", e)
    return ""

def on_male_char_select(char_id):
    if not char_id:
        return ""
    try:
        char = db_session.query(Character).filter(Character.id == char_id).first()
        if char:
            desc = f"[{char.name}]: {char.personality or ''}"
            if char.background:
                desc += f"\n배경: {char.background}"
            return desc
    except Exception as e:
        print("Error on male character select:", e)
    return ""

def ai_generate_erotic_settings(female_char_id, male_char_id):
    if not female_char_id or not male_char_id:
        gr.Warning("여성 캐릭터와 남성 캐릭터를 모두 선택해 주세요.")
        return gr.update(), gr.update(), gr.update(), gr.update()
        
    try:
        female_char = db_session.query(Character).filter(Character.id == female_char_id).first()
        male_char = db_session.query(Character).filter(Character.id == male_char_id).first()
        
        if not female_char or not male_char:
            gr.Warning("캐릭터 정보를 찾을 수 없습니다.")
            return gr.update(), gr.update(), gr.update(), gr.update()
            
        female_info = f"이름: {female_char.name}\n역할: {female_char.relations or ''}\n성격/특징: {female_char.personality or ''}\n배경: {female_char.background or ''}\n타 캐릭터와의 관계성: {female_char.character_relations or ''}\n말투: {female_char.speech_style or ''}"
        male_info = f"이름: {male_char.name}\n역할: {male_char.relations or ''}\n성격/특징: {male_char.personality or ''}\n배경: {male_char.background or ''}\n타 캐릭터와의 관계성: {male_char.character_relations or ''}\n말투: {male_char.speech_style or ''}"
        
        system_prompt = (
            "당신은 인간의 복잡한 심리와 관능적 긴장감을 섬세하게 묘사하는 전문 시나리오 작가이자 심리 분석가입니다.\n"
            "주어진 두 캐릭터 정보를 바탕으로, 관능 시나리오 분화(Erotic Scenario Branching)를 위해 적절한 캐릭터 설정, 관계성 설정, 그리고 첫 번째 도발이 일어날 수 있는 특정 상황/미션을 설정하여 JSON 형식으로 제공해 주세요.\n"
            "반드시 JSON 형식으로만 응답해야 하며, JSON 스키마는 다음과 같습니다:\n"
            "{\n"
            "  \"female_desc\": \"여성 캐릭터에 대한 관능적/심리적 성격 묘사 (예: [스미래 / 30대 중반 미망인]: 겉으로는 정숙하나...)\",\n"
            "  \"male_desc\": \"남성 캐릭터에 대한 관능적/심리적 성격 묘사 (예: [히로시 / 20대 초반 대학생]: 성실하지만 본능에 흔들리는...)\",\n"
            "  \"relations\": \"두 사람의 관능적 관계성 키워드 (예: 연상녀-연하남 / 금기된 관계 / 유혹하는 자와 함락되는 자)\",\n"
            "  \"situation\": \"첫 관능적 긴장이나 미션을 유도할 수 있는 구체적이고 자극적인 특정 상황 (예: 옷을 벗겨달라고 요구하는 상황)\"\n"
            "}"
        )
        
        user_prompt = (
            f"여성 캐릭터 정보:\n{female_info}\n\n"
            f"남성 캐릭터 정보:\n{male_info}"
        )
        
        gr.Info("AI가 캐릭터에 특화된 관능 설정을 생성 중입니다...")
        result = llama_client.send_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.8,
            parse_json=True
        )
        
        if not result or not isinstance(result, dict):
            gr.Warning("AI 설정 생성에 실패했습니다. 기본 또는 기존 설정 값을 사용해 주세요.")
            return gr.update(), gr.update(), gr.update(), gr.update()
            
        f_desc = result.get("female_desc", "")
        m_desc = result.get("male_desc", "")
        rels = result.get("relations", "")
        sit = result.get("situation", "")
        
        gr.Info("AI 설정이 생성 및 반영되었습니다!")
        return f_desc, m_desc, rels, sit
        
    except Exception as e:
        print("Error generating AI erotic settings:", e)
        gr.Warning(f"AI 설정 생성 중 오류가 발생했습니다: {str(e)}")
        return gr.update(), gr.update(), gr.update(), gr.update()

def on_scen_stage_change(project_str, stage):
    ret = on_stage_change(project_str, stage)
    scen_node, scen_ver, content, title, regen_prompt = ret
    return (
        scen_node,
        scen_node,
        scen_ver,
        scen_ver,
        content,
        content,
        title,
        title,
        regen_prompt
    )

def on_scen_node_change(project_str, stage, node_index):
    ret = on_node_change(project_str, stage, node_index)
    scen_ver, content, title, regen_prompt = ret
    return (
        scen_ver,
        scen_ver,
        content,
        content,
        title,
        title,
        regen_prompt
    )

def on_scen_ver_change(ver_id):
    ret = on_ver_change(ver_id)
    content, title, regen_prompt = ret
    return (
        content,
        content,
        title,
        title,
        regen_prompt
    )

def on_scen_save_ver(project_str, stage, node_index, ver_id, title, content, regen_prompt):
    ret = save_current_scenario_version(project_str, stage, node_index, ver_id, title, content, regen_prompt)
    ver_choices_update, node_choices_update, target_scenario_choices_update, content, title = ret
    return (
        ver_choices_update,
        ver_choices_update,
        node_choices_update,
        node_choices_update,
        target_scenario_choices_update,
        content,
        content,
        title,
        title
    )

def on_scen_delete_ver(project_str, stage, node_index, ver_id):
    ret = delete_scenario_version(project_str, stage, node_index, ver_id)
    ver_choices_update, node_choices_update, content, title = ret
    target_scenario_choices = get_target_scenario_node_choices(project_str)
    default_target_scen = target_scenario_choices[0][1] if target_scenario_choices else None
    target_scenario_choices_update = gr.update(choices=target_scenario_choices, value=default_target_scen)
    return (
        ver_choices_update,
        ver_choices_update,
        node_choices_update,
        node_choices_update,
        target_scenario_choices_update,
        content,
        content,
        title,
        title
    )

def on_scen_commit_ver(project_str, stage, node_index, title, content, commit_msg, ver_id, regen_prompt):
    ret = commit_new_scenario_version(project_str, stage, node_index, title, content, commit_msg, ver_id, regen_prompt)
    ver_choices_update, node_choices_update, _ = ret
    target_scenario_choices = get_target_scenario_node_choices(project_str)
    default_target_scen = target_scenario_choices[0][1] if target_scenario_choices else None
    target_scenario_choices_update = gr.update(choices=target_scenario_choices, value=default_target_scen)
    return (
        ver_choices_update,
        ver_choices_update,
        node_choices_update,
        node_choices_update,
        target_scenario_choices_update,
        content,
        content,
        title,
        title,
        ""
    )

def on_stage_change(project_str, stage):
    if not project_str or not stage:
        return gr.update(choices=[], value=None), gr.update(choices=[], value=None), "", "", ""
    pid = parse_project_id(project_str)
    
    node_choices = get_node_choices_for_stage(pid, stage)
    default_node = node_choices[0][1] if node_choices else None
    
    ver_choices = build_commit_tree_choices(pid, stage, default_node)
    default_ver = max(ver_choices, key=lambda x: x[1])[1] if ver_choices else None
    
    content = ""
    title = ""
    regen_prompt = ""
    if default_ver:
        node = db_session.query(ScenarioNode).filter(ScenarioNode.id == default_ver).first()
        if node:
            content = node.content
            title = node.title or ""
            regen_prompt = node.regen_prompt or ""
            
    return (
        gr.update(choices=node_choices, value=default_node),
        gr.update(choices=ver_choices, value=default_ver),
        content,
        title,
        regen_prompt
    )

def on_node_change(project_str, stage, node_index):
    if not project_str or not stage or node_index is None:
        return gr.update(choices=[], value=None), "", "", ""
    pid = parse_project_id(project_str)
    
    ver_choices = build_commit_tree_choices(pid, stage, node_index)
    default_ver = max(ver_choices, key=lambda x: x[1])[1] if ver_choices else None
    
    content = ""
    title = ""
    regen_prompt = ""
    if default_ver:
        node = db_session.query(ScenarioNode).filter(ScenarioNode.id == default_ver).first()
        if node:
            content = node.content
            title = node.title or ""
            regen_prompt = node.regen_prompt or ""
            
    return (
        gr.update(choices=ver_choices, value=default_ver),
        content,
        title,
        regen_prompt
    )

def on_ver_change(ver_id):
    if not ver_id:
        return "", "", ""
    node = db_session.query(ScenarioNode).filter(ScenarioNode.id == ver_id).first()
    if node:
        return node.content, node.title or "", node.regen_prompt or ""
    return "", "", ""

def add_scenario_node(project_str, stage, current_node_index, insert_position):
    """선택된 플롯 단계(Stage)에 새 빈 시나리오 노드를 삽입합니다.
    insert_position: 'before' | 'after' | 'end'
    """
    if not project_str or not stage:
        gr.Warning("프로젝트와 플롯 단계를 먼저 선택해 주세요.")
        return gr.update(), gr.update(), "", ""
    pid = parse_project_id(project_str)
    try:
        # 현재 stage의 모든 노드를 node_index 순으로 가져온다
        existing = db_session.query(ScenarioNode).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage == stage
        ).order_by(ScenarioNode.node_index).all()
        
        existing_indices = sorted(set(n.node_index for n in existing if n.node_index is not None))
        max_index = max(existing_indices) if existing_indices else 0
        
        # 삽입 위치 결정
        if insert_position == "end" or current_node_index is None or not existing_indices:
            new_index = max_index + 1
        elif insert_position == "before":
            new_index = current_node_index  # 현재 위치를 받고 기존을 늤로 밀음
        else:  # "after"
            new_index = current_node_index + 1
        
        # new_index 이상의 노드들의 node_index를 +1 시켰 (스공 만들기)
        if insert_position != "end" and current_node_index is not None:
            for node in existing:
                if node.node_index is not None and node.node_index >= new_index:
                    node.node_index += 1
            db_session.flush()
        
        stage_short = stage.split()[0] if stage else "기"
        new_node = ScenarioNode(
            project_id=pid,
            stage=stage,
            node_index=new_index,
            title=f"{stage_short}-{new_index}: 새 시나리오",
            content="",
            commit_message="사용자 직접 추가"
        )
        db_session.add(new_node)
        db_session.commit()
        db_session.expire_all()
        
        node_choices = get_node_choices_for_stage(pid, stage)
        ver_choices = build_commit_tree_choices(pid, stage, new_index)
        default_ver = max(ver_choices, key=lambda x: x[1])[1] if ver_choices else None
        
        pos_label = {"before": "앞에", "after": "뒤에", "end": "맨 끝"}.get(insert_position, "")
        gr.Info(f"{stage_short}-{new_index} 노드가 {pos_label} 삽입되었습니다.")
        return (
            gr.update(choices=node_choices, value=new_index),
            gr.update(choices=ver_choices, value=default_ver),
            f"{stage_short}-{new_index}: 새 시나리오",
            ""
        )
    except Exception as e:
        print("Error adding scenario node:", e)
        gr.Warning(f"노드 추가 중 오류가 발생했습니다: {str(e)}")
        return gr.update(), gr.update(), "", ""

def delete_scenario_node(project_str, stage, node_index):
    """선택된 시나리오 노드와 해당 노드의 모든 버전을 삭제합니다."""
    if not project_str or not stage or node_index is None:
        gr.Warning("삭제할 노드를 먼저 선택해 주세요.")
        return gr.update(), gr.update(), "", ""
    pid = parse_project_id(project_str)
    try:
        nodes_to_delete = db_session.query(ScenarioNode).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage == stage,
            ScenarioNode.node_index == node_index
        ).all()
        
        if not nodes_to_delete:
            gr.Warning("삭제할 노드를 찾을 수 없습니다.")
            return gr.update(), gr.update(), "", ""
        
        for node in nodes_to_delete:
            db_session.query(HistoryLog).filter(HistoryLog.scenario_node_id == node.id).delete()
            db_session.delete(node)
        
        db_session.commit()
        db_session.expire_all()
        
        node_choices = get_node_choices_for_stage(pid, stage)
        new_node_val = node_choices[0][1] if node_choices else None
        ver_choices = build_commit_tree_choices(pid, stage, new_node_val)
        default_ver = max(ver_choices, key=lambda x: x[1])[1] if ver_choices else None
        
        content, title = "", ""
        if default_ver:
            n = db_session.query(ScenarioNode).filter(ScenarioNode.id == default_ver).first()
            if n:
                content = n.content or ""
                title = n.title or ""
        
        stage_short = stage.split()[0] if stage else "기"
        gr.Info(f"{stage_short}-{node_index} 노드 및 모든 버전이 삭제되었습니다.")
        return (
            gr.update(choices=node_choices, value=new_node_val),
            gr.update(choices=ver_choices, value=default_ver),
            title,
            content
        )
    except Exception as e:
        print("Error deleting scenario node:", e)
        gr.Warning(f"노드 삭제 중 오류가 발생했습니다: {str(e)}")
        return gr.update(), gr.update(), "", ""

def commit_new_scenario_version(project_str, stage, node_index, title, content, commit_message, parent_ver_id, regen_prompt_text):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(choices=[], value=None), gr.update(), ""
    if node_index is None:
        gr.Warning("선택된 시나리오 노드가 없습니다.")
        return gr.update(), gr.update(), ""
    if not content.strip():
        gr.Warning("내용을 입력해 주세요.")
        return gr.update(), gr.update(), ""
    if not commit_message.strip():
        commit_message = "수동 편집 버전"
        
    pid = parse_project_id(project_str)
    
    new_node = ScenarioNode(
        project_id=pid,
        stage=stage,
        node_index=node_index,
        title=title.strip() if title.strip() else f"{stage}-{node_index} 씬",
        parent_id=parent_ver_id if parent_ver_id else None,
        content=content.strip(),
        regen_prompt=regen_prompt_text.strip() if regen_prompt_text else None,
        commit_message=commit_message.strip()
    )
    db_session.add(new_node)
    db_session.commit()
    gr.Info("새로운 시나리오 버전이 성공적으로 커밋되었습니다!")
    
    ver_choices = build_commit_tree_choices(pid, stage, node_index)
    node_choices = get_node_choices_for_stage(pid, stage)
    
    return (
        gr.update(choices=ver_choices, value=new_node.id),
        gr.update(choices=node_choices, value=node_index),
        ""
    )

def save_current_scenario_version(project_str, stage, node_index, ver_id, title, content, regen_prompt_text):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), gr.update(), gr.update(), "", ""
    if node_index is None:
        gr.Warning("선택된 시나리오 노드가 없습니다.")
        return gr.update(), gr.update(), gr.update(), "", ""
    if not content.strip():
        gr.Warning("내용을 입력해 주세요.")
        return gr.update(), gr.update(), gr.update(), "", ""
        
    pid = parse_project_id(project_str)
    
    node = None
    if ver_id:
        node = db_session.query(ScenarioNode).filter(ScenarioNode.id == ver_id).first()
        
    if node:
        node.title = title.strip() if title.strip() else f"{stage}-{node_index} 씬"
        node.content = content.strip()
        node.regen_prompt = regen_prompt_text.strip() if regen_prompt_text else None
        node.created_at = datetime.utcnow()
        db_session.commit()
        db_session.expire_all()
        gr.Info("현재 시나리오 버전의 변경사항이 성공적으로 저장되었습니다.")
        target_node_id = node.id
    else:
        new_node = ScenarioNode(
            project_id=pid,
            stage=stage,
            node_index=node_index,
            title=title.strip() if title.strip() else f"{stage}-{node_index} 씬",
            content=content.strip(),
            regen_prompt=regen_prompt_text.strip() if regen_prompt_text else None,
            commit_message="수동 저장 버전"
        )
        db_session.add(new_node)
        db_session.commit()
        db_session.expire_all()
        gr.Info("새로운 시나리오 버전이 성공적으로 저장되었습니다.")
        target_node_id = new_node.id
        
    ver_choices = build_commit_tree_choices(pid, stage, node_index)
    node_choices = get_node_choices_for_stage(pid, stage)
    target_scenario_choices = get_target_scenario_node_choices(project_str)
    
    default_target_scen = target_scenario_choices[0][1] if target_scenario_choices else None
    
    return (
        gr.update(choices=ver_choices, value=target_node_id),
        gr.update(choices=node_choices, value=node_index),
        gr.update(choices=target_scenario_choices, value=default_target_scen),
        content,
        title
    )

def delete_scenario_version(project_str, stage, node_index, ver_id):
    if not ver_id:
        gr.Warning("삭제할 버전을 선택해 주세요.")
        return gr.update(choices=[]), gr.update(), "", ""
        
    try:
        node = db_session.query(ScenarioNode).filter(ScenarioNode.id == ver_id).first()
        if node:
            children = db_session.query(ScenarioNode).filter(ScenarioNode.parent_id == ver_id).all()
            for child in children:
                child.parent_id = node.parent_id
                
            db_session.delete(node)
            db_session.commit()
            gr.Info("시나리오 버전이 성공적으로 삭제되었습니다.")
    except Exception as e:
        print("Error deleting scenario version:", e)
        gr.Warning("시나리오 버전 삭제 중 오류가 발생했습니다.")
        
    pid = parse_project_id(project_str)
    ver_choices = build_commit_tree_choices(pid, stage, node_index)
    default_ver = max(ver_choices, key=lambda x: x[1])[1] if ver_choices else None
    
    content = ""
    title = ""
    if default_ver:
        n = db_session.query(ScenarioNode).filter(ScenarioNode.id == default_ver).first()
        if n:
            content = n.content
            title = n.title or ""
            
    node_choices = get_node_choices_for_stage(pid, stage)
    
    return (
        gr.update(choices=ver_choices, value=default_ver),
        gr.update(choices=node_choices, value=node_index),
        content,
        title
    )

def regenerate_scenario_node(project_str, stage, node_index, title, parent_ver_id, user_regen_prompt):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), gr.update(), ""
    if node_index is None:
        gr.Warning("선택된 시나리오 노드가 없습니다.")
        return gr.update(), gr.update(), ""
        
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        gr.Warning("프로젝트를 찾을 수 없습니다.")
        return gr.update(), gr.update(), ""
        
    gr.Info("해당 노드를 인공지능이 재구성하는 중입니다...")
    client = synthesizer.client
    
    characters_str = ""
    characters = db_session.query(Character).filter(Character.project_id == pid).all()
    for char in characters:
        relation_kor = "남자 주인공" if char.relations == "male_hero" else ("여자 주인공" if char.relations == "female_hero" else "조연")
        characters_str += f"- {char.name} ({relation_kor}): {char.personality or ''}\n"
        
    overall_plot = proj.overall_plot or "줄거리 없음"
    
    system_instruction = (
        "You are an expert novel planner. "
        "Your task is to write a detailed scene description for a single scenario node. "
        "Write strictly in Korean, capturing the tone and characters."
    )
    
    user_prompt = (
        f"소설 제목: {proj.title}\n"
        f"장르: {proj.genre or '드라마'}\n"
        f"전체 소설 줄거리:\n{overall_plot}\n\n"
        f"등장인물 정보:\n{characters_str}\n\n"
        f"현재 진행 단계: {stage}\n"
        f"노드 순번: {node_index}번째 에피소드\n"
        f"씬 제목: {title or '제목 없음'}\n\n"
    )
    
    if user_regen_prompt and user_regen_prompt.strip():
        user_prompt += (
            f"[사용자 지시사항]\n{user_regen_prompt.strip()}\n\n"
            f"위 지시사항을 반드시 반영하여, 이 씬에 대한 상세한 서사 개요와 플롯 가이드를 한국어로 작성하세요. "
            f"캐릭터 역학, 긴장감, 서사 전개에 집중하세요."
        )
    else:
        user_prompt += (
            f"Please write a detailed narrative outline and plot guidance for this specific scene (about 4-5 sentences in Korean). "
            f"Focus on character dynamics, tension, and narrative progression."
        )
    
    try:
        new_content = client.send_chat_completion(
            system_prompt=system_instruction,
            user_prompt=user_prompt,
            temperature=0.8
        )
        if not new_content or not isinstance(new_content, str):
            new_content = "인공지능 재구성 실패. 다시 시도해 주세요."
    except Exception as e:
        print("Error during single node regeneration:", e)
        new_content = f"에러 발생: {e}"
        
    new_node = ScenarioNode(
        project_id=pid,
        stage=stage,
        node_index=node_index,
        title=title if title.strip() else f"{stage}-{node_index} 씬",
        parent_id=parent_ver_id if parent_ver_id else None,
        content=new_content,
        regen_prompt=user_regen_prompt.strip() if user_regen_prompt else None,
        commit_message="AI 자동 재구성"
    )
    db_session.add(new_node)
    db_session.commit()
    
    ver_choices = build_commit_tree_choices(pid, stage, node_index)
    node_choices = get_node_choices_for_stage(pid, stage)
    
    gr.Info("노드가 성공적으로 재생성되어 새 버전으로 기록되었습니다!")
    return (
        gr.update(choices=ver_choices, value=new_node.id),
        gr.update(choices=node_choices, value=node_index),
        new_content
    )

def get_scene_history_choices(project_str, target_node_id=None):
    if not project_str:
        return []
    pid = parse_project_id(project_str)
    try:
        query = db_session.query(ScenarioNode).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage == "Development"
        )
        if target_node_id:
            query = query.filter(ScenarioNode.parent_id == target_node_id)
            
        nodes = query.order_by(ScenarioNode.created_at.desc()).all()
        
        # Determine finalized node: either explicitly node_index == 1, or fallback to the latest
        finalized_id = None
        for n in nodes:
            if n.node_index == 1:
                finalized_id = n.id
                break
        if not finalized_id and nodes:
            finalized_id = nodes[0].id
            
        choices = []
        for n in nodes:
            time_str = format_local_time(n.created_at)
            marker = " [★ 최종확정]" if n.id == finalized_id else ""
            label = f"[ID: {n.id}] {n.commit_message or 'No message'} ({time_str}){marker}"
            choices.append((label, n.id))
        return choices
    except Exception as e:
        print("Error getting scene history choices:", e)
        return []

def api_generate_characters(project_str):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), "", "other", "", ""
        
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        gr.Warning("프로젝트를 찾을 수 없습니다.")
        return gr.update(), "", "other", "", ""
        
    gr.Info("AI 등장인물 프로필 생성을 시작합니다...")
    client = synthesizer.client
    
    system_instruction = (
        "You are an expert novel planner. "
        "Your task is to analyze the overall plot and genre of a novel, and design compelling character profiles and relationships. "
        "You must generate exactly: "
        "1. One Male Hero (남자 주인공): name, personality (가면), background (결핍), character_relations (관계 역학), speech_style (말투). "
        "2. One Female Hero (여자 주인공): name, personality, background, character_relations, speech_style. "
        "3. One Male Supporting character (남자 조연): name, personality, background, character_relations, speech_style. "
        "4. One Female Supporting character (여자 조연): name, personality, background, character_relations, speech_style. "
        "5. One Other character (기타): name, personality, background, character_relations, speech_style. "
        "You must output the result strictly in JSON format. Do not write any markdown outside the JSON."
    )
    
    user_prompt = (
        f"소설 제목: {proj.title}\n"
        f"장르: {proj.genre or '드라마'}\n"
        f"전체 소설 줄거리:\n{proj.overall_plot or '줄거리 없음'}\n\n"
        f"Please design the characters and their relationships according to the story. "
        f"The output must be a valid JSON object with the following schema:\n"
        f"{{\n"
        f"  \"male_hero\": {{\n"
        f"    \"name\": \"이름/나이/지위 (예: 강이현 / 34세 / 본부장)\",\n"
        f"    \"personality\": \"겉으로 드러나는 가면 (표면적 성격)\",\n"
        f"    \"background\": \"숨겨진 결핍 및 본능\",\n"
        f"    \"character_relations\": \"심층 역학 (표면적 역학 vs 무의식적 긴장 등)\",\n"
        f"    \"speech_style\": \"공적인 공간 vs 사적인 공간 호칭과 말투 변화\"\n"
        f"  }},\n"
        f"  \"female_hero\": {{\n"
        f"    \"name\": \"...\",\n"
        f"    \"personality\": \"...\",\n"
        f"    \"background\": \"...\",\n"
        f"    \"character_relations\": \"...\",\n"
        f"    \"speech_style\": \"...\"\n"
        f"  }},\n"
        f"  \"male_sub\": {{\n"
        f"    \"name\": \"...\",\n"
        f"    \"personality\": \"...\",\n"
        f"    \"background\": \"...\",\n"
        f"    \"character_relations\": \"...\",\n"
        f"    \"speech_style\": \"...\"\n"
        f"  }},\n"
        f"  \"female_sub\": {{\n"
        f"    \"name\": \"...\",\n"
        f"    \"personality\": \"...\",\n"
        f"    \"background\": \"...\",\n"
        f"    \"character_relations\": \"...\",\n"
        f"    \"speech_style\": \"...\"\n"
        f"  }},\n"
        f"  \"other\": {{\n"
        f"    \"name\": \"...\",\n"
        f"    \"personality\": \"...\",\n"
        f"    \"background\": \"...\",\n"
        f"    \"character_relations\": \"...\",\n"
        f"    \"speech_style\": \"...\"\n"
        f"  }}\n"
        f"}}\n"
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
            if name:
                char = Character(
                    project_id=pid,
                    name=name,
                    relations=rel,
                    personality=personality,
                    background=background,
                    character_relations=relations_desc,
                    speech_style=speech_style
                )
                db_session.add(char)
                db_session.commit()
                if first_char_id is None:
                    first_char_id = char.id
                    
        gr.Info("AI 등장인물 프로필이 성공적으로 생성되어 저장되었습니다!")
        
    except Exception as e:
        print("Error during AI character generation:", e)
        gr.Warning("AI 프로필 생성 중 오류가 발생하여 기본 템플릿으로 대체합니다.")
        
        # Fallback templates
        templates = [
            ("강민준 / 32세 / 검사", "male_hero", "냉정하고 철저한 원칙주의자.", "내면의 상처로 인한 타인에 대한 불신과 통제욕구.", "서연우(여주): 공조 관계이나 무의식적으로 이끌림. 김영철(조연): 표면적으로만 신뢰.", "공적: '서연우 씨', 차가운 존댓말 / 사적: '너', 억눌린 텐션의 반말"),
            ("서연우 / 29세 / 기자", "female_hero", "따뜻한 성품과 남다른 직관력.", "과거 사건에 대한 죄책감과 인정욕구.", "강민준(남주): 경계심과 호기심이 교차함. 박소현(조연): 적대적 갈등 구조.", "공적: '강 검사님', 깍듯한 톤 / 사적: '민준 씨', 감정이 묻어나는 톤"),
            ("김영철 / 40세 / 수사관", "male_sub", "우직하고 우호적인 맏형.", "과도한 충성심으로 인한 시야 협착.", "강민준(남주): 절대적 복종. 서연우(여주): 경계하는 태도.", "공적/사적 일관되게 투박한 말투"),
            ("박소현 / 35세 / 정보 브로커", "female_sub", "비밀을 쥐고 있는 의문의 여인.", "물질적 욕망과 애정 결핍.", "서연우(여주): 감시와 대치 관계. 강민준(남주): 이용하려는 관계.", "나른하고 여유로우며 상대를 도발하는 말투"),
            ("최 형사 / 45세", "other", "자애로운 후원자의 탈을 씀.", "파괴적인 성향과 절대 권력욕.", "강민준(남주): 장기말처럼 이용. 박소현(조연): 필요에 의해 거래.", "상대의 심리를 압박하는 나긋나긋한 존댓말")
        ]
        
        for name, rel, personality, background, rel_desc, speech_style in templates:
            char = Character(
                project_id=pid,
                name=name,
                relations=rel,
                personality=personality,
                background=background,
                character_relations=rel_desc,
                speech_style=speech_style
            )
            db_session.add(char)
            db_session.commit()
            if first_char_id is None:
                first_char_id = char.id
                
    choices = get_character_dropdown_choices(project_str)
    name, role, personality, background, relations_desc, speech_style = on_character_select_change(first_char_id)
    return gr.update(choices=choices, value=first_char_id), name, role, personality, background, relations_desc, speech_style

def update_scene_history_dropdown(project_str, target_node_id=None):
    choices = get_scene_history_choices(project_str, target_node_id)
    val = choices[0][1] if choices else None
    return gr.update(choices=choices, value=val)

def get_target_scenario_node_choices(project_str):
    if not project_str:
        return []
    pid = parse_project_id(project_str)
    try:
        from sqlalchemy import func
        subquery = db_session.query(
            ScenarioNode.stage,
            ScenarioNode.node_index,
            func.max(ScenarioNode.created_at).label('max_created')
        ).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage != "Development"
        ).group_by(
            ScenarioNode.stage,
            ScenarioNode.node_index
        ).subquery()

        nodes = db_session.query(ScenarioNode).join(
            subquery,
            (ScenarioNode.stage == subquery.c.stage) &
            (ScenarioNode.node_index == subquery.c.node_index) &
            (ScenarioNode.created_at == subquery.c.max_created)
        ).filter(
            ScenarioNode.project_id == pid
        ).all()
        
        # 기-승-전-결(起承轉結) 올바른 순서로 정렬
        STAGE_ORDER = {
            "기 (起 - 도입)": 0,
            "승 (承 - 전개)": 1,
            "전 (轉 - 위기/절정)": 2,
            "결 (結 - 결말)": 3,
        }
        nodes.sort(key=lambda n: (
            STAGE_ORDER.get(n.stage, 99),
            n.node_index if n.node_index is not None else 0
        ))
        
        choices = []
        for n in nodes:
            stage_short = n.stage.split()[0] if n.stage else "기"
            label = f"[{stage_short} - {n.node_index}] {n.title or '제목 없음'}"
            choices.append((label, n.id))
        return choices
    except Exception as e:
        print("Error getting target scenario choices:", e)
        return []

def on_target_scenario_change(project_str, target_node_id):
    if not project_str or not target_node_id:
        return gr.update(choices=[], value=None), "", "", [], "", ""
        
    # 1. Load the outline content for the generator instruction
    outline = load_target_scenario_content(target_node_id)
    
    # 2. Get history choices for this specific target scenario node
    choices = get_scene_history_choices(project_str, target_node_id)
    
    val = None
    content = ""
    diff_output = []
    fact_result = ""
    tracker_result = ""
    
    if choices:
        # Find the one marked as finalized, or fallback to the first choice (latest)
        finalized_choice = None
        for label, nid in choices:
            if "최종확정" in label:
                finalized_choice = nid
                break
        val = finalized_choice if finalized_choice else choices[0][1]
        
        if val:
            content, diff_output, fact_result, tracker_result, _, _ = load_scene_history(val)
            
    return gr.update(choices=choices, value=val), outline, content, diff_output, fact_result, tracker_result

def load_target_scenario_content(node_id):
    if not node_id:
        return ""
    try:
        node = db_session.query(ScenarioNode).filter(ScenarioNode.id == node_id).first()
        if node:
            return node.content or ""
    except Exception as e:
        print("Error loading target scenario content:", e)
    return ""

def load_scene_history(node_id):
    if not node_id:
        return "", [], "", "", "", ""
    try:
        node = db_session.query(ScenarioNode).filter(ScenarioNode.id == node_id).first()
        if not node:
            return "", [], "", "", "", ""
        
        content = node.content or ""
        log = db_session.query(HistoryLog).filter(HistoryLog.scenario_node_id == node_id).first()
        
        instruction_val = ""
        refine_val = ""
        
        if log:
            before = log.before_content or ""
            after  = log.after_content or content
            # before가 비어있으면 diff가 무의미하므로 content 전체를 '추가됨'으로 표시
            if before.strip():
                diff_output = diff_texts(before, after)
            else:
                diff_output = [(w + " ", "교정 후 (추가됨)") for w in after.split()] if after else []
                
            if log.action_type == "CREATE_WITH_FILTER":
                instruction_val = log.user_prompt or ""
            elif log.action_type == "REFINE_WITH_PROMPT":
                refine_val = log.user_prompt or ""
                
            return after, diff_output, log.fact_result or "", log.tracker_result or "", instruction_val, refine_val
        else:
            # 로그가 없으면 content를 그대로 보여주고 diff는 전체 내용을 녹색으로 표시
            diff_output = [(w + " ", "교정 후 (추가됨)") for w in content.split()] if content else []
            return content, diff_output, "", "", "", ""
    except Exception as e:
        print("Error loading scene history:", e)
        return "", [], "", "", "", ""

def delete_scene_history(project_str, node_id, target_node_id=None):
    if not node_id:
        gr.Warning("삭제할 이력이 선택되지 않았습니다.")
        return gr.update(), "", [], "", "", "", ""
    try:
        db_session.query(HistoryLog).filter(HistoryLog.scenario_node_id == node_id).delete()
        db_session.query(ScenarioNode).filter(ScenarioNode.id == node_id).delete()
        db_session.commit()
        gr.Info("선택된 씬 생성 이력이 삭제되었습니다.")
        
        choices = get_scene_history_choices(project_str, target_node_id)
        next_val = choices[0][1] if choices else None
        return gr.update(choices=choices, value=next_val), "", [], "", "", "", ""
    except Exception as e:
        print("Error deleting scene history:", e)
        gr.Warning("이력 삭제 중 오류가 발생했습니다.")
        return gr.update(), "", [], "", "", "", ""

def save_scene_history(project_str, node_id, final_scene, target_node_id=None):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), final_scene, []
        
    pid = parse_project_id(project_str)
    
    if not final_scene.strip():
        gr.Warning("저장할 내용이 없습니다.")
        return gr.update(), final_scene, []
        
    try:
        old_content = ""
        node = None
        if node_id:
            node = db_session.query(ScenarioNode).filter(ScenarioNode.id == node_id).first()
            if node:
                old_content = node.content or ""
                
        # 항상 새로운 노드와 이력을 생성하여 덮어쓰지 않고 이력 관리가 되도록 함
        new_node = ScenarioNode(
            project_id=pid,
            stage="Development",
            parent_id=target_node_id if target_node_id else None,
            content=final_scene.strip(),
            commit_message="사용자 수동 편집 저장" if node else "Manually created scene"
        )
        db_session.add(new_node)
        db_session.commit()
        
        log = HistoryLog(
            scenario_node_id=new_node.id,
            action_type="MANUAL_EDIT" if node else "CREATE",
            before_content=old_content,
            after_content=final_scene.strip()
        )
        db_session.add(log)
        db_session.commit()
        db_session.expire_all()
        
        gr.Info("새로운 씬 이력으로 성공적으로 저장되었습니다.")
        saved_node_id = new_node.id
            
        choices = get_scene_history_choices(project_str, target_node_id)
        
        if old_content.strip():
            diff_output = diff_texts(old_content, final_scene.strip())
        else:
            diff_output = [(w + " ", "교정 후 (추가됨)") for w in final_scene.strip().split()] if final_scene.strip() else []
            
        return gr.update(choices=choices, value=saved_node_id), final_scene, diff_output
    except Exception as e:
        print("Error saving scene history:", e)
        gr.Warning("씬 이력 저장 중 오류가 발생했습니다.")
        return gr.update(), final_scene, []

def finalize_scene_history(project_str, node_id, target_node_id):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update()
    if not target_node_id:
        gr.Warning("선택된 시나리오 노드가 없습니다.")
        return gr.update()
    if not node_id:
        gr.Warning("확정할 이력을 선택해 주세요.")
        return gr.update()
        
    pid = parse_project_id(project_str)
    try:
        # 1. Reset all finalized flags (node_index) for this target node's history
        history_nodes = db_session.query(ScenarioNode).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage == "Development",
            ScenarioNode.parent_id == target_node_id
        ).all()
        for hn in history_nodes:
            hn.node_index = 0
            
        # 2. Set node_index = 1 for the selected one
        selected_node = db_session.query(ScenarioNode).filter(ScenarioNode.id == node_id).first()
        if selected_node:
            selected_node.node_index = 1
            db_session.commit()
            db_session.expire_all()
            gr.Info("해당 이력이 최종확정되었습니다! [★ 최종확정]")
        else:
            gr.Warning("선택된 이력을 찾을 수 없습니다.")
            
        choices = get_scene_history_choices(project_str, target_node_id)
        return gr.update(choices=choices, value=node_id)
    except Exception as e:
        print("Error finalizing scene history:", e)
        gr.Warning("최종확정 처리 중 오류가 발생했습니다.")
        return gr.update()

def save_project_only(project_str, system_prompt, overall_plot, positive_prompt, negative_prompt):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return
    pid = parse_project_id(project_str)
    try:
        proj = db_session.query(Project).filter(Project.id == pid).first()
        if proj:
            proj.system_prompt = system_prompt
            proj.overall_plot = overall_plot
            proj.positive_prompt = positive_prompt
            proj.negative_prompt = negative_prompt
            
            db_session.commit()
            db_session.expire_all()
            gr.Info("프로젝트 설정이 성공적으로 저장되었습니다.")
    except Exception as e:
        print("Error saving project settings:", e)
        gr.Warning("프로젝트 저장 중 오류가 발생했습니다.")

def refresh_target_scenario_dropdown(project_str):
    choices = get_target_scenario_node_choices(project_str)
    val = choices[0][1] if choices else None
    return gr.update(choices=choices, value=val)

def compile_full_scenario_text(project_str):
    """프로젝트의 전체 시나리오를 기-승-전-결 순서로 텍스트로 컴파일합니다."""
    if not project_str:
        return ""
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        return ""
    
    stages_ordered = [
        ("기 (起 - 도입)", "기"),
        ("승 (承 - 전개)", "승"),
        ("전 (轉 - 위기/절정)", "전"),
        ("결 (結 - 결말)", "결")
    ]
    
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"  {proj.title}")
    lines.append(f"  장르: {proj.genre or '장르 없음'}")
    lines.append(f"{'='*60}")
    lines.append("")
    
    if proj.overall_plot:
        lines.append("[전체 줄거리]")
        lines.append(proj.overall_plot.strip())
        lines.append("")
        lines.append(f"{'-'*60}")
        lines.append("")
    
    for stage_full, stage_short in stages_ordered:
        from sqlalchemy import func
        subq = db_session.query(
            ScenarioNode.node_index,
            func.max(ScenarioNode.created_at).label('max_created')
        ).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage == stage_full
        ).group_by(ScenarioNode.node_index).subquery()
        
        latest_nodes = db_session.query(ScenarioNode).join(
            subq,
            (ScenarioNode.node_index == subq.c.node_index) &
            (ScenarioNode.created_at == subq.c.max_created)
        ).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage == stage_full
        ).order_by(ScenarioNode.node_index).all()
        
        if not latest_nodes:
            continue
        
        lines.append(f"{'='*60}")
        lines.append(f"  【{stage_full}】")
        lines.append(f"{'='*60}")
        lines.append("")
        
        for node in latest_nodes:
            lines.append(f"── [{stage_short}-{node.node_index}] {node.title or '제목 없음'} ──")
            lines.append("")
            
            # Find finalized detailed scene
            detailed_scenes = db_session.query(ScenarioNode).filter(
                ScenarioNode.project_id == pid,
                ScenarioNode.stage == "Development",
                ScenarioNode.parent_id == node.id
            ).order_by(ScenarioNode.created_at.desc()).all()
            
            scene_text = ""
            if detailed_scenes:
                finalized_node = None
                for ds in detailed_scenes:
                    if ds.node_index == 1:
                        finalized_node = ds
                        break
                if not finalized_node:
                    finalized_node = detailed_scenes[0]  # fallback to latest
                scene_text = finalized_node.content or ""
            else:
                scene_text = node.content or ""
                
            lines.append(scene_text.strip())
            lines.append("")
            lines.append(f"{'-'*40}")
            lines.append("")
    
    return "\n".join(lines)

def export_scenario_as_txt(project_str):
    """전체 시나리오를 TXT 파일로 내보냅니다."""
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return None
    
    text = compile_full_scenario_text(project_str)
    if not text.strip():
        gr.Warning("내보낼 시나리오 내용이 없습니다.")
        return None
    
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    safe_title = (proj.title if proj else "scenario").replace(" ", "_").replace("/", "_")
    
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    os.makedirs(export_dir, exist_ok=True)
    filepath = os.path.join(export_dir, f"{safe_title}_전체시나리오.txt")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    
    gr.Info("전체 시나리오 TXT 파일이 생성되었습니다.")
    return filepath

def copy_scenario_to_clipboard(project_str):
    """전체 시나리오 텍스트를 반환합니다 (클립보드 복사는 JS에서 처리)."""
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return ""
    
    text = compile_full_scenario_text(project_str)
    if not text.strip():
        gr.Warning("복사할 시나리오 내용이 없습니다.")
        return ""
    
    gr.Info("전체 시나리오가 클립보드에 복사되었습니다!")
    return text

def compile_all_character_profiles(project_str):
    """프로젝트의 모든 등장인물 프로필을 텍스트로 컴파일합니다."""
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
            
        lines.append("")
        
    return "\n".join(lines)

def export_characters_as_txt(project_str):
    """전체 등장인물 프로필을 TXT 파일로 내보냅니다."""
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return None
    
    text = compile_all_character_profiles(project_str)
    if not text.strip():
        gr.Warning("내보낼 등장인물 프로필이 없습니다.")
        return None
    
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    safe_title = (proj.title if proj else "project").replace(" ", "_").replace("/", "_")
    
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    os.makedirs(export_dir, exist_ok=True)
    filepath = os.path.join(export_dir, f"{safe_title}_등장인물_프로필.txt")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    
    gr.Info("전체 등장인물 프로필 TXT 파일이 생성되었습니다.")
    return filepath

def copy_characters_to_clipboard(project_str):
    """전체 등장인물 프로필 텍스트를 반환합니다 (클립보드 복사는 JS에서 처리)."""
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return ""
    
    text = compile_all_character_profiles(project_str)
    if not text.strip():
        gr.Warning("복사할 등장인물 프로필이 없습니다.")
        return ""
    
    gr.Info("전체 등장인물 프로필이 클립보드에 복사되었습니다!")
    return text

def compile_per_scenario_novels(project_str):
    """각 세부 시나리오별로 최종확정(또는 최신) 소설 내용을 리스트로 반환합니다.
    Returns: list of dicts: [{stage, node_index, title, outline, novel_content, is_finalized}, ...]
    """
    if not project_str:
        return []
    pid = parse_project_id(project_str)
    
    stages_ordered = [
        ("기 (起 - 도입)", "기"),
        ("승 (承 - 전개)", "승"),
        ("전 (轉 - 위기/절정)", "전"),
        ("결 (結 - 결말)", "결")
    ]
    
    result = []
    for stage_full, stage_short in stages_ordered:
        from sqlalchemy import func
        subq = db_session.query(
            ScenarioNode.node_index,
            func.max(ScenarioNode.created_at).label('max_created')
        ).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage == stage_full
        ).group_by(ScenarioNode.node_index).subquery()
        
        latest_nodes = db_session.query(ScenarioNode).join(
            subq,
            (ScenarioNode.node_index == subq.c.node_index) &
            (ScenarioNode.created_at == subq.c.max_created)
        ).filter(
            ScenarioNode.project_id == pid,
            ScenarioNode.stage == stage_full
        ).order_by(ScenarioNode.node_index).all()
        
        for node in latest_nodes:
            detailed_scenes = db_session.query(ScenarioNode).filter(
                ScenarioNode.project_id == pid,
                ScenarioNode.stage == "Development",
                ScenarioNode.parent_id == node.id
            ).order_by(ScenarioNode.created_at.desc()).all()
            
            novel_content = ""
            is_finalized = False
            if detailed_scenes:
                finalized_node = None
                for ds in detailed_scenes:
                    if ds.node_index == 1:
                        finalized_node = ds
                        break
                if finalized_node:
                    novel_content = finalized_node.content or ""
                    is_finalized = True
                else:
                    novel_content = detailed_scenes[0].content or ""
                    is_finalized = False
            
            result.append({
                "stage": stage_full,
                "stage_short": stage_short,
                "node_index": node.node_index,
                "title": node.title or "제목 없음",
                "outline": node.content or "",
                "novel_content": novel_content,
                "is_finalized": is_finalized
            })
    
    return result

def refresh_novel_compilation(project_str):
    """최종 소설 취합 탭의 모든 UI 요소를 갱신합니다.
    Returns: (full_text, *per_scenario_texts) - full compiled text + individual textbox values
    """
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return [""] * 21  # 1 full + max 20 scenario slots
    
    novels = compile_per_scenario_novels(project_str)
    full_text = compile_full_scenario_text(project_str)
    
    # Build per-scenario texts (max 20 slots)
    per_texts = []
    for n in novels:
        status = "✅ 최종확정" if n["is_finalized"] else ("⚠️ 미확정 (최신본)" if n["novel_content"] else "❌ 미작성")
        header = f"[{n['stage_short']}-{n['node_index']}] {n['title']} — {status}\n{'─'*40}\n"
        per_texts.append(header + n["novel_content"])
    
    # Pad to 20 slots
    while len(per_texts) < 20:
        per_texts.append("")
    
    return [full_text] + per_texts[:20]

def preview_ai_prompts(project_str, system_prompt, overall_plot, positive_prompt, negative_prompt, scene_instruction, selected_chars, target_node_id=None):
    """AI에게 전달될 프롬프트를 미리 구성하여 반환합니다 (LLM 호출 없음)."""
    print("[DEBUG] preview_ai_prompts START")
    if not project_str:
        gr.Warning("프로젝트를 먼저 선택해주세요.")
        return gr.update(visible=True, value="프로젝트를 먼저 선택해주세요.")
    
    project_id = parse_project_id(project_str)
    print(f"[DEBUG] project_id parsed: {project_id}")
    characters = db_session.query(Character).filter(Character.project_id == project_id).all()
    print(f"[DEBUG] characters fetched: {len(characters)}")
    
    if not selected_chars:
        selected_chars = [c.name for c in characters]
    
    char_list = [c.name for c in characters if c.name in selected_chars]
    char_profiles_text = "[현재 씬 등장인물 프로필]\n"
    for char in characters:
        if char.name not in selected_chars:
            continue
        role_label = {
            'male_hero': '남자 주인공', 'female_hero': '여자 주인공',
            'male_sub': '남자 조연', 'female_sub': '여자 조연', 'other': '기타'
        }.get(char.relations, '기타')
        char_profiles_text += f"- {char.name} ({role_label}): {char.personality or ''}\n"
        if char.character_relations:
            char_profiles_text += f"  (다른 인물과의 관계: {char.character_relations})\n"
    
    print("[DEBUG] Calling router.build_context")
    context = router.build_context(project_id, scene_instruction or "", target_node_id=target_node_id)
    print("[DEBUG] router.build_context FINISHED")
    
    overall_plot_text = f"[소설 전체 줄거리]\n{overall_plot.strip()}\n" if overall_plot and overall_plot.strip() else ""
    full_context = f"{char_profiles_text}\n{overall_plot_text}\n{context}"
    
    actual_sys = system_prompt.strip() if system_prompt and system_prompt.strip() else (
        "당신은 메소드 연기자입니다. 주어진 장면에서 해당 인물의 내면 독백과 신체적 반응을 한국어로 작성하세요. "
        "불필요한 설명이나 지시문 없이 순수한 소설 본문만 출력하세요."
    )
    print("[DEBUG] system prompts constructed")
    merge_sys = system_prompt.strip() if system_prompt and system_prompt.strip() else (
        "당신은 빠른 전개와 밀도 있는 문장을 구사하는 3인칭 전지적 시점의 마스터 소설가입니다. "
        "제시된 다수 인물의 시점과 심리, 그리고 관능적 장치들을 유기적으로 통합하여, "
        "단순한 행위의 나열이 아닌 마스터피스 형태로 집필하세요. "
        "절대 프롬프트, 설명, 지시문, 주석은 출력하지 마세요. 순수한 소설 본문만 출력하세요."
    )
    
    pov_user_template = f"{full_context}\n\n[씬 지시사항]\n{scene_instruction or '(씬 지시사항이 입력되지 않았습니다)'}\n\n{{인물명}}의 시점에서 서술하세요."
    if positive_prompt and positive_prompt.strip():
        pov_user_template += f"\n\n[문체 지시 (적용)]\n{positive_prompt.strip()}"
    if negative_prompt and negative_prompt.strip():
        pov_user_template += f"\n\n[문체 지시 (금지)]\n{negative_prompt.strip()}"
    
    prompt_info = (
        f"{'='*50}\n"
        f"  STEP 1: 등장인물별 POV 분석 프롬프트\n"
        f"{'='*50}\n\n"
        f"[시스템 프롬프트]\n{actual_sys}\n\n"
        f"{'-'*50}\n\n"
        f"[대상 인물] {', '.join(char_list) if char_list else '(선택된 인물 없음)'}\n"
        f"(각 인물마다 아래 User Prompt 템플릿으로 개별 LLM 호출)\n\n"
        f"[User Prompt 템플릿]\n{pov_user_template}\n\n"
        f"{'='*50}\n"
        f"  STEP 2: 3인칭 전지적 시점 통합 집필 프롬프트\n"
        f"{'='*50}\n\n"
        f"[시스템 프롬프트]\n{merge_sys}\n\n"
        f"{'-'*50}\n\n"
        f"[User Prompt]\n"
        f"{full_context}\n\n"
        f"[등장인물별 개별 시점]\n"
        f"(STEP 1에서 생성된 각 인물의 POV 결과가 여기에 삽입됩니다)\n\n"
        f"위 시점들을 통합하여 하나의 완성된 소설 씬으로 작성하세요."
    )
    if positive_prompt and positive_prompt.strip():
        prompt_info += f"\n\n[문체 지시 (적용)]\n{positive_prompt.strip()}"
    if negative_prompt and negative_prompt.strip():
        prompt_info += f"\n\n[문체 지시 (금지)]\n{negative_prompt.strip()}"
    
    opt_prompt = optimize_prompt(prompt_info)
    return gr.update(visible=True, value=prompt_info), gr.update(visible=True, value=opt_prompt)

def preview_scenario_regen_prompts(project_str, stage, node_index, title, user_regen_prompt):
    """시나리오 노드 AI 재구성 시 전달될 프롬프트를 미리 구성하여 반환합니다 (LLM 호출 없음)."""
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(visible=True, value="선택된 프로젝트가 없습니다.")
    if node_index is None:
        gr.Warning("선택된 시나리오 노드가 없습니다.")
        return gr.update(visible=True, value="선택된 시나리오 노드가 없습니다.")
        
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        gr.Warning("프로젝트를 찾을 수 없습니다.")
        return gr.update(visible=True, value="프로젝트를 찾을 수 없습니다.")
        
    characters_str = ""
    characters = db_session.query(Character).filter(Character.project_id == pid).all()
    for char in characters:
        relation_kor = "남자 주인공" if char.relations == "male_hero" else ("여자 주인공" if char.relations == "female_hero" else "조연")
        characters_str += f"- {char.name} ({relation_kor}): {char.personality or ''}\n"
        
    overall_plot = proj.overall_plot or "줄거리 없음"
    
    system_instruction = (
        "You are an expert novel planner. "
        "Your task is to write a detailed scene description for a single scenario node. "
        "Write strictly in Korean, capturing the tone and characters."
    )
    
    user_prompt = (
        f"소설 제목: {proj.title}\n"
        f"장르: {proj.genre or '드라마'}\n"
        f"전체 소설 줄거리:\n{overall_plot}\n\n"
        f"등장인물 정보:\n{characters_str}\n\n"
        f"현재 진행 단계: {stage}\n"
        f"노드 순번: {node_index}번째 에피소드\n"
        f"씬 제목: {title or '제목 없음'}\n\n"
    )
    
    if user_regen_prompt and user_regen_prompt.strip():
        user_prompt += (
            f"[사용자 지시사항]\n{user_regen_prompt.strip()}\n\n"
            f"위 지시사항을 반드시 반영하여, 이 씬에 대한 상세한 서사 개요와 플롯 가이드를 한국어로 작성하세요. "
            f"캐릭터 역학, 긴장감, 서사 전개에 집중하세요."
        )
    else:
        user_prompt += (
            f"Please write a detailed narrative outline and plot guidance for this specific scene (about 4-5 sentences in Korean). "
            f"Focus on character dynamics, tension, and narrative progression."
        )
        
    prompt_info = (
        f"{'═'*50}\n"
        f"  📋 시나리오 노드 AI 재구성 프롬프트 미리보기\n"
        f"{'═'*50}\n\n"
        f"【시스템 프롬프트 (System Instruction)】\n{system_instruction}\n\n"
        f"{'─'*50}\n\n"
        f"【사용자 프롬프트 (User Prompt)】\n{user_prompt}\n"
    )
    return gr.update(visible=True, value=prompt_info)

def preview_overall_plot_prompt(project_str, user_idea):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(visible=True, value="선택된 프로젝트가 없습니다.")
    if not user_idea or not user_idea.strip():
        gr.Warning("줄거리 아이디어를 입력해 주세요.")
        return gr.update(visible=True, value="줄거리 아이디어를 입력해 주세요.")
        
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        gr.Warning("프로젝트를 찾을 수 없습니다.")
        return gr.update(visible=True, value="프로젝트를 찾을 수 없습니다.")
        
    system_instruction = (
        "You are an expert creative writer and story planner.\n"
        "Your task is to generate a compelling, detailed overall plot (synopsis) for a novel based on the user's idea, title, and genre.\n"
        "Write the plot in Korean, consisting of 3-4 dense, detailed sentences.\n"
        "Make it engaging, professional, and descriptive, matching the genre.\n"
        "If the genre is erotic/romance, make it appropriately sensual and emotionally tense.\n"
        "Output only the final plot, with no explanations, introduction, or formatting labels."
    )
    
    user_prompt = (
        f"소설 제목: {proj.title}\n"
        f"장르: {proj.genre or '드라마'}\n"
        f"기본 아이디어 / 키워드: {user_idea.strip()}\n\n"
        f"Please write a detailed, high-quality overall plot (synopsis) in Korean based on the details above."
    )
    
    prompt_info = (
        f"{'═'*50}\n"
        f"  📋 전체 소설 줄거리 자동 생성 프롬프트 미리보기\n"
        f"{'═'*50}\n\n"
        f"【시스템 프롬프트 (System Instruction)】\n{system_instruction}\n\n"
        f"{'─'*50}\n\n"
        f"【사용자 프롬프트 (User Prompt)】\n{user_prompt}\n"
    )
    return gr.update(visible=True, value=prompt_info)

def generate_overall_plot(project_str, user_idea, system_prompt_val, positive_prompt_val, negative_prompt_val):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(), gr.update()
    if not user_idea or not user_idea.strip():
        gr.Warning("줄거리 아이디어를 입력해 주세요.")
        return gr.update(), gr.update()
        
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        gr.Warning("프로젝트를 찾을 수 없습니다.")
        return gr.update(), gr.update()
        
    gr.Info("인공지능이 소설 줄거리를 생성하는 중입니다...")
    
    system_instruction = (
        "You are an expert creative writer and story planner.\n"
        "Your task is to generate a compelling, detailed overall plot (synopsis) for a novel based on the user's idea, title, and genre.\n"
        "Write the plot in Korean, consisting of 3-4 dense, detailed sentences.\n"
        "Make it engaging, professional, and descriptive, matching the genre.\n"
        "If the genre is erotic/romance, make it appropriately sensual and emotionally tense.\n"
        "Output only the final plot, with no explanations, introduction, or formatting labels."
    )
    
    user_prompt = (
        f"소설 제목: {proj.title}\n"
        f"장르: {proj.genre or '드라마'}\n"
        f"기본 아이디어 / 키워드: {user_idea.strip()}\n\n"
        f"Please write a detailed, high-quality overall plot (synopsis) in Korean based on the details above."
    )
    
    try:
        generated_plot = llama_client.send_chat_completion(
            system_prompt=system_instruction,
            user_prompt=user_prompt,
            temperature=0.8
        )
        if not generated_plot or not isinstance(generated_plot, str):
            generated_plot = "줄거리 생성에 실패했습니다. 다시 시도해 주세요."
            return gr.update(value=generated_plot), gr.update()
        else:
            generated_plot = generated_plot.strip()
    except Exception as e:
        print("Error during overall plot generation:", e)
        generated_plot = f"에러 발생: {e}"
        return gr.update(value=generated_plot), gr.update()
        
    # Save the new version record to PromptVersion
    idea_snippet = user_idea.strip()
    if len(idea_snippet) > 15:
        idea_snippet = idea_snippet[:15] + "..."
    version_name = f"[AI 생성] {idea_snippet}"
    
    try:
        new_ver = PromptVersion(
            project_id=pid,
            version_name=version_name,
            system_prompt=system_prompt_val,
            overall_plot=generated_plot,
            positive_prompt=positive_prompt_val,
            negative_prompt=negative_prompt_val
        )
        db_session.add(new_ver)
        db_session.commit()
        gr.Info(f"새로운 이력 버전 '{version_name}'(으)로 자동 저장되었습니다.")
    except Exception as e:
        print("Error saving prompt version on AI generation:", e)
        
    updated_choices = get_prompt_version_choices(project_str)
    return (
        gr.update(value=generated_plot),
        gr.update(choices=updated_choices, value=updated_choices[0] if updated_choices else None)
    )

def preview_character_gen_prompt(project_str):
    if not project_str:
        gr.Warning("선택된 프로젝트가 없습니다.")
        return gr.update(visible=True, value="선택된 프로젝트가 없습니다.")
        
    pid = parse_project_id(project_str)
    proj = db_session.query(Project).filter(Project.id == pid).first()
    if not proj:
        gr.Warning("프로젝트를 찾을 수 없습니다.")
        return gr.update(visible=True, value="프로젝트를 찾을 수 없습니다.")
        
    system_instruction = (
        "You are an expert novel planner. "
        "Your task is to analyze the overall plot and genre of a novel, and design compelling character profiles and relationships. "
        "You must generate exactly: "
        "1. One Male Hero (남자 주인공): name, personality (가면), background (결핍), character_relations (관계 역학), speech_style (말투). "
        "2. One Female Hero (여자 주인공): name, personality, background, character_relations, speech_style. "
        "3. One Male Supporting character (남자 조연): name, personality, background, character_relations, speech_style. "
        "4. One Female Supporting character (여자 조연): name, personality, background, character_relations, speech_style. "
        "5. One Other character (기타): name, personality, background, character_relations, speech_style. "
        "You must output the result strictly in JSON format. Do not write any markdown outside the JSON."
    )
    
    user_prompt = (
        f"소설 제목: {proj.title}\n"
        f"장르: {proj.genre or '드라마'}\n"
        f"전체 소설 줄거리:\n{proj.overall_plot or '줄거리 없음'}\n\n"
        f"Please design the characters and their relationships according to the story. "
        f"The output must be a valid JSON object with the following schema:\n"
        f"{{\n"
        f"  \"male_hero\": {{\n"
        f"    \"name\": \"이름/나이/지위 (예: 강이현 / 34세 / 본부장)\",\n"
        f"    \"personality\": \"겉으로 드러나는 가면 (표면적 성격)\",\n"
        f"    \"background\": \"숨겨진 결핍 및 본능\",\n"
        f"    \"character_relations\": \"심층 역학 (표면적 역학 vs 무의식적 긴장 등)\",\n"
        f"    \"speech_style\": \"공적인 공간 vs 사적인 공간 호칭과 말투 변화\"\n"
        f"  }},\n"
        f"  \"female_hero\": {{\n"
        f"    \"name\": \"...\",\n"
        f"    \"personality\": \"...\",\n"
        f"    \"background\": \"...\",\n"
        f"    \"character_relations\": \"...\",\n"
        f"    \"speech_style\": \"...\"\n"
        f"  }},\n"
        f"  \"male_sub\": {{\n"
        f"    \"name\": \"...\",\n"
        f"    \"personality\": \"...\",\n"
        f"    \"background\": \"...\",\n"
        f"    \"character_relations\": \"...\",\n"
        f"    \"speech_style\": \"...\"\n"
        f"  }},\n"
        f"  \"female_sub\": {{\n"
        f"    \"name\": \"...\",\n"
        f"    \"personality\": \"...\",\n"
        f"    \"background\": \"...\",\n"
        f"    \"character_relations\": \"...\",\n"
        f"    \"speech_style\": \"...\"\n"
        f"  }},\n"
        f"  \"other\": {{\n"
        f"    \"name\": \"...\",\n"
        f"    \"personality\": \"...\",\n"
        f"    \"background\": \"...\",\n"
        f"    \"character_relations\": \"...\",\n"
        f"    \"speech_style\": \"...\"\n"
        f"  }}\n"
        f"}}\n"
        f"Write all character details strictly in Korean, aligning with the story tone."
    )
    
    prompt_info = (
        f"{'═'*50}\n"
        f"  📋 AI 등장인물 자동 생성 프롬프트 미리보기\n"
        f"{'═'*50}\n\n"
        f"【시스템 프롬프트 (System Instruction)】\n{system_instruction}\n\n"
        f"{'─'*50}\n\n"
        f"【사용자 프롬프트 (User Prompt)】\n{user_prompt}\n"
    )
    return gr.update(visible=True, value=prompt_info)

import threading

_session_ctx = threading.local()

# Thread-safe database session management wrapper
def with_db_session(fn):
    if inspect.isgeneratorfunction(fn):
        @functools.wraps(fn)
        def generator_wrapper(*args, **kwargs):
            if not hasattr(_session_ctx, 'depth'):
                _session_ctx.depth = 0
            _session_ctx.depth += 1
            is_outermost = (_session_ctx.depth == 1)
            try:
                if is_outermost:
                    db_session.remove()
                gen = fn(*args, **kwargs)
                for item in gen:
                    yield item
            finally:
                _session_ctx.depth -= 1
                if is_outermost:
                    db_session.remove()
        return generator_wrapper
    else:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not hasattr(_session_ctx, 'depth'):
                _session_ctx.depth = 0
            _session_ctx.depth += 1
            is_outermost = (_session_ctx.depth == 1)
            try:
                if is_outermost:
                    db_session.remove()
                return fn(*args, **kwargs)
            finally:
                _session_ctx.depth -= 1
                if is_outermost:
                    db_session.remove()
        return wrapper

# Apply decorator to database functions dynamically to prevent connection leak/locks
funcs_to_wrap = [
    get_project_list, load_project_character_data, get_node_choices_for_stage,
    build_commit_tree_choices, get_character_dropdown_choices, get_character_names,
    update_active_characters_checkbox, on_character_select_change, save_or_update_character,
    add_new_blank_character, delete_selected_character, load_project_details,
    save_project_settings, create_new_project, delete_project,
    get_erotic_version_choices, save_erotic_version, load_erotic_version, delete_erotic_version, auto_save_erotic_version,
    get_prompt_version_choices, save_prompt_version, load_prompt_version,
    delete_prompt_version, edit_prompt_version, refine_scene_with_prompt,
    get_character_version_choices, save_character_version, load_character_version,
    delete_character_version, edit_character_version, get_character_version_choices_update,
    generate_scene, verify_generated_scene, api_generate_scenario_nodes,
    on_stage_change, on_node_change, on_ver_change, add_scenario_node,
    delete_scenario_node, commit_new_scenario_version, save_current_scenario_version,
    delete_scenario_version, regenerate_scenario_node, get_scene_history_choices,
    api_generate_characters, update_scene_history_dropdown, get_target_scenario_node_choices,
    load_target_scenario_content, load_scene_history, delete_scene_history,
    save_scene_history, finalize_scene_history, on_target_scenario_change, save_project_only, refresh_target_scenario_dropdown,
    compile_full_scenario_text, export_scenario_as_txt, copy_scenario_to_clipboard,
    compile_per_scenario_novels, refresh_novel_compilation,
    preview_ai_prompts, preview_scenario_regen_prompts,
    preview_overall_plot_prompt, generate_overall_plot,
    preview_character_gen_prompt, on_page_load
]

for f in funcs_to_wrap:
    globals()[f.__name__] = with_db_session(f)

def update_radio_title_on_type(project_str, stage, node_index, title):
    if not project_str or not stage or node_index is None:
        return gr.update()
    pid = parse_project_id(project_str)
    choices = get_node_choices_for_stage(pid, stage)
    new_choices = []
    for label, val in choices:
        if val == node_index:
            new_title = title.strip() if title and title.strip() else f"제목 없음"
            new_choices.append((f"[{val}] {new_title}", val))
        else:
            new_choices.append((label, val))
    return gr.update(choices=new_choices, value=node_index)

def build_ui():
    with gr.Blocks(theme=gr.themes.Soft(primary_hue="purple", secondary_hue="indigo", neutral_hue="slate"), title="Abyss Writer") as app:
        gr.Markdown("# 🖋️ Abyss Writer (전문가용 소설 창작 시스템)")
        
        # Load initial project data
        project_choices = get_project_list()
        initial_project = project_choices[0] if project_choices else None
        (
            init_char_name, init_char_role, 
            init_char_personality, init_char_background, init_char_relations, init_char_speech_style,
            init_char_dropdown_update,
            init_dummy,
            init_sys_prompt, init_overall_plot,
            init_pos_prompt, init_neg_prompt,
            _, _, _, _,
            init_scen_content,
            init_scen_title,
            _,
            _,
            init_active_chars_update,
            init_erotic_ver_update
        ) = load_project_details(initial_project)
        
        # Global Project Selector at the top
        with gr.Group():
            gr.Markdown("### 📂 글로벌 프로젝트 관리")
            with gr.Row():
                project_dropdown = gr.Dropdown(
                    label="프로젝트 선택", 
                    choices=project_choices, 
                    value=initial_project,
                    interactive=True,
                    scale=3
                )
                btn_load_project = gr.Button("📂 불러오기", variant="secondary", scale=1)
                btn_save_project = gr.Button("💾 저장하기", variant="secondary", scale=1)
                btn_delete_project = gr.Button("🗑️ 삭제", variant="stop", scale=1)
        
            gr.Markdown("#### ➕ 새 프로젝트 생성")
            with gr.Row():
                new_title = gr.Textbox(label="프로젝트 제목", placeholder="예: 심연의 메아리", scale=2)
                new_genre = gr.Textbox(label="장르", placeholder="예: SF 스릴러", scale=2)
                btn_create_project = gr.Button("생성하기", variant="primary", scale=1)
                    
        # Initialize Scenario tab data
        initial_pid = parse_project_id(initial_project)
        init_stages = ["기 (起 - 도입)", "승 (承 - 전개)", "전 (轉 - 위기/절정)", "결 (結 - 결말)"]
        init_node_choices = get_node_choices_for_stage(initial_pid, init_stages[0])
        init_node_val = init_node_choices[0][1] if init_node_choices else None
        init_scen_ver_choices = build_commit_tree_choices(initial_pid, init_stages[0], init_node_val)
        init_scen_ver_val = max(init_scen_ver_choices, key=lambda x: x[1])[1] if init_scen_ver_choices else None

        # Initialize Target scenario node choices
        init_target_scenario_choices = get_target_scenario_node_choices(initial_project)
        init_target_scenario_val = init_target_scenario_choices[0][1] if init_target_scenario_choices else None

        # Initialize Erotic Scenario character choices
        init_char_choices = get_character_dropdown_choices(initial_project)
        init_female_val = None
        init_male_val = None
        
        # Initialize Character Version choices
        init_first_char_id = init_char_choices[0][1] if init_char_choices else None
        init_char_ver_choices = get_character_version_choices(init_first_char_id)
        init_char_ver_val = init_char_ver_choices[0] if init_char_ver_choices else None
        if initial_project:
            try:
                init_pid = parse_project_id(initial_project)
                init_chars = db_session.query(Character).filter(Character.project_id == init_pid).all()
                for c in init_chars:
                    if c.relations == "female_hero":
                        init_female_val = c.id
                    elif c.relations == "male_hero":
                        init_male_val = c.id
            except Exception as e:
                print("Error loading initial erotic character values:", e)

        # Initialize Scene generation history data
        init_scene_history_choices = get_scene_history_choices(initial_project, init_target_scenario_val)
        init_scene_history_val = init_scene_history_choices[0][1] if init_scene_history_choices else None

        # Initialize Erotic Scenario Version choices
        init_erotic_ver_choices = get_erotic_version_choices(initial_project)
        init_erotic_ver_val = init_erotic_ver_choices[0][1] if init_erotic_ver_choices else None

        # Main Tabs
        with gr.Tabs():


            with gr.Tab("⚙️ 전체 설정 및 프롬프트"):
                with gr.Row():
                    with gr.Column(scale=1):
                        system_prompt = gr.Textbox(
                            label="시스템 프롬프트 (System Prompt)", 
                            placeholder="예: 당신은 미스터리 스릴러 전문 작가입니다. 냉철하고 긴장감 넘치는 어조로 작성해 주세요.",
                            value=init_sys_prompt,
                            lines=4
                        )
                        overall_plot = gr.Textbox(
                            label="전체 소설 줄거리 (Overall Novel Plot)", 
                            placeholder="예: 비밀 조직의 요원인 카이토가 기억을 잃은 채 평범한 미사키를 만나고, 서로의 정체를 알아가며 충돌한다.",
                            value=init_overall_plot,
                            lines=8
                        )
                    with gr.Column(scale=1):
                        positive_prompt = gr.Textbox(
                            label="Positive 스타일 프롬프트 (Style Directive)", 
                            placeholder="예: 시각적인 묘사 극대화, 빠른 템포의 대화, 은유적 표현 사용",
                            value=init_pos_prompt,
                            lines=4
                        )
                        negative_prompt = gr.Textbox(
                            label="Negative 스타일 프롬프트 (Avoid Directive)", 
                            placeholder="예: 상투적인 감정 표현 금지, 지루한 설명조 생략, 클리셰 금지",
                            value=init_neg_prompt,
                            lines=4
                        )
                
                with gr.Accordion("🪄 AI 전체 줄거리 자동 생성", open=False):
                    with gr.Row():
                        with gr.Column(scale=2):
                            plot_idea_input = gr.Textbox(
                                label="줄거리 아이디어 / 키워드 입력",
                                placeholder="예: 30대 중반 미망인과 20대 초반 하숙생의 은밀하고 관능적인 로맨스",
                                lines=3
                            )
                            with gr.Row():
                                btn_preview_plot_prompt = gr.Button("🔬 AI 실제 사용 프롬프트 확인", variant="secondary")
                                btn_generate_plot = gr.Button("✨ AI 줄거리 생성", variant="primary")
                        with gr.Column(scale=3):
                            plot_prompt_preview = gr.Textbox(
                                label="AI 줄거리 생성 프롬프트 미리보기",
                                lines=6,
                                interactive=False,
                                visible=False
                            )
                
                btn_save_settings = gr.Button("💾 현재 설정을 프로젝트 기본값으로 저장", variant="secondary")

                gr.Markdown("---")
                
                with gr.Group():
                    gr.Markdown("### 📜 프롬프트 버전 관리 (이력 관리)")
                    with gr.Row():
                        with gr.Column(scale=2):
                            ver_name_input = gr.Textbox(
                                label="저장할 버전 이름 / 변경 사항 설명",
                                placeholder="예: SF 서사 보강 버전, 감정선 묘사 강화"
                            )
                            btn_save_version = gr.Button("💾 현재 설정을 새 버전으로 저장", variant="primary")
                        with gr.Column(scale=3):
                            init_ver_choices = get_prompt_version_choices(initial_project)
                            init_ver_val = init_ver_choices[0] if init_ver_choices else None
                            
                            version_dropdown = gr.Dropdown(
                                label="이력 버전 선택",
                                choices=init_ver_choices,
                                value=init_ver_val,
                                interactive=True,
                                allow_custom_value=True
                            )
                            with gr.Row():
                                btn_load_version = gr.Button("📂 선택 버전 불러오기", variant="secondary")
                                btn_delete_version = gr.Button("🗑️ 선택 버전 삭제", variant="stop")
                            with gr.Row():
                                new_ver_name_input = gr.Textbox(
                                    label="변경할 버전 이름",
                                    placeholder="예: 이름 수정안"
                                )
                                btn_edit_version = gr.Button("✍️ 버전 이름 수정", variant="secondary")

            with gr.Tab("👥 캐릭터 설정"):
                gr.Markdown("### 👥 등장인물 프로필 설정")
                with gr.Row():
                    char_dropdown = gr.Dropdown(
                        label="등장인물 선택",
                        choices=get_character_dropdown_choices(initial_project),
                        value=init_char_dropdown_update.get("value") if isinstance(init_char_dropdown_update, dict) else None,
                        interactive=True,
                        allow_custom_value=True,
                        scale=3
                    )
                    btn_add_char = gr.Button("➕ 인물 추가", variant="secondary", scale=1)
                    btn_delete_char = gr.Button("🗑️ 인물 삭제", variant="stop", scale=1)
                    with gr.Row():
                        btn_generate_characters = gr.Button("🪄 AI 등장인물 프로필 자동 생성", variant="secondary")
                        btn_save_character_detail = gr.Button("💾 등장인물 정보 저장", variant="primary")
                    
                    with gr.Accordion("🔬 AI 등장인물 생성 프롬프트 확인", open=False):
                        btn_preview_char_prompt = gr.Button("🔬 AI 실제 사용 프롬프트 확인", variant="secondary")
                        char_prompt_preview = gr.Textbox(
                            label="AI 등장인물 생성 프롬프트 미리보기",
                            lines=8,
                            interactive=False,
                            visible=False
                        )
                        
                    with gr.Row():
                        btn_export_chars_txt = gr.Button("📥 전체 프로필 TXT 다운로드", variant="secondary")
                    btn_copy_chars_clipboard = gr.Button("📋 전체 프로필 클립보드 복사", variant="secondary")
                char_download_file = gr.File(label="다운로드 파일", visible=False)
                char_clipboard_hidden = gr.Textbox(visible=False, elem_id="char_clipboard_hidden")
                
                with gr.Group():
                    char_name = gr.Textbox(label="인물 A (이름/나이/지위)", placeholder="예: 강이현 / 34세 / 대기업 전략기획본부장", value=init_char_name)
                    char_role = gr.Dropdown(
                        label="역할 및 분류",
                        choices=[
                            ("남자 주인공", "male_hero"),
                            ("여자 주인공", "female_hero"),
                            ("남자 조연", "male_sub"),
                            ("여자 조연", "female_sub"),
                            ("기타", "other")
                        ],
                        value=init_char_role or "other",
                        interactive=True
                    )
                    char_personality = gr.Textbox(label="겉으로 드러나는 가면 (표면적 성격)", placeholder="예: 완벽주의, 냉혈함", value=init_char_personality, lines=2)
                    char_background = gr.Textbox(label="숨겨진 결핍 및 본능 (심층 심리)", placeholder="예: 인정욕구, 타인에 대한 뿌리 깊은 불신", value=init_char_background, lines=3)
                    char_relations = gr.Textbox(label="다른 등장인물간의 관계의 심층 역학 설정 가이드", placeholder="표면적 역학 vs 무의식적 긴장, 결핍의 상호작용, 결정적 균열의 시점", value=init_char_relations, lines=4)
                    char_speech_style = gr.Textbox(label="언어적 발현: 호칭과 말투 구체화 요구사항", placeholder="공적인 공간 (가면을 쓴 상태) vs 사적인 공간 (경계가 허물어지는 순간)에서의 호칭 및 대화 양식", value=init_char_speech_style, lines=4)
                    char_dummy = gr.State()

                gr.Markdown("---")
                with gr.Group():
                    gr.Markdown("### 📜 캐릭터 프로필 버전 관리 (이력 관리)")
                    with gr.Row():
                        with gr.Column(scale=2):
                            char_ver_name_input = gr.Textbox(
                                label="저장할 버전 이름 / 변경 사항 설명",
                                placeholder="예: 초안, 외양 상세화, 2차 수정안"
                            )
                            btn_save_char_version = gr.Button("💾 현재 설정을 새 버전으로 저장", variant="primary")
                        with gr.Column(scale=3):
                            char_version_dropdown = gr.Dropdown(
                                label="이력 버전 선택",
                                choices=init_char_ver_choices,
                                value=init_char_ver_val,
                                interactive=True,
                                allow_custom_value=True
                            )
                            with gr.Row():
                                btn_load_char_version = gr.Button("📂 선택 버전 불러오기", variant="secondary")
                                btn_delete_char_version = gr.Button("🗑️ 선택 버전 삭제", variant="stop")
                            with gr.Row():
                                new_char_ver_name_input = gr.Textbox(
                                    label="변경할 버전 이름",
                                    placeholder="예: 이름 수정안"
                                )
                                btn_edit_char_version = gr.Button("✍️ 버전 이름 수정", variant="secondary")

            with gr.Tab("🗺️ 시나리오 구성"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 🪄 시나리오 대량 생성")
                        gr.Markdown("프로젝트의 전체 줄거리와 등장인물 프로필을 바탕으로, 기승전결(起承轉結)의 4단계로 각 단계별 4~5개의 세부 시나리오 노드를 자동으로 구성합니다.")
                        btn_auto_scen_gen = gr.Button("🪄 기승전결 시나리오 자동 생성", variant="primary")
                        
                        gr.Markdown("---")
                        gr.Markdown("### 🔍 시나리오 탐색")
                        scen_stage_dropdown = gr.Dropdown(
                            label="1. 플롯 단계 선택 (Stage)",
                            choices=init_stages,
                            value=init_stages[0],
                            interactive=True
                        )
                        scen_node_dropdown = gr.Radio(
                            label="2. 세부 시나리오 노드 선택",
                            choices=init_node_choices,
                            value=init_node_val,
                            interactive=True
                        )
                        with gr.Group():
                            gr.Markdown("**노드 삽입 위치**")
                            node_insert_position = gr.Radio(
                                choices=[
                                    ("현재 노드 앞에", "before"),
                                    ("현재 노드 뒤에", "after"),
                                    ("맨 끝에", "end")
                                ],
                                value="after",
                                label="",
                                interactive=True
                            )
                        with gr.Row():
                            btn_add_node = gr.Button("➕ 노드 추가", variant="secondary", scale=1)
                            btn_delete_node = gr.Button("🗑️ 노드 삭제", variant="stop", scale=1)
                        scen_ver_dropdown = gr.Dropdown(
                            label="3. 이력 버전 트리 선택 (Git Commits)",
                            choices=init_scen_ver_choices,
                            value=init_scen_ver_val,
                            interactive=True,
                            allow_custom_value=True
                        )
                        
                    with gr.Column(scale=2):
                        gr.Markdown("### ✍️ 시나리오 상세 편집 및 버전 관리")
                        scen_title_box = gr.Textbox(
                            label="시나리오 제목",
                            placeholder="예: 기-1: 카이토의 조력자 등장",
                            value=init_scen_title
                        )
                        scen_content_box = gr.Textbox(
                            label="시나리오 상세 내용 / 지시문",
                            lines=12,
                            placeholder="여기에 시나리오 내용을 직접 작성하거나 편집하세요.",
                            value=init_scen_content
                        )
                        scen_regen_prompt = gr.Textbox(
                            label="AI 재구성 지시사항 (선택 입력)",
                            placeholder="예: 남주의 갈등을 더 부각해줘 / NTR 심리묘사를 강화해줘 / 전개 속도를 더 빠르게",
                            lines=2
                        )
                        with gr.Row():
                            btn_regen_node = gr.Button("🪄 이 노드만 AI 자동 재구성", variant="secondary")
                            btn_preview_regen_prompt = gr.Button("🔬 AI 실제 사용 프롬프트 확인", variant="secondary")
                            
                        scen_used_prompts = gr.Textbox(
                            label="AI에게 전달될 프롬프트 전문 (미리보기)",
                            lines=15,
                            interactive=False,
                            visible=False
                        )
                        
                        with gr.Row():
                            btn_save_scen_ver = gr.Button("💾 현재 버전에 바로 저장", variant="primary")
                            btn_delete_ver = gr.Button("🗑️ 선택한 버전 삭제", variant="stop")
                            
                        gr.Markdown("---")
                        gr.Markdown("### 💾 새로운 버전으로 커밋")
                        scen_commit_msg = gr.Textbox(
                            label="커밋 메시지 (변경 사항에 대한 간략한 기록)",
                            placeholder="예: 주인공 대사 톤 다듬음, SF 설정 추가"
                        )
                        btn_commit_ver = gr.Button("💾 현재 변경사항을 새 버전으로 커밋", variant="primary")
                        
                        gr.Markdown("---")
                        gr.Markdown("### 📥 전체 시나리오 내보내기")
                        with gr.Row():
                            btn_export_txt = gr.Button("📥 전체 시나리오 TXT 다운로드", variant="secondary")
                            btn_copy_clipboard = gr.Button("📋 전체 시나리오 클립보드 복사", variant="secondary")
                        scenario_download_file = gr.File(label="다운로드 파일", visible=False)
                        scenario_clipboard_hidden = gr.Textbox(visible=False, elem_id="scenario_clipboard_hidden")

            with gr.Tab("🎬 씬 생성기"):
                with gr.Row():
                    with gr.Column():
                        with gr.Group():
                            gr.Markdown("### 👥 이번 씬 출연 인물 선택")
                            active_characters = gr.CheckboxGroup(
                                label="출연시킬 등장인물 체크 (선택한 인물만 시점 분석 수행)",
                                choices=get_character_names(initial_project),
                                value=get_main_character_names(initial_project),
                                interactive=True
                            )
                        with gr.Group():
                            gr.Markdown("### 🗺️ 시나리오 구성 연동")
                            with gr.Row():
                                target_scenario_dropdown = gr.Dropdown(
                                    label="가져올 시나리오 노드 선택",
                                    choices=init_target_scenario_choices,
                                    value=init_target_scenario_val,
                                    interactive=True,
                                    allow_custom_value=True,
                                    scale=3
                                )
                                btn_load_scen_node_gen = gr.Button("🎯 시나리오 불러오기", variant="secondary", scale=1)
                                
                        instruction = gr.Textbox(label="씬 지시사항 (상황/사건 묘사)", lines=5, placeholder="예: 카이토와 미사키가 빗속에서 대치하는 장면")
                        btn_generate = gr.Button("씬 생성하기 (다중 시점)", variant="primary")
                        

                        
                    with gr.Column():
                        out_final_scene = gr.Textbox(label="최종 생성된 씬 (문체 교정 완료)", lines=45)
                        with gr.Row():
                            btn_save_scene = gr.Button("💾 현재 씬 바로 저장", variant="primary", scale=2)
                            btn_finalize_scene = gr.Button("✔️ 최종확정", variant="primary", scale=2)
                            btn_preview_prompts = gr.Button("🔬 AI 실제 사용 프롬프트 확인", variant="secondary", scale=3)
                            
                        gr.Markdown("---")
                        gr.Markdown("### 📜 씬 편집 이력 (버전) 관리")
                        scene_history_dropdown = gr.Dropdown(
                            label="이전 생성 및 저장된 이력 선택",
                            choices=init_scene_history_choices,
                            value=init_scene_history_val,
                            interactive=True,
                            allow_custom_value=True
                        )
                        with gr.Row():
                            btn_load_scene_history = gr.Button("📂 이 내용으로 불러오기", variant="secondary")
                            btn_delete_scene_history = gr.Button("🗑️ 이력 삭제", variant="stop")
                            
                        out_used_prompts = gr.Textbox(
                            label="AI에게 전달될 프롬프트 전문 (미리보기)",
                            lines=20,
                            interactive=False,
                            visible=False
                        )
                        out_optimized_prompts = gr.Textbox(
                            label="최적화 완료된 실제 전송 프롬프트 (미리보기)",
                            lines=20,
                            interactive=False,
                            visible=False
                        )
                        
                        with gr.Accordion("✍️ 사용자 프롬프트로 씬 수정", open=True):
                            gr.Markdown("위에서 생성된 씬 내용을 직접 수정하거나, 아래에 지시를 입력하여 AI가 다시 다듬도록 할 수 있습니다.")
                            user_refine_prompt = gr.Textbox(
                                label="수정 지시 프롬프트",
                                placeholder="예: 렌의 감정을 더 구체적으로 묘사해줘 / 대화 부분을 늘려줘 / 마지막 단락을 더 극적으로 수정해줘",
                                lines=4
                            )
                            btn_refine_scene = gr.Button("🔄 프롬프트 실행 (씬 수정)", variant="primary")
                        
                        with gr.Accordion("🔍 생성된 씬 논리/팩트 교차 검증 (속도 저하 요인, 필요시 실행)", open=True):
                            btn_verify_scene = gr.Button("🔎 정합성 & 팩트 검증 실행 (LLM 분석)", variant="secondary")
                            out_tracker = gr.Textbox(label="타임라인 및 논리 정합성 검증 결과", value="🔍 검증 실행 버튼을 누르면 분석이 시작됩니다.")
                            out_facts = gr.Textbox(label="팩트 vs 허구 교차 검증 (법리/기술)", value="🔍 검증 실행 버튼을 누르면 분석이 시작됩니다.")
                        
                with gr.Row():
                    gr.Markdown("### 🔍 교정 전 vs 교정 후 비교 (문체 및 리듬 필터 차이)")
                with gr.Row():
                    out_diff = gr.HighlightedText(
                        label="차이 비교 뷰어",
                        combine_adjacent=True,
                        color_map={"교정 전 (삭제됨)": "red", "교정 후 (추가됨)": "green"},
                        show_legend=True,
                        elem_id="out_diff_full_width"
                    )
                    
            with gr.Tab("🔥 관능 시나리오 분화"):
                gr.Markdown(
                    """
                    # 🔥 관능적 심리 시나리오 분화 발전기
                    *인물의 정숙한 외면과 은밀한 욕망의 모순을 탐구하고, 관능적 긴장감이 극대화된 상황을 다각도로 분화하여 집필합니다.*
                    """
                )
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 🎭 캐릭터 및 상황 설정")
                        
                        btn_autofill_chars = gr.Button("📂 현재 프로젝트 캐릭터 정보 가져오기", variant="secondary")
                        
                        with gr.Row():
                            female_char_select = gr.Dropdown(
                                label="여성 캐릭터 선택",
                                choices=init_char_choices,
                                value=init_female_val,
                                interactive=True,
                                allow_custom_value=True
                            )
                            male_char_select = gr.Dropdown(
                                label="남성 캐릭터 선택",
                                choices=init_char_choices,
                                value=init_male_val,
                                interactive=True,
                                allow_custom_value=True
                            )
                        
                        btn_ai_autofill_erotic_settings = gr.Button("🪄 AI 캐릭터 맞춤 설정 자동 완성", variant="primary")
                        
                        female_desc_input = gr.Textbox(
                            label="여성 캐릭터 설정 (예: 스미래)",
                            placeholder="예: 30대 중반 미망인, 겉으로는 정숙하나 내면에는 강렬한 성적 결핍과 탐욕이 있음...",
                            value="스미래: [30대 중반 미망인, 겉으로는 정숙하나 내면에는 강렬한 성적 결핍과 탐욕이 있음. 연하남을 유혹할 때 노련하게 수치심 및 도발을 혼합하여 사용하는 전략적 성격]",
                            lines=3
                        )
                        male_desc_input = gr.Textbox(
                            label="남성 캐릭터 설정 (예: 히로시)",
                            placeholder="예: 20대 초반 대학생, 성실하지만 본능에 흔들리는 순진한 청년...",
                            value="히로시: [20대 초반 대학생, 성실하지만 본능에 흔들리는 순진한 청년]",
                            lines=3
                        )
                        relations_desc_input = gr.Textbox(
                            label="관계성 설정",
                            placeholder="예: 연상녀-연하남 / 금기된 관계 / 유혹하는 자와 함락되는 자...",
                            value="연상녀-연하남 / 금기된 관계 / 유혹하는 자와 함락되는 자",
                            lines=2
                        )
                        situation_desc_input = gr.Textbox(
                            label="특정 상황 / 미션 상황 설정",
                            placeholder="예: 옷을 벗겨달라고 요구하는 상황, 빗속에서 문이 잠겨 단둘이 갇힌 상황 등",
                            value="옷을 벗겨달라고 요구하는 상황",
                            lines=2
                        )
                        
                        with gr.Accordion("⚙️ 고급 설정 (추가 프롬프트 조건)", open=True):
                            sensory_enabled = gr.Checkbox(
                                label="👁️ 감각의 구체화 요청",
                                value=True,
                                info="시각, 청각, 후각, 촉각 중 최소 3가지 이상의 감각 묘사를 포함합니다."
                            )
                            contrast_enabled = gr.Checkbox(
                                label="🎭 대조(Contrast) 강조 요청",
                                value=True,
                                info="사회적 정숙함과 도발적인 행동 사이의 수치심과 모순을 강조합니다."
                            )
                            buildup_enabled = gr.Checkbox(
                                label="📈 단계적 빌드업 요청",
                                value=True,
                                info="케이스 번호가 올라갈수록 수위와 유혹의 노골함이 점진적으로 높아집니다."
                            )
                            num_cases_slider = gr.Slider(
                                minimum=1,
                                maximum=10,
                                value=3,
                                step=1,
                                label="생성 케이스 수 (Number of Cases)"
                            )
                            
                        btn_generate_cases = gr.Button("🔥 관능 시나리오 케이스 분화 생성", variant="primary")
                        
                        gr.Markdown("---")
                        with gr.Group():
                            gr.Markdown("### 📜 관능 설정 이력 관리")
                            erotic_ver_name_input = gr.Textbox(
                                label="저장할 버전 이름",
                                placeholder="예: 초안 설정, 2차 자극 다듬음"
                            )
                            with gr.Row():
                                btn_save_erotic_ver = gr.Button("💾 설정 이력 저장", variant="primary")
                                btn_delete_erotic_ver = gr.Button("🗑️ 이력 삭제", variant="stop")
                            erotic_version_dropdown = gr.Dropdown(
                                label="이력 버전 선택",
                                choices=init_erotic_ver_choices,
                                value=init_erotic_ver_val,
                                interactive=True,
                                allow_custom_value=True
                            )
                            btn_load_erotic_ver = gr.Button("📂 선택 이력 불러오기", variant="secondary")
                        
                    with gr.Column(scale=1):
                        gr.Markdown("### 📜 생성된 시나리오 결과")
                        out_cases_markdown = gr.Markdown(
                            value="*왼쪽 설정을 마친 후 생성 버튼을 누르면 실시간으로 관능 시나리오가 분화되어 나타납니다.*",
                            elem_id="cases_output"
                        )
                        
                        parsed_cases_state = gr.State(value=[])
                        
                        with gr.Group():
                            gr.Markdown("### 📥 시나리오 노드로 추가")
                            
                            case_select_dropdown = gr.Dropdown(
                                label="추가할 케이스 선택",
                                choices=[],
                                interactive=True,
                                multiselect=True,
                                allow_custom_value=True
                            )
                            
                            with gr.Row():
                                case_title_input = gr.Textbox(
                                    label="시나리오 노드 제목",
                                    placeholder="선택한 케이스 제목이 표시됩니다.",
                                    scale=3
                                )
                                case_insert_pos = gr.Radio(
                                    choices=[("앞에 삽입", "before"), ("뒤에 삽입", "after"), ("맨 끝에 삽입", "end")],
                                    value="after",
                                    label="삽입 위치",
                                    scale=3
                                )
                                
                            with gr.Row():
                                with gr.Column(scale=1):
                                    case_stage_select = gr.Dropdown(
                                        label="1. 플롯 단계 선택 (Stage)",
                                        choices=init_stages,
                                        value=init_stages[0],
                                        interactive=True
                                    )
                                with gr.Column(scale=2):
                                    case_node_select = gr.Radio(
                                        label="2. 세부 시나리오 노드 선택",
                                        choices=init_node_choices,
                                        value=init_node_val,
                                        interactive=True
                                    )
                                    case_ver_select = gr.Dropdown(
                                        label="3. 이력 버전 트리 선택 (Git Commits)",
                                        choices=init_scen_ver_choices,
                                        value=init_scen_ver_val,
                                        interactive=True,
                                        allow_custom_value=True
                                    )
                                
                            case_content_input = gr.Textbox(
                                label="상세 묘사 텍스트 (편집 가능)",
                                placeholder="노드로 저장될 내용입니다. 편집 후 추가할 수 있습니다.",
                                lines=8
                            )
                            case_meta_display = gr.Textbox(
                                label="참고용 내면 심리 & 자극 포인트 (DB 비저장)",
                                interactive=False,
                                lines=4
                            )
                            
                            with gr.Row():
                                btn_save_case_ver = gr.Button("💾 현재 버전에 바로 저장", variant="primary")
                                btn_delete_case_ver = gr.Button("🗑️ 선택한 버전 삭제", variant="stop")
                                
                            gr.Markdown("---")
                            gr.Markdown("### 💾 새로운 버전으로 커밋")
                            case_commit_msg = gr.Textbox(
                                label="커밋 메시지 (변경 사항에 대한 간략한 기록)",
                                placeholder="예: 관능 씬 묘사 다듬음, 대사 수정"
                            )
                            btn_commit_case_ver = gr.Button("💾 현재 변경사항을 새 버전으로 커밋", variant="primary")
                            
                            gr.Markdown("---")
                            btn_insert_case = gr.Button("💾 선택한 케이스를 시나리오 노드로 삽입", variant="secondary")

            with gr.Tab("📖 최종 소설 취합"):
                gr.Markdown("### 📖 세부 시나리오별 최종 작성 소설 취합 뷰")
                gr.Markdown("각 시나리오 노드별로 최종확정된(또는 최신) 소설 내용을 한눈에 확인하고 관리할 수 있습니다.")
                with gr.Row():
                    btn_refresh_novels = gr.Button("🔄 최종 소설 새로고침", variant="primary", scale=2)
                    btn_export_novels_txt = gr.Button("📥 전체 소설 TXT 다운로드", variant="secondary", scale=1)
                    btn_copy_novels = gr.Button("📋 전체 소설 클립보드 복사", variant="secondary", scale=1)
                novels_download_file = gr.File(label="다운로드 파일", visible=False)
                novels_clipboard_hidden = gr.Textbox(visible=False, elem_id="novels_clipboard_hidden")
                
                with gr.Accordion("📜 전체 취합 텍스트 (Full Compiled Novel)", open=False):
                    novel_full_text = gr.Textbox(
                        label="전체 취합 소설",
                        lines=30,
                        interactive=False
                    )
                
                # Per-scenario textboxes (max 20 slots)
                novel_scenario_boxes = []
                init_novels = compile_per_scenario_novels(initial_project) if initial_project else []
                for i in range(20):
                    if i < len(init_novels):
                        n = init_novels[i]
                        status = "✅ 최종확정" if n["is_finalized"] else ("⚠️ 미확정 (최신본)" if n["novel_content"] else "❌ 미작성")
                        label = f"[{n['stage_short']}-{n['node_index']}] {n['title']} — {status}"
                        header = f"{label}\n{'─'*40}\n"
                        val = header + n["novel_content"]
                        visible = True
                    else:
                        label = f"시나리오 슬롯 {i+1}"
                        val = ""
                        visible = False
                    
                    box = gr.Textbox(
                        label=label,
                        value=val,
                        lines=15,
                        interactive=False,
                        visible=visible
                    )
                    novel_scenario_boxes.append(box)

        # Erotic Scenario Branching Tab Events
        btn_autofill_chars.click(
            fn=autofill_characters_from_project,
            inputs=[project_dropdown],
            outputs=[female_desc_input, male_desc_input, relations_desc_input]
        )
        
        btn_generate_cases.click(
            fn=generate_psychological_scenarios_stream,
            inputs=[
                project_dropdown,
                female_desc_input,
                male_desc_input,
                relations_desc_input,
                situation_desc_input,
                num_cases_slider,
                sensory_enabled,
                contrast_enabled,
                buildup_enabled
            ],
            outputs=[
                out_cases_markdown,
                parsed_cases_state,
                case_select_dropdown
            ]
        ).then(
            fn=auto_save_erotic_version,
            inputs=[
                project_dropdown,
                female_desc_input,
                male_desc_input,
                relations_desc_input,
                situation_desc_input,
                sensory_enabled,
                contrast_enabled,
                buildup_enabled,
                num_cases_slider,
                out_cases_markdown,
                parsed_cases_state
            ],
            outputs=[
                erotic_version_dropdown
            ]
        )
        
        btn_save_erotic_ver.click(
            fn=save_erotic_version,
            inputs=[
                project_dropdown,
                erotic_ver_name_input,
                female_desc_input,
                male_desc_input,
                relations_desc_input,
                situation_desc_input,
                sensory_enabled,
                contrast_enabled,
                buildup_enabled,
                num_cases_slider,
                out_cases_markdown,
                parsed_cases_state
            ],
            outputs=[
                erotic_version_dropdown,
                erotic_ver_name_input
            ]
        )

        btn_load_erotic_ver.click(
            fn=load_erotic_version,
            inputs=[
                erotic_version_dropdown
            ],
            outputs=[
                female_desc_input,
                male_desc_input,
                relations_desc_input,
                situation_desc_input,
                sensory_enabled,
                contrast_enabled,
                buildup_enabled,
                num_cases_slider,
                out_cases_markdown,
                parsed_cases_state,
                case_select_dropdown
            ]
        )

        btn_delete_erotic_ver.click(
            fn=delete_erotic_version,
            inputs=[
                erotic_version_dropdown,
                project_dropdown
            ],
            outputs=[
                erotic_version_dropdown
            ]
        )
        
        case_select_dropdown.change(
            fn=load_selected_case_details,
            inputs=[case_select_dropdown, parsed_cases_state],
            outputs=[case_title_input, case_content_input, case_meta_display]
        )
        
        btn_insert_case.click(
            fn=insert_case_to_scenario_node,
            inputs=[
                project_dropdown,
                case_stage_select,
                case_insert_pos,
                case_node_select,
                case_title_input,
                case_content_input
            ],
            outputs=[
                case_node_select,
                scen_node_dropdown,
                scen_ver_dropdown,
                scen_title_box,
                scen_content_box
            ]
        ).then(
            fn=refresh_target_scenario_dropdown,
            inputs=[project_dropdown],
            outputs=[target_scenario_dropdown]
        )

        case_stage_select.change(
            fn=on_case_stage_change,
            inputs=[project_dropdown, case_stage_select],
            outputs=[case_node_select, case_ver_select, case_content_input, case_title_input]
        )

        case_node_select.change(
            fn=on_case_node_change,
            inputs=[project_dropdown, case_stage_select, case_node_select],
            outputs=[case_ver_select, case_content_input, case_title_input]
        )

        case_ver_select.change(
            fn=on_case_ver_change,
            inputs=[case_ver_select],
            outputs=[case_content_input, case_title_input]
        )

        project_dropdown.change(
            fn=load_project_details,
            inputs=[project_dropdown],
            outputs=[
                char_name, char_role, 
                char_personality, char_background, char_relations, char_speech_style,
                char_dropdown, char_dummy,
                system_prompt, overall_plot,
                positive_prompt, negative_prompt,
                version_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_ver_dropdown,
                scen_content_box,
                scen_title_box,
                scene_history_dropdown,
                target_scenario_dropdown,
                active_characters,
                erotic_version_dropdown
            ]
        ).then(
            fn=lambda: gr.update(value="기 (起 - 도입)"),
            inputs=[],
            outputs=[case_stage_select]
        ).then(
            fn=on_case_stage_change,
            inputs=[project_dropdown, case_stage_select],
            outputs=[case_node_select, case_ver_select, case_content_input, case_title_input]
        ).then(
            fn=update_erotic_char_dropdowns,
            inputs=[project_dropdown],
            outputs=[female_char_select, male_char_select]
        )

        btn_save_case_ver.click(
            fn=on_case_save_ver,
            inputs=[
                project_dropdown,
                case_stage_select,
                case_node_select,
                case_ver_select,
                case_title_input,
                case_content_input
            ],
            outputs=[
                case_ver_select,
                scen_ver_dropdown,
                case_node_select,
                scen_node_dropdown,
                target_scenario_dropdown,
                case_content_input,
                scen_content_box,
                case_title_input,
                scen_title_box
            ]
        )

        btn_delete_case_ver.click(
            fn=on_case_delete_ver,
            inputs=[
                project_dropdown,
                case_stage_select,
                case_node_select,
                case_ver_select
            ],
            outputs=[
                case_ver_select,
                scen_ver_dropdown,
                case_node_select,
                scen_node_dropdown,
                target_scenario_dropdown,
                case_content_input,
                scen_content_box,
                case_title_input,
                scen_title_box
            ]
        )

        btn_commit_case_ver.click(
            fn=on_case_commit_ver,
            inputs=[
                project_dropdown,
                case_stage_select,
                case_node_select,
                case_title_input,
                case_content_input,
                case_commit_msg,
                case_ver_select
            ],
            outputs=[
                case_ver_select,
                scen_ver_dropdown,
                case_node_select,
                scen_node_dropdown,
                target_scenario_dropdown,
                case_content_input,
                scen_content_box,
                case_title_input,
                scen_title_box,
                case_commit_msg
            ]
        )

        female_char_select.change(
            fn=on_female_char_select,
            inputs=[female_char_select],
            outputs=[female_desc_input]
        )

        male_char_select.change(
            fn=on_male_char_select,
            inputs=[male_char_select],
            outputs=[male_desc_input]
        )

        btn_ai_autofill_erotic_settings.click(
            fn=ai_generate_erotic_settings,
            inputs=[female_char_select, male_char_select],
            outputs=[female_desc_input, male_desc_input, relations_desc_input, situation_desc_input]
        )

        # Set up event handlers
        btn_load_project.click(
            fn=load_project_details,
            inputs=[project_dropdown],
            outputs=[
                char_name, char_role, 
                char_personality, char_background, char_relations, char_speech_style,
                char_dropdown, char_dummy,
                system_prompt, overall_plot,
                positive_prompt, negative_prompt,
                version_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_ver_dropdown,
                scen_content_box,
                scen_title_box,
                scene_history_dropdown,
                target_scenario_dropdown,
                active_characters,
                erotic_version_dropdown
            ]
        ).then(
            fn=lambda: gr.update(value="기 (起 - 도입)"),
            inputs=[],
            outputs=[case_stage_select]
        ).then(
            fn=on_case_stage_change,
            inputs=[project_dropdown, case_stage_select],
            outputs=[case_node_select, case_ver_select, case_content_input, case_title_input]
        ).then(
            fn=update_erotic_char_dropdowns,
            inputs=[project_dropdown],
            outputs=[female_char_select, male_char_select]
        )
        
        btn_save_project.click(
            fn=save_project_only,
            inputs=[
                project_dropdown, 
                system_prompt, overall_plot,
                positive_prompt, negative_prompt
            ],
            outputs=[]
        )
        
        btn_save_settings.click(
            fn=save_project_only,
            inputs=[
                project_dropdown, 
                system_prompt, overall_plot,
                positive_prompt, negative_prompt
            ],
            outputs=[]
        )
        
        btn_preview_plot_prompt.click(
            fn=preview_overall_plot_prompt,
            inputs=[project_dropdown, plot_idea_input],
            outputs=[plot_prompt_preview],
            queue=False
        )

        btn_generate_plot.click(
            fn=generate_overall_plot,
            inputs=[
                project_dropdown, 
                plot_idea_input, 
                system_prompt, 
                positive_prompt, 
                negative_prompt
            ],
            outputs=[overall_plot, version_dropdown]
        )
        
        btn_delete_project.click(
            fn=delete_project,
            inputs=[project_dropdown],
            outputs=[
                project_dropdown, 
                char_name, char_role, 
                char_personality, char_background, char_relations, char_speech_style,
                char_dropdown, char_dummy,
                system_prompt, overall_plot,
                positive_prompt, negative_prompt,
                version_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_ver_dropdown,
                scen_content_box,
                scen_title_box,
                scene_history_dropdown,
                target_scenario_dropdown,
                active_characters,
                erotic_version_dropdown
            ]
        ).then(
            fn=lambda: gr.update(value="기 (起 - 도입)"),
            inputs=[],
            outputs=[case_stage_select]
        ).then(
            fn=on_case_stage_change,
            inputs=[project_dropdown, case_stage_select],
            outputs=[case_node_select, case_ver_select, case_content_input, case_title_input]
        ).then(
            fn=update_erotic_char_dropdowns,
            inputs=[project_dropdown],
            outputs=[female_char_select, male_char_select]
        )
        
        btn_create_project.click(
            fn=create_new_project,
            inputs=[new_title, new_genre],
            outputs=[
                project_dropdown, 
                char_name, char_role, 
                char_personality, char_background, char_relations, char_speech_style,
                char_dropdown, char_dummy,
                system_prompt, overall_plot,
                positive_prompt, negative_prompt,
                version_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_ver_dropdown,
                scen_content_box,
                scen_title_box,
                new_title, new_genre,
                scene_history_dropdown,
                target_scenario_dropdown,
                active_characters,
                erotic_version_dropdown
            ]
        ).then(
            fn=lambda: gr.update(value="기 (起 - 도입)"),
            inputs=[],
            outputs=[case_stage_select]
        ).then(
            fn=on_case_stage_change,
            inputs=[project_dropdown, case_stage_select],
            outputs=[case_node_select, case_ver_select, case_content_input, case_title_input]
        ).then(
            fn=update_erotic_char_dropdowns,
            inputs=[project_dropdown],
            outputs=[female_char_select, male_char_select]
        )

        btn_load_scen_node_gen.click(
            fn=on_target_scenario_change,
            inputs=[project_dropdown, target_scenario_dropdown],
            outputs=[scene_history_dropdown, instruction, out_final_scene, out_diff, out_facts, out_tracker]
        ).then(
            fn=preview_ai_prompts,
            inputs=[
                project_dropdown, 
                system_prompt, overall_plot,
                positive_prompt, negative_prompt,
                instruction,
                active_characters,
                target_scenario_dropdown
            ],
            outputs=[out_used_prompts, out_optimized_prompts],
            queue=False
        )

        target_scenario_dropdown.change(
            fn=on_target_scenario_change,
            inputs=[project_dropdown, target_scenario_dropdown],
            outputs=[scene_history_dropdown, instruction, out_final_scene, out_diff, out_facts, out_tracker]
        ).then(
            fn=preview_ai_prompts,
            inputs=[
                project_dropdown, 
                system_prompt, overall_plot,
                positive_prompt, negative_prompt,
                instruction,
                active_characters,
                target_scenario_dropdown
            ],
            outputs=[out_used_prompts, out_optimized_prompts],
            queue=False
        )

        btn_generate.click(
            fn=generate_scene,
            inputs=[
                project_dropdown, 
                system_prompt, overall_plot,
                positive_prompt, negative_prompt,
                instruction,
                active_characters,
                target_scenario_dropdown
            ],
            outputs=[out_final_scene, out_diff, out_facts, out_tracker, scene_history_dropdown]
        )
        
        btn_load_scene_history.click(
            fn=load_scene_history,
            inputs=[scene_history_dropdown],
            outputs=[out_final_scene, out_diff, out_facts, out_tracker, instruction, user_refine_prompt]
        )
        
        btn_delete_scene_history.click(
            fn=delete_scene_history,
            inputs=[project_dropdown, scene_history_dropdown, target_scenario_dropdown],
            outputs=[scene_history_dropdown, out_final_scene, out_diff, out_facts, out_tracker, instruction, user_refine_prompt]
        )

        btn_save_scene.click(
            fn=save_scene_history,
            inputs=[
                project_dropdown,
                scene_history_dropdown,
                out_final_scene,
                target_scenario_dropdown
            ],
            outputs=[
                scene_history_dropdown,
                out_final_scene,
                out_diff
            ]
        )

        btn_finalize_scene.click(
            fn=finalize_scene_history,
            inputs=[project_dropdown, scene_history_dropdown, target_scenario_dropdown],
            outputs=[scene_history_dropdown]
        )

        btn_preview_prompts.click(
            fn=preview_ai_prompts,
            inputs=[
                project_dropdown,
                system_prompt, overall_plot,
                positive_prompt, negative_prompt,
                instruction,
                active_characters,
                target_scenario_dropdown
            ],
            outputs=[out_used_prompts, out_optimized_prompts],
            queue=False
        )

        # Dynamic Character Management Handlers
        char_dropdown.change(
            fn=on_character_select_change,
            inputs=[char_dropdown],
            outputs=[char_name, char_role, char_personality, char_background, char_relations, char_speech_style]
        ).then(
            fn=get_character_version_choices_update,
            inputs=[char_dropdown],
            outputs=[char_version_dropdown]
        )

        btn_add_char.click(
            fn=add_new_blank_character,
            inputs=[project_dropdown],
            outputs=[char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style]
        ).then(
            fn=update_active_characters_checkbox,
            inputs=[project_dropdown],
            outputs=[active_characters]
        ).then(
            fn=update_erotic_char_dropdowns,
            inputs=[project_dropdown],
            outputs=[female_char_select, male_char_select]
        )

        btn_delete_char.click(
            fn=delete_selected_character,
            inputs=[project_dropdown, char_dropdown],
            outputs=[char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style]
        ).then(
            fn=update_active_characters_checkbox,
            inputs=[project_dropdown],
            outputs=[active_characters]
        ).then(
            fn=update_erotic_char_dropdowns,
            inputs=[project_dropdown],
            outputs=[female_char_select, male_char_select]
        )

        btn_save_character_detail.click(
            fn=save_or_update_character,
            inputs=[project_dropdown, char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style],
            outputs=[char_dropdown, char_dummy, char_name, char_role, char_personality, char_background, char_relations, char_speech_style]
        ).then(
            fn=update_active_characters_checkbox,
            inputs=[project_dropdown],
            outputs=[active_characters]
        ).then(
            fn=update_erotic_char_dropdowns,
            inputs=[project_dropdown],
            outputs=[female_char_select, male_char_select]
        )

        btn_generate_characters.click(
            fn=api_generate_characters,
            inputs=[project_dropdown],
            outputs=[char_dropdown, char_name, char_role, char_personality, char_background, char_relations, char_speech_style]
        ).then(
            fn=update_active_characters_checkbox,
            inputs=[project_dropdown],
            outputs=[active_characters]
        ).then(
            fn=update_erotic_char_dropdowns,
            inputs=[project_dropdown],
            outputs=[female_char_select, male_char_select]
        )

        btn_preview_char_prompt.click(
            fn=preview_character_gen_prompt,
            inputs=[project_dropdown],
            outputs=[char_prompt_preview],
            queue=False
        )

        # Character Version history handlers
        btn_save_char_version.click(
            fn=save_character_version,
            inputs=[
                char_dropdown,
                char_ver_name_input,
                char_name,
                char_role,
                char_personality,
                char_background,
                char_relations,
                char_speech_style
            ],
            outputs=[char_version_dropdown, char_ver_name_input]
        )

        btn_load_char_version.click(
            fn=load_character_version,
            inputs=[char_version_dropdown],
            outputs=[char_name, char_role, char_personality, char_background, char_relations, char_speech_style]
        )

        btn_delete_char_version.click(
            fn=delete_character_version,
            inputs=[char_version_dropdown, char_dropdown],
            outputs=[char_version_dropdown]
        )

        btn_edit_char_version.click(
            fn=edit_character_version,
            inputs=[char_version_dropdown, new_char_ver_name_input, char_dropdown],
            outputs=[char_version_dropdown, new_char_ver_name_input]
        )

        btn_refine_scene.click(
            fn=refine_scene_with_prompt,
            inputs=[project_dropdown, out_final_scene, user_refine_prompt, system_prompt, target_scenario_dropdown],
            outputs=[out_final_scene, out_diff]
        ).then(
            fn=update_scene_history_dropdown,
            inputs=[project_dropdown, target_scenario_dropdown],
            outputs=[scene_history_dropdown]
        )

        btn_verify_scene.click(
            fn=verify_generated_scene,
            inputs=[project_dropdown, out_final_scene, target_scenario_dropdown],
            outputs=[out_facts, out_tracker]
        )

        # Version control handlers
        btn_save_version.click(
            fn=save_prompt_version,
            inputs=[
                project_dropdown,
                ver_name_input,
                system_prompt,
                overall_plot,
                positive_prompt,
                negative_prompt
            ],
            outputs=[version_dropdown, ver_name_input]
        )

        btn_load_version.click(
            fn=load_prompt_version,
            inputs=[version_dropdown],
            outputs=[system_prompt, overall_plot, positive_prompt, negative_prompt]
        )

        btn_delete_version.click(
            fn=delete_prompt_version,
            inputs=[version_dropdown, project_dropdown],
            outputs=[version_dropdown]
        )

        btn_edit_version.click(
            fn=edit_prompt_version,
            inputs=[version_dropdown, new_ver_name_input, project_dropdown],
            outputs=[version_dropdown, new_ver_name_input]
        )
        
        # Scenario planning event handlers
        btn_auto_scen_gen.click(
            fn=api_generate_scenario_nodes,
            inputs=[project_dropdown],
            outputs=[scen_stage_dropdown, scen_node_dropdown, scen_ver_dropdown]
        ).then(
            fn=on_ver_change,
            inputs=[scen_ver_dropdown],
            outputs=[scen_content_box, scen_title_box, scen_regen_prompt]
        ).then(
            fn=refresh_target_scenario_dropdown,
            inputs=[project_dropdown],
            outputs=[target_scenario_dropdown]
        ).then(
            fn=on_case_stage_change,
            inputs=[project_dropdown, case_stage_select],
            outputs=[case_node_select, case_ver_select, case_content_input, case_title_input]
        )
        
        scen_stage_dropdown.change(
            fn=on_scen_stage_change,
            inputs=[project_dropdown, scen_stage_dropdown],
            outputs=[scen_node_dropdown, case_node_select, scen_ver_dropdown, case_ver_select, scen_content_box, case_content_input, scen_title_box, case_title_input, scen_regen_prompt]
        )
        
        scen_node_dropdown.change(
            fn=on_scen_node_change,
            inputs=[project_dropdown, scen_stage_dropdown, scen_node_dropdown],
            outputs=[scen_ver_dropdown, case_ver_select, scen_content_box, case_content_input, scen_title_box, case_title_input, scen_regen_prompt]
        )
        
        scen_ver_dropdown.change(
            fn=on_scen_ver_change,
            inputs=[scen_ver_dropdown],
            outputs=[scen_content_box, case_content_input, scen_title_box, case_title_input, scen_regen_prompt]
        )
        
        scen_title_box.input(
            fn=update_radio_title_on_type,
            inputs=[project_dropdown, scen_stage_dropdown, scen_node_dropdown, scen_title_box],
            outputs=[scen_node_dropdown]
        )
        
        btn_commit_ver.click(
            fn=on_scen_commit_ver,
            inputs=[
                project_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_title_box,
                scen_content_box,
                scen_commit_msg,
                scen_ver_dropdown,
                scen_regen_prompt
            ],
            outputs=[
                scen_ver_dropdown,
                case_ver_select,
                scen_node_dropdown,
                case_node_select,
                target_scenario_dropdown,
                scen_content_box,
                case_content_input,
                scen_title_box,
                case_title_input,
                scen_commit_msg
            ]
        )
        
        btn_delete_ver.click(
            fn=on_scen_delete_ver,
            inputs=[
                project_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_ver_dropdown
            ],
            outputs=[
                scen_ver_dropdown,
                case_ver_select,
                scen_node_dropdown,
                case_node_select,
                target_scenario_dropdown,
                scen_content_box,
                case_content_input,
                scen_title_box,
                case_title_input
            ]
        )
        
        btn_save_scen_ver.click(
            fn=on_scen_save_ver,
            inputs=[
                project_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_ver_dropdown,
                scen_title_box,
                scen_content_box,
                scen_regen_prompt
            ],
            outputs=[
                scen_ver_dropdown,
                case_ver_select,
                scen_node_dropdown,
                case_node_select,
                target_scenario_dropdown,
                scen_content_box,
                case_content_input,
                scen_title_box,
                case_title_input
            ]
        )
        
        btn_regen_node.click(
            fn=regenerate_scenario_node,
            inputs=[
                project_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_title_box,
                scen_ver_dropdown,
                scen_regen_prompt
            ],
            outputs=[scen_ver_dropdown, scen_node_dropdown, scen_content_box]
        ).then(
            fn=refresh_target_scenario_dropdown,
            inputs=[project_dropdown],
            outputs=[target_scenario_dropdown]
        )
        
        btn_preview_regen_prompt.click(
            fn=preview_scenario_regen_prompts,
            inputs=[
                project_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_title_box,
                scen_regen_prompt
            ],
            outputs=[scen_used_prompts],
            queue=False
        )
        # 시나리오 노드 추가/삭제 핸들러
        btn_add_node.click(
            fn=add_scenario_node,
            inputs=[project_dropdown, scen_stage_dropdown, scen_node_dropdown, node_insert_position],
            outputs=[scen_node_dropdown, scen_ver_dropdown, scen_title_box, scen_content_box]
        ).then(
            fn=refresh_target_scenario_dropdown,
            inputs=[project_dropdown],
            outputs=[target_scenario_dropdown]
        ).then(
            fn=on_case_stage_change,
            inputs=[project_dropdown, case_stage_select],
            outputs=[case_node_select, case_ver_select, case_content_input, case_title_input]
        )

        btn_delete_node.click(
            fn=delete_scenario_node,
            inputs=[project_dropdown, scen_stage_dropdown, scen_node_dropdown],
            outputs=[scen_node_dropdown, scen_ver_dropdown, scen_title_box, scen_content_box]
        ).then(
            fn=refresh_target_scenario_dropdown,
            inputs=[project_dropdown],
            outputs=[target_scenario_dropdown]
        ).then(
            fn=on_case_stage_change,
            inputs=[project_dropdown, case_stage_select],
            outputs=[case_node_select, case_ver_select, case_content_input, case_title_input]
        )

        # 전체 시나리오 내보내기 핸들러
        btn_export_txt.click(
            fn=export_scenario_as_txt,
            inputs=[project_dropdown],
            outputs=[scenario_download_file]
        ).then(
            fn=lambda x: gr.update(visible=True) if x else gr.update(visible=False),
            inputs=[scenario_download_file],
            outputs=[scenario_download_file]
        )

        btn_copy_clipboard.click(
            fn=copy_scenario_to_clipboard,
            inputs=[project_dropdown],
            outputs=[scenario_clipboard_hidden]
        ).then(
            fn=None,
            inputs=[scenario_clipboard_hidden],
            outputs=[],
            js="(text) => { if(text) { navigator.clipboard.writeText(text).then(() => {}).catch(err => console.error('Clipboard write failed:', err)); } }"
        )

        # 최종 소설 취합 탭 핸들러
        def _refresh_novels_with_visibility(project_str):
            """소설 취합 새로고침 + 슬롯 가시성 업데이트"""
            novels = compile_per_scenario_novels(project_str)
            full_text = compile_full_scenario_text(project_str)
            
            updates = [gr.update(value=full_text)]
            for i in range(20):
                if i < len(novels):
                    n = novels[i]
                    status = "✅ 최종확정" if n["is_finalized"] else ("⚠️ 미확정 (최신본)" if n["novel_content"] else "❌ 미작성")
                    label = f"[{n['stage_short']}-{n['node_index']}] {n['title']} — {status}"
                    header = f"{label}\n{'─'*40}\n"
                    updates.append(gr.update(value=header + n["novel_content"], label=label, visible=True))
                else:
                    updates.append(gr.update(value="", visible=False))
            
            gr.Info("최종 소설 취합이 새로고침되었습니다.")
            return updates

        btn_refresh_novels.click(
            fn=_refresh_novels_with_visibility,
            inputs=[project_dropdown],
            outputs=[novel_full_text] + novel_scenario_boxes
        )

        btn_export_novels_txt.click(
            fn=export_scenario_as_txt,
            inputs=[project_dropdown],
            outputs=[novels_download_file]
        ).then(
            fn=lambda x: gr.update(visible=True) if x else gr.update(visible=False),
            inputs=[novels_download_file],
            outputs=[novels_download_file]
        )

        btn_copy_novels.click(
            fn=copy_scenario_to_clipboard,
            inputs=[project_dropdown],
            outputs=[novels_clipboard_hidden]
        ).then(
            fn=None,
            inputs=[novels_clipboard_hidden],
            outputs=[],
            js="(text) => { if(text) { navigator.clipboard.writeText(text).then(() => {}).catch(err => console.error('Clipboard write failed:', err)); } }"
        )
        
        btn_export_chars_txt.click(
            fn=export_characters_as_txt,
            inputs=[project_dropdown],
            outputs=[char_download_file]
        ).then(
            fn=lambda x: gr.update(visible=True) if x else gr.update(visible=False),
            inputs=[char_download_file],
            outputs=[char_download_file]
        )

        btn_copy_chars_clipboard.click(
            fn=copy_characters_to_clipboard,
            inputs=[project_dropdown],
            outputs=[char_clipboard_hidden]
        ).then(
            fn=None,
            inputs=[char_clipboard_hidden],
            outputs=[],
            js="(text) => { if(text) { navigator.clipboard.writeText(text).then(() => {}).catch(err => console.error('Clipboard write failed:', err)); } }"
        )

        app.load(
            fn=on_page_load,
            inputs=[],
            outputs=[project_dropdown]
        ).then(
            fn=load_project_details,
            inputs=[project_dropdown],
            outputs=[
                char_name, char_role, 
                char_personality, char_background, char_relations, char_speech_style,
                char_dropdown, char_dummy,
                system_prompt, overall_plot,
                positive_prompt, negative_prompt,
                version_dropdown,
                scen_stage_dropdown,
                scen_node_dropdown,
                scen_ver_dropdown,
                scen_content_box,
                scen_title_box,
                scene_history_dropdown,
                target_scenario_dropdown,
                active_characters,
                erotic_version_dropdown
            ]
        ).then(
            fn=lambda: gr.update(value="기 (起 - 도입)"),
            inputs=[],
            outputs=[case_stage_select]
        ).then(
            fn=on_case_stage_change,
            inputs=[project_dropdown, case_stage_select],
            outputs=[case_node_select, case_ver_select, case_content_input, case_title_input]
        ).then(
            fn=update_erotic_char_dropdowns,
            inputs=[project_dropdown],
            outputs=[female_char_select, male_char_select]
        )
        
    return app

if __name__ == "__main__":
    app = build_ui()
    app.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)
