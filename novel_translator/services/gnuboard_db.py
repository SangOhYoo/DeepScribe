import os
import json
import pymysql
import logging
import re
import html

logger = logging.getLogger("NovelTranslator.GnuboardDB")

# config.json 경로 탐색
def get_db_config():
    paths = [
        r"d:\indexer_max\config.json",
        r"D:\indexer_max\config.json",
        r"C:\indexer_max\config.json",
        r"indexer_max\config.json",
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("database", {})
            except Exception as e:
                logger.error(f"Error loading config from {path}: {e}")
    # Default fallback
    return {
        "host": "127.0.0.1",
        "user": "root",
        "password": "gmlakddl",
        "db": "g5",
        "charset": "utf8mb4"
    }

DB_CONFIG = get_db_config()
TABLE_PREFIX = "g5_write_"

# lux_merge.php의 target_boards 리스트
TARGET_BOARDS = ['noc', 'jp', 'sora', 'yajun', 'wolf', 'private', 'wm', 'trs']

def get_db_connection():
    """동기식 PyMySQL 커넥션을 생성합니다. 타임아웃 5초 설정으로 락 대기를 방지합니다."""
    return pymysql.connect(
        host=DB_CONFIG.get("host", "127.0.0.1"),
        user=DB_CONFIG.get("user", "root"),
        password=DB_CONFIG.get("password", ""),
        database=DB_CONFIG.get("db", "g5"),
        charset=DB_CONFIG.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5
    )

_cached_boards = None

def get_boards():
    """게시판 목록을 동적으로 가져옵니다. target_boards 리스트에 있는 게시판 위주로 필터링합니다."""
    global _cached_boards
    if _cached_boards is not None:
        return _cached_boards
    default_boards = [
        ("녹턴노벨즈 (noc)", "noc"),
        ("프랑스서원 (jp)", "jp"),
        ("소라 가이드 (sora)", "sora"),
        ("야설의 전당 (yajun)", "yajun"),
        ("야설의 문 (wolf)", "wolf"),
        ("야설의 모음 (private)", "private"),
        ("아내와 발기된 남자들 (wm)", "wm"),
        ("번역 (trs)", "trs"),
    ]
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT bo_table, bo_subject FROM g5_board ORDER BY bo_subject ASC")
            rows = cur.fetchall()
            if rows:
                db_boards = {r["bo_table"]: r["bo_subject"] for r in rows}
                result = []
                # lux_merge.php 처럼 TARGET_BOARDS 순서대로 필터링하여 우선 생성
                for table in TARGET_BOARDS:
                    if table in db_boards:
                        result.append((f"{db_boards[table]} ({table})", table))
                    else:
                        # 디폴트 텍스트 매칭
                        matched_default = [d[0] for d in default_boards if d[1] == table]
                        name = matched_default[0] if matched_default else f"게시판 ({table})"
                        result.append((name, table))
                return result
    except Exception as e:
        logger.error(f"Failed to fetch boards from DB: {e}")
    finally:
        if conn:
            conn.close()
        
    return default_boards

def search_posts(bo_table, stx="", sort="wr_id", page_rows=20, page=1):
    """게시글을 검색하여 목록과 총 개수를 반환합니다."""
    if not bo_table:
        return {"posts": [], "total_count": 0, "page": 1, "max_page": 1}
    
    # 보안 강화 (lux_merge.php와 동일하게 영문, 숫자, _ 만 허용)
    safe_bo_table = re.sub(r'[^a-zA-Z0-9_]', '', bo_table)
    write_table = f"{TABLE_PREFIX}{safe_bo_table}"
    
    # 정렬 방식 매핑
    sort_mapping = {
        "wr_id": "wr_id DESC",
        "wr_id_asc": "wr_id ASC",
        "wr_subject": "wr_subject ASC",
        "wr_subject_desc": "wr_subject DESC",
    }
    order_clause = sort_mapping.get(sort, "wr_id DESC")
    
    # 검색 조건 (lux_merge.php와 같이 공백 분할 다중 검색어 적용)
    where_clause = "WHERE wr_is_comment = 0"
    params = []
    if stx and stx.strip():
        keywords = stx.strip().split()
        search_clauses = []
        for word in keywords:
            if word.strip():
                search_clauses.append("wr_subject LIKE %s")
                params.append(f"%{word.strip()}%")
        if search_clauses:
            where_clause += " AND " + " AND ".join(search_clauses)
        
    limit = int(page_rows)
    offset = (int(page) - 1) * limit
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 1. Total Count 조회
            count_sql = f"SELECT COUNT(*) as cnt FROM {write_table} {where_clause}"
            cur.execute(count_sql, tuple(params))
            count_row = cur.fetchone()
            total_count = count_row["cnt"] if count_row else 0
            
            # 2. Posts 목록 조회
            select_sql = f"""
                SELECT wr_id, ca_name, wr_subject, wr_name, wr_datetime 
                FROM {write_table} 
                {where_clause} 
                ORDER BY {order_clause} 
                LIMIT %s OFFSET %s
            """
            query_params = list(params) + [limit, offset]
            cur.execute(select_sql, tuple(query_params))
            posts = cur.fetchall()
            
            # datetime 포맷팅
            for p in posts:
                if p.get("wr_datetime"):
                    p["wr_datetime"] = p["wr_datetime"].strftime("%Y-%m-%d %H:%M:%S")
                else:
                    p["wr_datetime"] = ""
            
            max_page = max(1, (total_count + limit - 1) // limit)
            return {
                "posts": posts,
                "total_count": total_count,
                "page": page,
                "max_page": max_page
            }
    except Exception as e:
        logger.error(f"Error searching posts in {write_table}: {e}")
        return {"posts": [], "total_count": 0, "page": 1, "max_page": 1}
    finally:
        if conn:
            conn.close()

def clean_html_content(content):
    """lux_merge.php 와 동일한 텍스트 가독성 개선 로직을 구현합니다."""
    if not content:
        return ""
    # 1. 줄바꿈 태그(<br>, <br />, <br/>, </p>, </div>)를 개행문자(\n)로 변환
    content = re.sub(r'(?i)(<br>|<br\s*/>|</p>|</div>)', '\n', content)
    # 2. HTML 태그 제거
    content = re.sub(r'<[^>]*>', '', content)
    # 3. 엔티티(&nbsp; 등) 디코딩
    content = html.unescape(content)
    # 4. 연속된 빈 줄 정리 (\n\n+ -> \n\n)
    content = re.sub(r'\n\n+', '\n\n', content.strip())
    return content

def merge_posts_content(bo_table, wr_ids):
    """지정된 wr_id들의 본문을 순서대로 결합하여 반환합니다. lux_merge.php와 가공 포맷을 맞춥니다."""
    if not bo_table or not wr_ids:
        return ""
    
    safe_bo_table = re.sub(r'[^a-zA-Z0-9_]', '', bo_table)
    write_table = f"{TABLE_PREFIX}{safe_bo_table}"
    
    try:
        ids = [int(x) for x in wr_ids]
    except Exception as e:
        logger.error(f"Invalid wr_ids: {wr_ids}, error: {e}")
        return ""
        
    if not ids:
        return ""
        
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 넘어온 ID 순서(화면의 드래그 앤 드롭 정렬된 순서)대로 데이터 추출
            placeholders = ",".join(["%s"] * len(ids))
            sql = f"""
                SELECT wr_id, wr_subject, wr_content, wr_name, ca_name 
                FROM {write_table} 
                WHERE wr_id IN ({placeholders})
            """
            cur.execute(sql, tuple(ids))
            rows = cur.fetchall()
            
            # wr_id 별 post 매핑 생성
            posts_map = {r["wr_id"]: r for r in rows}
            
            # 입력된 ids 순서(정렬된 순서)대로 병합
            merged_parts = []
            for wr_id in ids:
                post = posts_map.get(wr_id)
                if post:
                    subject = post["wr_subject"] or ""
                    content = post["wr_content"] or ""
                    wr_name = post["wr_name"] or ""
                    ca_name = post["ca_name"] or ""
                    
                    # lux_merge.php와 동일한 헤더 구성
                    post_header  = "==========================================================\n"
                    post_header += f"[{ca_name}] {subject} (작성자: {wr_name})\n"
                    post_header += "==========================================================\n\n"
                    
                    cleaned_content = clean_html_content(content)
                    
                    merged_parts.append(post_header + cleaned_content + "\n\n\n")
            return "".join(merged_parts)
    except Exception as e:
        logger.error(f"Error merging posts in {write_table}: {e}")
        return ""
    finally:
        if conn:
            conn.close()

def get_posts_details(bo_table, wr_ids):
    """지정된 wr_id들의 정보를 순서대로 가져옵니다."""
    if not bo_table or not wr_ids:
        return []
    
    safe_bo_table = re.sub(r'[^a-zA-Z0-9_]', '', bo_table)
    write_table = f"{TABLE_PREFIX}{safe_bo_table}"
    
    try:
        ids = [int(x) for x in wr_ids]
    except Exception as e:
        logger.error(f"Invalid wr_ids: {wr_ids}, error: {e}")
        return []
        
    if not ids:
        return []
        
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            sql = f"""
                SELECT wr_id, wr_subject, wr_content, wr_name, ca_name, wr_datetime, wr_link1 
                FROM {write_table} 
                WHERE wr_id IN ({placeholders})
            """
            cur.execute(sql, tuple(ids))
            rows = cur.fetchall()
            
            posts_map = {r["wr_id"]: r for r in rows}
            
            result = []
            for wr_id in ids:
                post = posts_map.get(wr_id)
                if post:
                    result.append({
                        "wr_id": wr_id,
                        "wr_subject": post["wr_subject"] or "",
                        "wr_content": clean_html_content(post["wr_content"] or ""),
                        "wr_name": post["wr_name"] or "",
                        "ca_name": post["ca_name"] or "",
                        "wr_datetime": str(post["wr_datetime"]) if post["wr_datetime"] else "",
                        "wr_link1": post["wr_link1"] or ""
                    })
            return result
    except Exception as e:
        logger.error(f"Error fetching posts details in {write_table}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_posts_raw_details(bo_table, wr_ids):
    """지정된 wr_id들의 정보를 가공하지 않고(HTML 태그 유지) 순서대로 가져옵니다."""
    if not bo_table or not wr_ids:
        return []
    
    safe_bo_table = re.sub(r'[^a-zA-Z0-9_]', '', bo_table)
    write_table = f"{TABLE_PREFIX}{safe_bo_table}"
    
    try:
        ids = [int(x) for x in wr_ids]
    except Exception as e:
        logger.error(f"Invalid wr_ids: {wr_ids}, error: {e}")
        return []
        
    if not ids:
        return []
        
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            sql = f"""
                SELECT wr_id, wr_subject, wr_content, wr_name, ca_name, wr_datetime, wr_link1, wr_option, wr_1 
                FROM {write_table} 
                WHERE wr_id IN ({placeholders})
            """
            cur.execute(sql, tuple(ids))
            rows = cur.fetchall()
            
            posts_map = {r["wr_id"]: r for r in rows}
            
            result = []
            for wr_id in ids:
                post = posts_map.get(wr_id)
                if post:
                    result.append({
                        "wr_id": wr_id,
                        "wr_subject": post["wr_subject"] or "",
                        "wr_content": post["wr_content"] or "",
                        "wr_name": post["wr_name"] or "",
                        "ca_name": post["ca_name"] or "",
                        "wr_datetime": str(post["wr_datetime"]) if post["wr_datetime"] else "",
                        "wr_link1": post["wr_link1"] or "",
                        "wr_option": post["wr_option"] or "",
                        "wr_1": post["wr_1"] or ""
                    })
            return result
    except Exception as e:
        logger.error(f"Error fetching raw posts details in {write_table}: {e}")
        return []
    finally:
        if conn:
            conn.close()

def _strip_4byte_chars(text):
    if not isinstance(text, str):
        return text
    # MySQL utf8 인코딩에서 지원하지 않는 4바이트 문자(이모지 등) 제거
    return re.sub(r'[^\u0000-\uFFFF]', '', text)

def register_post_to_gnuboard(
    bo_table, subject, content, ca_name, mb_id="admin", wr_name="최고관리자",
    wr_datetime=None, wr_1="", wr_link1="", wr_option=""
):
    """Registers or updates a post in the target Gnuboard table, matching PHP logic."""
    import datetime
    
    subject = _strip_4byte_chars(subject)
    content = _strip_4byte_chars(content)
    wr_name = _strip_4byte_chars(wr_name)
    
    safe_bo_table = re.sub(r'[^a-zA-Z0-9_]', '', bo_table)
    write_table = f"{TABLE_PREFIX}{safe_bo_table}"
    
    if not wr_datetime:
        wr_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # [1] 중복 데이터 체크 (제목 + 글쓴이 기준)
            check_sql = f"""
                SELECT wr_id, wr_datetime 
                FROM {write_table} 
                WHERE wr_subject = %s AND wr_name = %s
            """
            cur.execute(check_sql, (subject, wr_name))
            row = cur.fetchone()
            
            # [2] 중복된 글이 존재할 경우: 날짜 비교 후 갱신 or 스킵
            if row:
                stored_wr_id = row["wr_id"]
                stored_datetime = str(row["wr_datetime"])
                
                # 크롤링된 날짜($wr_datetime)가 DB에 저장된 날짜보다 최신인 경우에만 수정
                if wr_datetime > stored_datetime:
                    update_sql = f"""
                        UPDATE {write_table}
                        SET wr_content = %s,
                            wr_datetime = %s,
                            wr_last = %s,
                            wr_link1 = %s,
                            wr_1 = %s,
                            wr_option = %s
                        WHERE wr_id = %s
                    """
                    cur.execute(update_sql, (content, wr_datetime, now_str, wr_link1, wr_1, wr_option, stored_wr_id))
                    conn.commit()
                    logger.info(f" [Update] {subject} (ID: {stored_wr_id})")
                    return f"updated:{stored_wr_id}"
                else:
                    logger.info(f" [Skip] {subject} (No new update)")
                    return f"skipped:{stored_wr_id}"
            
            # [3] 중복이 없을 경우: 신규 등록 (INSERT)
            cur.execute(f"SELECT MIN(wr_num) as min_num FROM {write_table}")
            min_row = cur.fetchone()
            min_num = min_row["min_num"] if min_row and min_row["min_num"] is not None else 0
            wr_num = min_num - 1
            
            # 테이블 컬럼 정보를 동적으로 조회하여 스키마 불일치/strict 모드 방지
            cur.execute(f"DESCRIBE {write_table}")
            columns_meta = cur.fetchall()
            
            # 명시적으로 제공할 값들
            explicit_values = {
                'wr_num': wr_num,
                'ca_name': ca_name or "",
                'wr_subject': subject,
                'wr_content': content,
                'wr_link1': wr_link1,
                'mb_id': mb_id,
                'wr_name': wr_name,
                'wr_datetime': wr_datetime,
                'wr_last': now_str,
                'wr_ip': '127.0.0.1',
                'wr_1': wr_1 or "",
                'wr_option': wr_option,
            }
            
            # 그누보드 표준 필드들의 기본값 매핑
            standard_defaults = {
                'wr_reply': '',
                'wr_parent': 0,
                'wr_is_comment': 0,
                'wr_comment': 0,
                'wr_comment_reply': '',
                'wr_seo_title': '',
                'wr_option': '',
                'wr_link2': '',
                'wr_link1_hit': 0,
                'wr_link2_hit': 0,
                'wr_hit': 0,
                'wr_good': 0,
                'wr_nogood': 0,
                'wr_password': '',
                'wr_email': '',
                'wr_homepage': '',
                'wr_facebook_user': '',
                'wr_twitter_user': '',
                'wr_file': 0,
            }
            
            insert_data = {}
            for col in columns_meta:
                field_name = col['Field']
                
                # wr_id(auto_increment)는 INSERT에서 제외
                if field_name == 'wr_id' or 'auto_increment' in col.get('Extra', '').lower():
                    continue
                    
                if field_name in explicit_values:
                    insert_data[field_name] = explicit_values[field_name]
                elif field_name in standard_defaults:
                    insert_data[field_name] = standard_defaults[field_name]
                else:
                    # NOT NULL이며 기본값이 설정되어 있지 않은 컬럼(예: 아미나 스킨 as_re_mb 등 커스텀 필드)은 타입별 기본값 설정
                    is_not_null = col['Null'] == 'NO'
                    has_no_default = col['Default'] is None
                    
                    if is_not_null and has_no_default:
                        col_type = col['Type'].lower()
                        if 'int' in col_type or 'decimal' in col_type or 'float' in col_type or 'double' in col_type:
                            insert_data[field_name] = 0
                        elif 'date' in col_type or 'time' in col_type:
                            insert_data[field_name] = now_str
                        else:
                            insert_data[field_name] = ''
            
            # 동적 INSERT 쿼리 빌드 및 실행
            set_clauses = []
            values = []
            for field, val in insert_data.items():
                set_clauses.append(f"`{field}` = %s")
                values.append(val)
                
            insert_sql = f"INSERT INTO `{write_table}` SET {', '.join(set_clauses)}"
            cur.execute(insert_sql, tuple(values))
            new_wr_id = cur.lastrowid
            
            # 부모 아이디에 UPDATE
            cur.execute(f"UPDATE {write_table} SET wr_parent = %s WHERE wr_id = %s", (new_wr_id, new_wr_id))
            
            # 새글 INSERT
            cur.execute(
                "INSERT INTO g5_board_new (bo_table, wr_id, wr_parent, bn_datetime, mb_id) VALUES (%s, %s, %s, %s, %s)",
                (bo_table, new_wr_id, new_wr_id, now_str, mb_id)
            )
            
            # 게시글 1 증가
            cur.execute(
                "UPDATE g5_board SET bo_count_write = bo_count_write + 1 WHERE bo_table = %s",
                (bo_table,)
            )
            
            conn.commit()
            logger.info(f" [Insert] {subject} (ID: {new_wr_id})")
            return f"inserted:{new_wr_id}"
            
    except Exception as e:
        logger.error(f"Error registering post to {bo_table}: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

class GnuboardDB:
    def get_boards(self):
        return get_boards()
        
    def get_posts_count(self, bo_table, stx=""):
        safe_bo_table = re.sub(r'[^a-zA-Z0-9_]', '', bo_table)
        write_table = f"{TABLE_PREFIX}{safe_bo_table}"
        where_clause = "WHERE wr_is_comment = 0"
        params = []
        if stx and stx.strip():
            keywords = stx.strip().split()
            search_clauses = []
            for word in keywords:
                if word.strip():
                    search_clauses.append("wr_subject LIKE %s")
                    params.append(f"%{word.strip()}%")
            if search_clauses:
                where_clause += " AND " + " AND ".join(search_clauses)
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                count_sql = f"SELECT COUNT(*) as cnt FROM {write_table} {where_clause}"
                cur.execute(count_sql, tuple(params))
                count_row = cur.fetchone()
                return count_row["cnt"] if count_row else 0
        except Exception as e:
            logger.error(f"Error get_posts_count: {e}")
            return 0
        finally:
            if conn:
                conn.close()
                
    def search_posts(self, bo_table, stx="", sort="wr_id", page=1, page_rows=20):
        res = search_posts(bo_table, stx=stx, sort=sort, page_rows=page_rows, page=page)
        return res.get("posts", [])
        
    def get_posts_details(self, bo_table, wr_ids):
        return get_posts_details(bo_table, wr_ids)
        
    def get_posts_raw_details(self, bo_table, wr_ids):
        return get_posts_raw_details(bo_table, wr_ids)
        
    def register_post_to_gnuboard(
        self, bo_table, title, content, original_url="", original_datetime=None, ip="127.0.0.1"
    ):
        return register_post_to_gnuboard(
            bo_table=bo_table,
            subject=title,
            content=content,
            ca_name="",
            mb_id="admin",
            wr_name="최고관리자",
            wr_datetime=original_datetime,
            wr_1="",
            wr_link1=original_url
        )
