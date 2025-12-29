from typing import Dict
from context_manager import ContextManager
from config import LLM_CONFIG
from work.tools import BufferFilterTool, ElevationFilterTool, SlopeFilterTool, VegetationFilterTool
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
        self.tools = {
            "buffer_filter_tool": BufferFilterTool(),
            "elevation_filter_tool": ElevationFilterTool(),
            "slope_filter_tool": SlopeFilterTool(),
            "vegetation_filter_tool": VegetationFilterTool()
        }

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

        tools_schema = []
        for tool_name, tool in self.tools.items():
            schema = tool.get_schema()
            tools_schema.append(json.dumps(schema, ensure_ascii=False, indent=2))

        tools_schema_text = "\n\n".join(tools_schema)
        prompt_with_schema = f"{prompt}\n\n## 工具参数规范（动态获取）\n{tools_schema_text}"

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
            {"role": "system", "content": prompt_with_schema},
            {"role": "user", "content": f"任务: {user_task}{knowledge_text}{equipment_text}{tasks_text}"}
        ]

        response = self._call_llm(messages)
        logger.info(f"Plan阶段 - LLM响应长度: {len(response)}")
        logger.info(f"Plan阶段 - LLM响应前500字符: {response[:500]}")

        plan = self._parse_plan(response)

        if "sub_plans" in plan:
            logger.info(f"Plan阶段 - 多任务模式，子计划数: {len(plan.get('sub_plans', []))}")
            for i, sub_plan in enumerate(plan.get('sub_plans', [])):
                logger.info(f"Plan阶段 - 子计划[{i+1}] 单位: {sub_plan.get('unit', 'N/A')}, 步骤数: {len(sub_plan.get('steps', []))}")
        else:
            logger.info(f"Plan阶段 - 单任务模式，解析后的步骤数: {len(plan.get('steps', []))}")
            logger.info(f"Plan阶段 - 步骤类型: {[s.get('type', 'N/A') for s in plan.get('steps', [])]}")
        plan["llm_response"] = response

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

        json_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
        if json_block_match:
            try:
                plan = json.loads(json_block_match.group(1))
                
                if "sub_plans" in plan:
                    for sub_plan in plan.get("sub_plans", []):
                        if "steps" not in sub_plan:
                            sub_plan["steps"] = []
                else:
                    if "steps" not in plan:
                        plan["steps"] = []
                    if "estimated_steps" not in plan:
                        plan["estimated_steps"] = len(plan.get("steps", []))

                thinking_part = response[:json_block_match.start()].strip()

                goal_value = str(plan.get("goal", ""))
                if "<redacted" in goal_value.lower() or (thinking_part and len(goal_value) < len(thinking_part)):
                    if thinking_part:
                        if goal_value and "<redacted" not in goal_value.lower():
                            plan["goal"] = thinking_part + "\n\n" + goal_value
                        else:
                            plan["goal"] = thinking_part
                    elif goal_value:
                        plan["goal"] = goal_value
                elif thinking_part and not goal_value:
                    plan["goal"] = thinking_part

                return plan
            except Exception as e:
                logger.warning(f"解析JSON代码块失败: {e}")
                pass

        json_match = None
        for match in re.finditer(r'\{[\s\S]*\}', response):
            try:
                test_json = json.loads(match.group())
                json_match = match
            except:
                continue

        if json_match:
            try:
                plan = json.loads(json_match.group())
                
                if "sub_plans" in plan:
                    for sub_plan in plan.get("sub_plans", []):
                        if "steps" not in sub_plan:
                            sub_plan["steps"] = []
                else:
                    if "steps" not in plan:
                        plan["steps"] = []
                    if "estimated_steps" not in plan:
                        plan["estimated_steps"] = len(plan.get("steps", []))

                thinking_part = response[:json_match.start()].strip()

                goal_value = str(plan.get("goal", ""))
                if "<redacted" in goal_value.lower() or (thinking_part and len(goal_value) < len(thinking_part)):
                    if thinking_part:
                        if goal_value and "<redacted" not in goal_value.lower():
                            plan["goal"] = thinking_part + "\n\n" + goal_value
                        else:
                            plan["goal"] = thinking_part
                    elif goal_value:
                        plan["goal"] = goal_value
                elif thinking_part and not goal_value:
                    plan["goal"] = thinking_part

                return plan
            except Exception as e:
                logger.warning(f"解析JSON对象失败: {e}")
                pass

        steps = []
        if "缓冲区" in response or "距离" in response:
            steps.append({"step_id": 1, "description": "根据建筑和道路距离筛选空地", "type": "buffer", "params": {}})
        if "高程" in response or "海拔" in response:
            steps.append({"step_id": len(steps) + 1, "description": "根据高程范围筛选", "type": "elevation", "params": {}})
        if "坡度" in response or "倾斜" in response:
            steps.append({"step_id": len(steps) + 1, "description": "根据坡度范围筛选", "type": "slope", "params": {}})
        if "植被" in response or "草地" in response or "林地" in response or "树木" in response or "耕地" in response or "裸地" in response or "水体" in response or "湿地" in response or "苔原" in response or "植被" in response or "稀疏植被" in response or "永久性水体" in response or "雪和冰" in response:
            steps.append({"step_id": len(steps) + 1, "description": "根据植被类型筛选", "type": "vegetation", "params": {}})

        return {
            "task": "",
            "goal": response,
            "steps": steps,
            "estimated_steps": len(steps)
        }
