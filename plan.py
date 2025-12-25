from typing import Dict
from context_manager import ContextManager
from config import LLM_CONFIG
import requests
import json


class PlanModule:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
    
    def generate_plan(self, user_task: str) -> Dict:
        rag_tasks = self.context_manager.load_dynamic_context(
            user_task,
            collection="tasks"
        )
        
        rag_knowledge = self.context_manager.load_dynamic_context(
            user_task,
            collection="knowledge",
            top_k=3
        )
        
        rag_equipment = self.context_manager.load_dynamic_context(
            user_task,
            collection="equipment",
            top_k=3
        )
        
        prompt = self.context_manager.load_static_context("plan_prompt")
        
        knowledge_text = ""
        if rag_knowledge:
            knowledge_text = "\n相关部署规则:\n" + "\n".join([ctx.get("text", "") for ctx in rag_knowledge])
        
        equipment_text = ""
        if rag_equipment:
            equipment_text = "\n相关装备信息（含射程）:\n" + "\n".join([ctx.get("text", "") for ctx in rag_equipment])
        
        tasks_text = ""
        if rag_tasks:
            tasks_text = "\n相关历史任务:\n" + json.dumps(rag_tasks, ensure_ascii=False)
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"任务: {user_task}{knowledge_text}{equipment_text}{tasks_text}"}
        ]
        
        response = self._call_llm(messages)
        plan = self._parse_plan(response)
        
        self.context_manager.add_to_rag(
            user_task,
            {"type": "task", "plan": json.dumps(plan)},
            collection="tasks"
        )
        
        return plan
    
    def _call_llm(self, messages: list) -> str:
        payload = {
            **LLM_CONFIG,
            "messages": messages
        }
        
        response = requests.post(LLM_CONFIG["api_endpoint"], json=payload, timeout=LLM_CONFIG.get("timeout", 120))
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    def _parse_plan(self, response: str) -> Dict:
        import re
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                plan = json.loads(json_match.group())
                if "steps" not in plan:
                    plan["steps"] = []
                if "estimated_steps" not in plan:
                    plan["estimated_steps"] = len(plan.get("steps", []))
                return plan
            except:
                pass
        
        steps = []
        if "缓冲区" in response or "距离" in response:
            steps.append({"step_id": 1, "description": "根据建筑和道路距离筛选空地", "type": "buffer"})
        if "高程" in response or "海拔" in response:
            steps.append({"step_id": len(steps) + 1, "description": "根据高程范围筛选", "type": "elevation"})
        if "坡度" in response or "倾斜" in response:
            steps.append({"step_id": len(steps) + 1, "description": "根据坡度范围筛选", "type": "slope"})
        if "植被" in response or "草地" in response or "林地" in response or "树木" in response or "耕地" in response or "裸地" in response or "水体" in response:
            steps.append({"step_id": len(steps) + 1, "description": "根据植被类型筛选", "type": "vegetation"})
        
        return {
            "task": "",
            "goal": response[:200],
            "steps": steps,
            "estimated_steps": len(steps)
        }
