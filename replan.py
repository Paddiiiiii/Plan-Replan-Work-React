from typing import Dict, List
from context_manager import ContextManager
from config import LLM_CONFIG
from work.tools import BufferFilterTool, ElevationFilterTool, SlopeFilterTool, VegetationFilterTool
import requests
import json
import logging

logger = logging.getLogger(__name__)


class ReplanModule:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        # 初始化工具实例以获取schema信息
        self.tools = {
            "buffer_filter_tool": BufferFilterTool(),
            "elevation_filter_tool": ElevationFilterTool(),
            "slope_filter_tool": SlopeFilterTool(),
            "vegetation_filter_tool": VegetationFilterTool()
        }
    
    def should_replan(self, work_result: Dict) -> bool:
        if not work_result.get("success", False):
            return True
        return False
    
    def replan(self, original_plan: Dict, work_result: Dict, available_tools: List[str]) -> Dict:
        prompt_template = self.context_manager.load_static_context("replan_prompt")
        
        # 添加工具schema信息，确保replan部分了解工具的具体参数结构
        tools_schema = []
        for tool_name, tool in self.tools.items():
            schema = tool.get_schema()
            tools_schema.append(json.dumps(schema, ensure_ascii=False, indent=2))
        
        tools_schema_text = "\n\n".join(tools_schema)
        prompt_with_schema = f"{prompt_template}\n\n## 工具参数规范（动态获取）\n{tools_schema_text}"
        
        # 检索装备信息（含射程），用于重新规划时考虑射程因素
        plan_text = json.dumps(original_plan, ensure_ascii=False)
        rag_equipment = self.context_manager.load_dynamic_context(
            plan_text,
            collection="equipment",
            top_k=3
        )
        
        plan_str = json.dumps(original_plan, ensure_ascii=False, indent=2)
        result_str = json.dumps(work_result, ensure_ascii=False, indent=2)
        
        equipment_text = ""
        if rag_equipment:
            equipment_text = "\n\n相关装备信息（含射程）:\n" + "\n".join([ctx.get("text", "") for ctx in rag_equipment])
        
        user_content = f"请根据原计划和执行结果重写 JSON 计划\n\n原计划:\n{plan_str}\n\n执行结果:\n{result_str}{equipment_text}"
        
        messages = [
            {"role": "system", "content": prompt_with_schema},
            {"role": "user", "content": user_content}
        ]
        
        response = self._call_llm(messages)
        new_plan = self._parse_plan(response)
        
        return new_plan
    
    def replan_with_feedback(self, original_plan: Dict, feedback: str, available_tools: List[str]) -> Dict:
        try:
            logger.info(f"开始重新规划，反馈: {feedback[:50]}...")
            
            prompt_template = self.context_manager.load_static_context("replan_prompt")
            
            # 添加工具schema信息，确保replan部分了解工具的具体参数结构
            tools_schema = []
            for tool_name, tool in self.tools.items():
                schema = tool.get_schema()
                tools_schema.append(json.dumps(schema, ensure_ascii=False, indent=2))
            
            tools_schema_text = "\n\n".join(tools_schema)
            prompt_with_schema = f"{prompt_template}\n\n## 工具参数规范（动态获取）\n{tools_schema_text}"
            
            # 检索装备信息（含射程），用于重新规划时考虑射程因素
            plan_text = json.dumps(original_plan, ensure_ascii=False)
            rag_equipment = self.context_manager.load_dynamic_context(
                plan_text,
                collection="equipment",
                top_k=3
            )
            
            plan_str = json.dumps(original_plan, ensure_ascii=False, indent=2)
            
            equipment_text = ""
            if rag_equipment:
                equipment_text = "\n\n相关装备信息（含射程）:\n" + "\n".join([ctx.get("text", "") for ctx in rag_equipment])
            
            user_content = f"请根据原计划和用户反馈重写 JSON 计划\n\n原计划:\n{plan_str}\n\n用户反馈:\n{feedback}{equipment_text}"
            
            messages = [
                {"role": "system", "content": prompt_with_schema},
                {"role": "user", "content": user_content}
            ]
            
            logger.info("调用LLM生成新计划...")
            response = self._call_llm(messages)
            logger.info(f"LLM响应长度: {len(response)}")
            
            new_plan = self._parse_plan(response)
            
            if not new_plan:
                raise ValueError("解析计划失败，返回的计划为空")
            
            if "steps" not in new_plan:
                new_plan["steps"] = []
            
            logger.info(f"重新规划成功，新计划包含 {len(new_plan.get('steps', []))} 个步骤")
            return new_plan
            
        except Exception as e:
            logger.error(f"重新规划失败: {str(e)}", exc_info=True)
            raise Exception(f"重新规划失败: {str(e)}")
    
    def _call_llm(self, messages: list) -> str:
        payload = {
            **LLM_CONFIG,
            "messages": messages
        }
        
        try:
            response = requests.post(LLM_CONFIG["api_endpoint"], json=payload, timeout=LLM_CONFIG.get("timeout", 120))
            response.raise_for_status()
            result = response.json()
            
            if "choices" not in result or len(result["choices"]) == 0:
                raise ValueError("LLM响应格式错误：缺少choices字段")
            
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            raise Exception(f"LLM API调用失败: {str(e)}")
        except (KeyError, IndexError) as e:
            raise Exception(f"LLM响应解析失败: {str(e)}, 响应: {result}")
    
    def _parse_plan(self, response: str) -> Dict:
        import re

        json_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
        if json_block_match:
            try:
                plan = json.loads(json_block_match.group(1))
                if "steps" not in plan:
                    plan["steps"] = []
                if "estimated_steps" not in plan:
                    plan["estimated_steps"] = len(plan.get("steps", []))
                return plan
            except Exception as e:
                logger.warning(f"解析JSON代码块失败: {e}")
                pass

        json_match = None
        for match in re.finditer(r'\{[\s\S]*\}', response):
            try:
                test_json = json.loads(match.group())
                json_match = match
                break
            except:
                continue
        
        if json_match:
            try:
                plan = json.loads(json_match.group())
                if "steps" not in plan:
                    plan["steps"] = []
                if "estimated_steps" not in plan:
                    plan["estimated_steps"] = len(plan.get("steps", []))
                return plan
            except Exception as e:
                logger.warning(f"解析JSON对象失败: {e}")
                pass
        
        return {
            "task": "",
            "goal": response[:200] if response else "",
            "steps": [],
            "estimated_steps": 0,
            "reason": "解析失败"
        }
