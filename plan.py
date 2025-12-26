from typing import Dict
from context_manager import ContextManager
from config import LLM_CONFIG
import requests
import json
import logging

logger = logging.getLogger(__name__)


def save_task_to_rag(context_manager: ContextManager, user_task: str, plan: Dict):
    """保存任务到tasks集合"""
    context_manager.add_to_rag(
        user_task,
        {"type": "task", "plan": json.dumps(plan)},
        collection="tasks"
    )


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
        
        # 保存完整的LLM响应（包含思考过程）
        plan["llm_response"] = response
        
        # 将匹配的规则信息添加到plan中
        plan["matched_rules"] = []
        if rag_knowledge:
            for ctx in rag_knowledge:
                plan["matched_rules"].append({
                    "text": ctx.get("text", ""),
                    "metadata": ctx.get("metadata", {})
                })
        
        plan["matched_equipment"] = []
        if rag_equipment:
            for ctx in rag_equipment:
                plan["matched_equipment"].append({
                    "text": ctx.get("text", ""),
                    "metadata": ctx.get("metadata", {})
                })
        
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
        
        # 尝试提取JSON部分（可能包含在代码块中）
        # 先尝试匹配 ```json ... ``` 格式
        json_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
        if json_block_match:
            try:
                plan = json.loads(json_block_match.group(1))
                if "steps" not in plan:
                    plan["steps"] = []
                if "estimated_steps" not in plan:
                    plan["estimated_steps"] = len(plan.get("steps", []))
                
                # 提取JSON之前的思考过程
                thinking_part = response[:json_block_match.start()].strip()
                
                # 如果goal字段被截断、包含<redacted>标记，或者思考过程存在，则合并
                goal_value = str(plan.get("goal", ""))
                if "<redacted" in goal_value.lower() or (thinking_part and len(goal_value) < len(thinking_part)):
                    # 用完整的思考过程替换或补充goal
                    if thinking_part:
                        # 如果goal中有内容（即使被截断），保留它
                        if goal_value and "<redacted" not in goal_value.lower():
                            plan["goal"] = thinking_part + "\n\n" + goal_value
                        else:
                            plan["goal"] = thinking_part
                    elif goal_value:
                        plan["goal"] = goal_value
                elif thinking_part and not goal_value:
                    # 如果goal为空但有思考过程，使用思考过程
                    plan["goal"] = thinking_part
                
                return plan
            except Exception as e:
                logger.warning(f"解析JSON代码块失败: {e}")
                pass
        
        # 尝试匹配普通的JSON对象（贪婪匹配，匹配最后一个完整的JSON对象）
        # 从后往前找，找到最后一个完整的JSON对象
        json_match = None
        for match in re.finditer(r'\{[\s\S]*\}', response):
            try:
                # 尝试解析，如果成功则保留
                test_json = json.loads(match.group())
                json_match = match
            except:
                continue
        
        if json_match:
            try:
                plan = json.loads(json_match.group())
                if "steps" not in plan:
                    plan["steps"] = []
                if "estimated_steps" not in plan:
                    plan["estimated_steps"] = len(plan.get("steps", []))
                
                # 提取JSON之前的思考过程
                thinking_part = response[:json_match.start()].strip()
                
                # 如果goal字段被截断、包含<redacted>标记，或者思考过程存在，则合并
                goal_value = str(plan.get("goal", ""))
                if "<redacted" in goal_value.lower() or (thinking_part and len(goal_value) < len(thinking_part)):
                    # 用完整的思考过程替换或补充goal
                    if thinking_part:
                        # 如果goal中有内容（即使被截断），保留它
                        if goal_value and "<redacted" not in goal_value.lower():
                            plan["goal"] = thinking_part + "\n\n" + goal_value
                        else:
                            plan["goal"] = thinking_part
                    elif goal_value:
                        plan["goal"] = goal_value
                elif thinking_part and not goal_value:
                    # 如果goal为空但有思考过程，使用思考过程
                    plan["goal"] = thinking_part
                
                return plan
            except Exception as e:
                logger.warning(f"解析JSON对象失败: {e}")
                pass
        
        # Fallback: 关键词匹配
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
            "goal": response,  # 返回完整响应，不再截断
            "steps": steps,
            "estimated_steps": len(steps)
        }
