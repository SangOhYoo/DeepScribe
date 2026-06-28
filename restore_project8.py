"""
Project 8 (동정-스미래) Restoration Script
Restores:
  - Project record with system_prompt, overall_plot, positive/negative prompts
  - 5 Characters from recovered_project8_characters.json (히로시, 스미래, 후미애, 하숙집 할머니, 타카시)
  - 12 Scenario Nodes (기/승/전/결 structure)
"""
import sys
import json
sys.path.append('d:/DeepScribe/abyss_writer')
from models import init_db, Project, Character, ScenarioNode
from datetime import datetime

session = init_db()

# Check if project 8 already exists
existing = session.query(Project).filter(Project.id == 8).first()
if existing:
    print(f"[WARNING] Project 8 already exists: {existing.title}. Aborting to prevent duplication.")
    sys.exit(0)

# ===== 1. Create Project =====
overall_plot = (
    "30대 중반 미망인 스미래의 집으로 20대 초반 대학생 히로시가 하숙생으로 들어오며 벌어지는 관능적인 로맨스 소설입니다. "
    "정숙한 미망인의 가면 속에 숨겨진 스미래의 강렬한 성적 결핍과, 순진하지만 거부할 수 없는 본능에 흔들리는 하숙생 히로시 "
    "사이의 위태로운 관계가 폭우 속에서 점차 파국으로 치달으며 전개됩니다."
)

system_prompt = (
    "당신은 심리묘사, 감정의 결, 그리고 인물 간 역학관계에 능통한 한국어 소설 작가입니다. "
    "지금부터 당신은 '금단의 갈증'이라는 제목의 성인 소설을 집필합니다. "
    "인물의 내면 심리, 육체적 감각, 금기된 욕망과 도덕적 갈등을 섬세하게 엮어서 "
    "독자의 몰입을 극대화하는 생생하고 감각적인 산문체로 작성하십시오."
)

positive_prompt = (
    "심리적 갈등의 미세한 결, 감각적인 묘사, 금기된 욕망의 긴장감, "
    "정숙함과 탐욕 사이의 이중성, 억압된 본능의 폭발, 비유적이고 시적인 문체"
)

negative_prompt = (
    "설명적이고 딱딱한 문체, 단순한 포르노그래피, 감정 없는 행위 묘사, "
    "캐릭터 성격과 무관한 대사, 현실성 없는 전개"
)

# Use raw SQL to insert with specific ID
from sqlalchemy import text
with session.bind.begin() as conn:
    conn.execute(text("""
        INSERT INTO projects (id, title, genre, status, system_prompt, overall_plot, positive_prompt, negative_prompt, created_at, updated_at)
        VALUES (:id, :title, :genre, :status, :system_prompt, :overall_plot, :positive_prompt, :negative_prompt, :created_at, :updated_at)
    """), {
        "id": 8,
        "title": "동정-스미래",
        "genre": "관능",
        "status": "Draft",
        "system_prompt": system_prompt,
        "overall_plot": overall_plot,
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "created_at": datetime(2026, 6, 9, 0, 0, 0),
        "updated_at": datetime.utcnow()
    })
print("[OK] Project 8 created.")

# ===== 2. Restore Characters =====
with open("d:/DeepScribe/recovered_project8_characters.json", "r", encoding="utf-8") as f:
    chars_data = json.load(f)

# Add 타카시 (missing from JSON but present in extracted data)
if "타카시" not in chars_data:
    chars_data["타카시"] = {
        "name": "타카시",
        "relations": "male_sub",
        "personality": "개방적이고 쾌락주의적이며, 격식보다는 효율과 본능을 중시하는 현대적인 성격이다.",
        "background": "전통적인 가치관이나 도덕적 굴레에 얽매이지 않는 도쿄 토박이로, 히로시가 가진 도덕적 강박을 비웃는 자유로운 영혼의 소유자이다.",
        "character_relations": "히로시의 대학 동기로서 그에게 현대적인 이성 관계의 방식을 조언하며, 히로시가 금기된 욕망에 눈을 뜨게 만드는 심리적 촉매제 역할을 한다.",
        "speech_style": "격식 없는 반말과 가벼운 말투를 사용하며, 냉소적인 농담과 유행어를 섞어 말하는 경향이 있다.",
    }

for char_key, char_data in chars_data.items():
    new_char = Character(
        project_id=8,
        name=char_data.get("name", char_key),
        relations=char_data.get("relations", "other"),
        personality=char_data.get("personality", ""),
        background=char_data.get("background", ""),
        character_relations=char_data.get("character_relations", ""),
        speech_style=char_data.get("speech_style", ""),
        physical_signature=char_data.get("physical_signature"),
        psychological_trigger=char_data.get("psychological_trigger"),
        behavioral_quirks=char_data.get("behavioral_quirks"),
        secret_taboo=char_data.get("secret_taboo"),
        signature_quotes=char_data.get("signature_quotes"),
    )
    session.add(new_char)
session.commit()
print(f"[OK] {len(chars_data)} characters restored.")

# ===== 3. Restore Scenario Nodes =====
# Based on previous output.txt which showed 12 nodes:
scenario_nodes = [
    # 기 (起 - 도입) - Introduction
    {"stage": "기 (起 - 도입)", "node_index": 1, "title": "금기의 공간, 하숙집 입성",
     "content": "도쿄 유학생 히로시가 엄격한 분위기의 스미래 하숙집에 입성한다. 하숙집 할머니의 냉혹한 규율 아래 정숙한 미망인 스미래와 그녀의 어린 딸 후미애를 만나며, 낯선 공간에서의 새로운 생활이 시작된다. 히로시는 스미래의 청초한 외모에 첫인상부터 강렬한 인상을 받지만, 도덕적 경계선을 넘지 않으려 스스로를 경계한다.",
     "commit_message": "자동 생성 시나리오"},
    {"stage": "기 (起 - 도입)", "node_index": 2, "title": "은밀한 호의와 본능의 각성",
     "content": "스미래가 히로시에게 은밀한 호의를 보이기 시작한다. 밤늦은 시간 차를 가져다주거나, 빨래를 챙기며 우연히 신체 접촉이 일어난다. 히로시는 스미래의 의도를 의심하면서도 자신의 내면에서 끓어오르는 본능적 끌림을 자각한다. 할머니의 엄격한 감시 속에서 두 사람 사이에 미세한 긴장감이 형성된다.",
     "commit_message": "자동 생성 시나리오"},
    {"stage": "기 (起 - 도입)", "node_index": 3, "title": "순결한 기억과 육체적 갈망의 충돌",
     "content": "히로시는 고향에 남겨둔 첫사랑 아유꼬를 떠올리며 도덕적 갈등에 시달린다. 순결한 사랑의 기억과 스미래가 불러일으키는 강렬한 육체적 갈망 사이에서 괴로워하며, 자신이 어떤 인간인지에 대한 정체성의 혼란을 겪기 시작한다.",
     "commit_message": "자동 생성 시나리오"},

    # 승 (承 - 전개) - Development
    {"stage": "승 (承 - 전개)", "node_index": 4, "title": "만원 전철, 무언의 약속",
     "content": "출퇴근 만원 전철에서 우연히 마주친 히로시와 스미래. 밀착된 공간에서 서로의 체온과 호흡을 느끼며, 말로는 하지 못하는 무언의 약속이 오간다. 스미래의 손끝이 히로시의 손등에 닿는 찰나, 두 사람 모두 더 이상 부정할 수 없는 욕망의 신호를 교환한다.",
     "commit_message": "자동 생성 시나리오"},
    {"stage": "승 (承 - 전개)", "node_index": 5, "title": "신사의 숲, 첫 번째 금기를 깨다",
     "content": "인적이 드문 신사의 숲에서 히로시와 스미래는 처음으로 금기의 선을 넘는다. 3년간 억눌려왔던 스미래의 결핍이 폭발하고, 히로시 역시 도덕의 감옥에서 잠시 해방된다. 격정적인 첫 만남 이후 두 사람은 강렬한 죄책감과 동시에 중독적인 쾌감을 경험한다.",
     "commit_message": "자동 생성 시나리오"},
    {"stage": "승 (承 - 전개)", "node_index": 6, "title": "이중생활의 시작과 탐닉의 가속",
     "content": "히로시는 모범생과 스미래의 밀회 상대라는 이중생활을 시작한다. 대학에서는 타카시의 냉소적인 조언에 시달리고, 하숙집에서는 할머니의 눈을 피해 스미래와 비밀스러운 만남을 이어간다. 탐닉은 점점 깊어지고, 두 사람의 관계는 단순한 육체적 관계를 넘어 감정적으로도 복잡하게 얽히기 시작한다.",
     "commit_message": "자동 생성 시나리오"},

    # 전 (轉 - 위기/절정) - Crisis/Climax
    {"stage": "전 (轉 - 위기/절정)", "node_index": 7, "title": "무더운 여름밤의 광적인 정사",
     "content": "무더운 여름밤, 할머니가 절에 간 틈을 타 히로시와 스미래는 하숙집에서 광적인 밀회를 벌인다. 억눌려왔던 모든 갈증이 폭발하며, 스미래의 본성이 완전히 드러나는 밤. 그러나 이 밤이 끝난 후 히로시는 자신이 돌이킬 수 없는 곳까지 왔음을 깨닫는다.",
     "commit_message": "자동 생성 시나리오"},
    {"stage": "전 (轉 - 위기/절정)", "node_index": 8, "title": "사춘기 후미애의 동경과 심리적 압박",
     "content": "후미애가 히로시에 대한 이성적 감정을 자각하기 시작한다. 히로시를 '선생님'으로 부르며 따르던 순수한 동경이 사춘기적 연모로 변질되어 가고, 히로시는 후미애의 시선에서 또 다른 형태의 죄책감을 느낀다. 어머니와 딸 사이에서 히로시의 심리적 압박이 극에 달한다.",
     "commit_message": "자동 생성 시나리오"},
    {"stage": "전 (轉 - 위기/절정)", "node_index": 9, "title": "폭우 속의 밀회와 파국의 목격",
     "content": "폭우가 쏟아지는 밤, 히로시와 스미래의 격정적인 밀회가 벌어진다. 그러나 이 결정적인 순간에 후미애가 두 사람의 관계를 목격하게 된다. 후미애의 비명과 눈물, 스미래의 공포, 히로시의 절망이 교차하며 모든 것이 무너지기 시작한다.",
     "commit_message": "자동 생성 시나리오"},

    # 결 (結 - 결말) - Conclusion
    {"stage": "결 (結 - 결말)", "node_index": 10, "title": "수치심의 도피와 무너진 질서",
     "content": "진실이 드러난 후 하숙집의 질서는 완전히 무너진다. 할머니의 분노와 심판, 스미래의 수치심과 자기혐오, 후미애의 트라우마. 히로시는 도피하듯 하숙집을 나서지만, 떠나는 그의 발걸음은 해방이 아닌 더 깊은 자기파괴로 향한다.",
     "commit_message": "자동 생성 시나리오"},
    {"stage": "결 (結 - 결말)", "node_index": 11, "title": "미숙한 방어기제와 고독한 퇴장",
     "content": "히로시는 대학 기숙사로 돌아가지만, 스미래와의 기억은 지울 수 없는 낙인처럼 그를 따라다닌다. 타카시에게조차 진실을 말하지 못하고, 아유꼬에게 연락할 자격도 없다고 느끼며 완전한 고립 속에 빠진다. 미숙한 방어기제로 일상을 유지하려 하지만, 내면은 이미 돌이킬 수 없이 변해버렸다.",
     "commit_message": "자동 생성 시나리오"},
    {"stage": "결 (結 - 결말)", "node_index": 12, "title": "초겨울의 재회, 남겨진 잔혹한 상처",
     "content": "초겨울, 히로시는 우연히 스미래와 재회한다. 시간이 흘렀지만 두 사람 사이의 상처는 전혀 아물지 않았다. 스미래의 눈에는 여전히 결핍의 그림자가 서려 있고, 히로시는 그녀를 마주한 순간 자신의 본능이 여전히 살아있음을 깨닫는다. 그들의 이야기는 끝나지 않았으며, 남겨진 상처는 잔혹하게 계속된다.",
     "commit_message": "자동 생성 시나리오"},
]

for node_data in scenario_nodes:
    new_node = ScenarioNode(
        project_id=8,
        stage=node_data["stage"],
        node_index=node_data["node_index"],
        title=node_data["title"],
        content=node_data["content"],
        commit_message=node_data["commit_message"],
        created_at=datetime(2026, 6, 9, 0, 0, 0)
    )
    session.add(new_node)
session.commit()
print(f"[OK] {len(scenario_nodes)} scenario nodes restored.")

# ===== 4. Verify =====
proj = session.query(Project).filter(Project.id == 8).first()
chars = session.query(Character).filter(Character.project_id == 8).all()
nodes = session.query(ScenarioNode).filter(ScenarioNode.project_id == 8).all()
print(f"\n=== VERIFICATION ===")
print(f"Project: [{proj.id}] {proj.title} ({proj.genre})")
print(f"Characters: {len(chars)}")
for c in chars:
    print(f"  - {c.name} ({c.relations})")
print(f"Scenario Nodes: {len(nodes)}")
for n in nodes:
    print(f"  - [{n.node_index}] {n.stage}: {n.title}")

print("\n[DONE] Project 8 restoration complete!")
