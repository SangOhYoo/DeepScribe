from typing import List, Dict, Any
from models import Character, ScenarioNode

class ContextRouter:
    """
    Context Window Optimization: dynamically route/inject only the most relevant 
    profiles and previous scenario summaries into the prompt.
    """
    def __init__(self, db_session):
        self.db = db_session

    def build_context(self, project_id: int, current_scene_desc: str, max_history_nodes: int = 3, target_node_id: int = None) -> str:
        """
        Builds optimized context by fetching only relevant characters
        and the last N scenario nodes based on the current context tree.
        """
        # 1. Fetch relevant characters (Simple keyword matching for optimization)
        characters = self.db.query(Character).filter(Character.project_id == project_id).all()
        relevant_chars = []
        for char in characters:
            if char.name in current_scene_desc:
                relevant_chars.append(char)
        
        # If no explicit match, include all (or top few) for safety
        if not relevant_chars:
            relevant_chars = characters[:3]

        char_context = "[Character Profiles]\n"
        for char in relevant_chars:
            char_context += f"- {char.name}: {char.personality} / {char.speech_style}\n"
            char_context += f"  Background: {char.background}\n"

        # 2. Fetch all latest outline nodes (stage != "Development") in chronological order
        from sqlalchemy import func
        STAGE_ORDER = {
            "기 (起 - 도입)": 0,
            "승 (承 - 전개)": 1,
            "전 (轉 - 위기/절정)": 2,
            "결 (結 - 결말)": 3
        }

        try:
            subq = self.db.query(
                ScenarioNode.stage,
                ScenarioNode.node_index,
                func.max(ScenarioNode.created_at).label('max_created')
            ).filter(
                ScenarioNode.project_id == project_id,
                ScenarioNode.stage != "Development"
            ).group_by(
                ScenarioNode.stage,
                ScenarioNode.node_index
            ).subquery()

            all_outline_nodes = self.db.query(ScenarioNode).join(
                subq,
                (ScenarioNode.stage == subq.c.stage) &
                (ScenarioNode.node_index == subq.c.node_index) &
                (ScenarioNode.created_at == subq.c.max_created)
            ).filter(
                ScenarioNode.project_id == project_id
            ).all()

            all_outline_nodes.sort(key=lambda n: (STAGE_ORDER.get(n.stage, 99), n.node_index or 0))
        except Exception as e:
            print("Error querying outline nodes for context:", e)
            all_outline_nodes = []

        # Find preceding nodes relative to target_node_id
        preceding_nodes = []
        if target_node_id:
            curr_node = self.db.query(ScenarioNode).filter(ScenarioNode.id == target_node_id).first()
            if curr_node:
                curr_stage_order = STAGE_ORDER.get(curr_node.stage, 99)
                curr_index = curr_node.node_index or 0
                
                for node in all_outline_nodes:
                    node_stage_order = STAGE_ORDER.get(node.stage, 99)
                    node_index = node.node_index or 0
                    if (node_stage_order < curr_stage_order) or (node_stage_order == curr_stage_order and node_index < curr_index):
                        preceding_nodes.append(node)
        else:
            # Fallback: take all outline nodes
            preceding_nodes = all_outline_nodes

        # Take last N preceding nodes
        preceding_nodes = preceding_nodes[-max_history_nodes:]
        
        history_context = "[Previous Scenario History]\n"
        for parent_node in preceding_nodes:
            # Find finalized/latest detailed scene for this outline node
            detailed_scenes = self.db.query(ScenarioNode).filter(
                ScenarioNode.project_id == project_id,
                ScenarioNode.stage == "Development",
                ScenarioNode.parent_id == parent_node.id
            ).order_by(ScenarioNode.created_at.desc()).all()
            
            scene_text = ""
            if detailed_scenes:
                finalized_node = None
                for ds in detailed_scenes:
                    if ds.node_index == 1:
                        finalized_node = ds
                        break
                if not finalized_node:
                    finalized_node = detailed_scenes[0]
                scene_text = finalized_node.content or ""
            else:
                scene_text = parent_node.content or ""
                
            stage_short = parent_node.stage[0] if parent_node.stage else "씬"
            history_context += f"- Stage: {stage_short}-{parent_node.node_index} | {scene_text[:150].strip()}...\n"

        final_context = f"{char_context}\n{history_context}"
        return final_context
