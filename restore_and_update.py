import os

def run():
    path = "d:/DeepScribe/abyss_writer/ui.py"
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # We want to keep lines up to index 332 (which is line 333, "        gr.Info(...)")
    # Let's verify line 333 (index 332) content
    part1 = lines[:333]
    print("Part 1 last line:", part1[-1])
    
    # We want to keep lines from index 346 (which is line 347, "        status=\"Draft\",")
    # Let's verify line 347 (index 346) content
    part2 = lines[346:]
    print("Part 2 first line:", part2[0])
    
    # Reconstructed gap code:
    gap_code = """        return (
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
"""
    
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(part1)
        f.write(gap_code)
        f.writelines(part2)
    print("Restore and Update successful!")

if __name__ == "__main__":
    run()
