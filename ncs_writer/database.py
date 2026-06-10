import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ncs_projects.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # Create projects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    
    # Create project_versions table to store snapshots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            revision INTEGER NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            
            -- Tab 1 Fields
            job_name_mod TEXT,
            learning_no_mod TEXT,
            learning_title_mod TEXT,
            section_no_mod TEXT,
            module_header_mod TEXT,
            additional_info_mod TEXT,
            out_objectives TEXT,
            out_knowledge TEXT,
            out_perf_content TEXT,
            out_perf_steps TEXT,
            out_perf_tips TEXT,
            
            -- Tab 2 Fields
            job_name TEXT,
            additional_info TEXT,
            out_ksa TEXT,
            out_range TEXT,
            out_assessment TEXT,
            
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    conn.close()

def get_project_list():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM projects ORDER BY updated_at DESC")
    projects = [row[0] for row in cursor.fetchall()]
    conn.close()
    if not projects:
        create_project("기본 프로젝트")
        projects = ["기본 프로젝트"]
    return projects

def create_project(name):
    init_db()
    if not name or not name.strip():
        return False, "프로젝트 이름을 입력해주세요."
    
    name = name.strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO projects (name, created_at, updated_at) VALUES (?, ?, ?)", (name, now, now))
        conn.commit()
        project_id = cursor.lastrowid
        
        # Insert initial empty version (Revision 1)
        cursor.execute("""
            INSERT INTO project_versions (
                project_id, revision, description, created_at,
                job_name_mod, learning_no_mod, learning_title_mod, section_no_mod, module_header_mod, additional_info_mod,
                out_objectives, out_knowledge, out_perf_content, out_perf_steps, out_perf_tips,
                job_name, additional_info, out_ksa, out_range, out_assessment
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, "초기 생성", now,
            "침해사고 분석대응", "학습 2", "침해사고정보 수집하기", "2-1. 현장 보존 후 대상별 정보 확보", "학습 1 침해사고정보 수집 준비하기", "",
            "", "", "", "", "",
            "침해사고 분석대응", "", "", "", ""
        ))
        conn.commit()
        return True, f"프로젝트 '{name}'이(가) 성공적으로 생성되었습니다."
    except sqlite3.IntegrityError:
        return False, "이미 존재하는 프로젝트 이름입니다."
    finally:
        conn.close()

def delete_project(name):
    init_db()
    if not name:
        return False, "삭제할 프로젝트가 선택되지 않았습니다."
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("DELETE FROM projects WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    return True, f"프로젝트 '{name}'이(가) 삭제되었습니다."

def save_version(project_name, description, fields_dict):
    init_db()
    if not project_name:
        return False, "프로젝트가 선택되지 않았습니다."
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM projects WHERE name = ?", (project_name,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "프로젝트를 찾을 수 없습니다."
    
    project_id = row[0]
    
    # Get last revision number
    cursor.execute("SELECT MAX(revision) FROM project_versions WHERE project_id = ?", (project_id,))
    max_rev = cursor.fetchone()[0] or 0
    next_rev = max_rev + 1
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Save snapshot
    cursor.execute("""
        INSERT INTO project_versions (
            project_id, revision, description, created_at,
            job_name_mod, learning_no_mod, learning_title_mod, section_no_mod, module_header_mod, additional_info_mod,
            out_objectives, out_knowledge, out_perf_content, out_perf_steps, out_perf_tips,
            job_name, additional_info, out_ksa, out_range, out_assessment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_id, next_rev, description, now,
        fields_dict.get("job_name_mod", ""),
        fields_dict.get("learning_no_mod", ""),
        fields_dict.get("learning_title_mod", ""),
        fields_dict.get("section_no_mod", ""),
        fields_dict.get("module_header_mod", ""),
        fields_dict.get("additional_info_mod", ""),
        fields_dict.get("out_objectives", ""),
        fields_dict.get("out_knowledge", ""),
        fields_dict.get("out_perf_content", ""),
        fields_dict.get("out_perf_steps", ""),
        fields_dict.get("out_perf_tips", ""),
        fields_dict.get("job_name", ""),
        fields_dict.get("additional_info", ""),
        fields_dict.get("out_ksa", ""),
        fields_dict.get("out_range", ""),
        fields_dict.get("out_assessment", "")
    ))
    
    # Update project updated_at time
    cursor.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (now, project_id))
    conn.commit()
    conn.close()
    return True, f"리비전 {next_rev} ({description})이(가) 저장되었습니다."

def get_project_versions(project_name):
    init_db()
    if not project_name:
        return []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT pv.revision, pv.description, pv.created_at
        FROM project_versions pv
        JOIN projects p ON pv.project_id = p.id
        WHERE p.name = ?
        ORDER BY pv.revision DESC
    """, (project_name,))
    
    versions = []
    for row in cursor.fetchall():
        rev, desc, dt = row
        label = f"Rev {rev} ({dt}) - {desc}"
        versions.append((label, rev))
    
    conn.close()
    return versions

def load_version(project_name, revision):
    init_db()
    if not project_name or not revision:
        return None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            pv.job_name_mod, pv.learning_no_mod, pv.learning_title_mod, pv.section_no_mod, pv.module_header_mod, pv.additional_info_mod,
            pv.out_objectives, pv.out_knowledge, pv.out_perf_content, pv.out_perf_steps, pv.out_perf_tips,
            pv.job_name, pv.additional_info, pv.out_ksa, pv.out_range, pv.out_assessment
        FROM project_versions pv
        JOIN projects p ON pv.project_id = p.id
        WHERE p.name = ? AND pv.revision = ?
    """, (project_name, int(revision)))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    keys = [
        "job_name_mod", "learning_no_mod", "learning_title_mod", "section_no_mod", "module_header_mod", "additional_info_mod",
        "out_objectives", "out_knowledge", "out_perf_content", "out_perf_steps", "out_perf_tips",
        "job_name", "additional_info", "out_ksa", "out_range", "out_assessment"
    ]
    return dict(zip(keys, row))
