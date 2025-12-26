from typing import Dict, List
from context_manager import ContextManager
from config import LLM_CONFIG
import requests
import json
import logging

logger = logging.getLogger(__name__)


class ReplanModule:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
    
    def should_replan(self, work_result: Dict) -> bool:
        if not work_result.get("success", False):
            return True
        return False
    
    def replan(self, original_plan: Dict, work_result: Dict, available_tools: List[str]) -> Dict:
        prompt_template = self.context_manager.load_static_context("replan_prompt")
        
        tools_info = [{"name": tool} for tool in available_tools]
        tools_info_str = json.dumps(tools_info, ensure_ascii=False, indent=2)
        
        # 使用replace而不是format，避免JSON示例中的字段被误认为是占位符
        try:
            prompt = prompt_template.replace("{tools_info}", tools_info_str)
        except (KeyError, ValueError) as e:
            logger.warning(f"提示词格式化失败，使用替换方式: {e}")
            prompt = prompt_template.replace("{tools_info}", tools_info_str)
        
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
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content}
        ]
        
        response = self._call_llm(messages)
        new_plan = self._parse_plan(response)
        
        return new_plan
    
    def replan_with_feedback(self, original_plan: Dict, feedback: str, available_tools: List[str]) -> Dict:
        try:
            logger.info(f"开始重新规划，反馈: {feedback[:50]}...")
            
            prompt_template = self.context_manager.load_static_context("replan_prompt")
            
            if not prompt_template:
                prompt_template = """你是一个重新规划助手，根据用户反馈调整计划。

可用工具：
{tools_info}

输出格式（JSON）：
{{
    "task": "用户原始任务",
    "goal": "调整后的任务目标",
    "steps": [
        {{"step_id": 1, "tool": "buffer_filter_tool", "params": {{"buffer_distance": 500}}}},
        {{"step_id": 2, "tool": "vegetation_filter_tool", "params": {{"input_geojson_path": "...", "vegetation_types": [30]}}}},
        ...
    ],
    "required_tools": ["buffer_filter_tool", "vegetation_filter_tool"],
    "reason": "重新规划的原因"
}}"""
            
            tools_info = [{"name": tool} for tool in available_tools]
            tools_info_str = json.dumps(tools_info, ensure_ascii=False, indent=2)
            
            try:
                prompt = prompt_template.format(tools_info=tools_info_str)
            except (KeyError, ValueError) as e:
                logger.warning(f"提示词格式化失败，使用替换方式: {e}")
                prompt = prompt_template.replace("{tools_info}", tools_info_str)
            
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
                {"role": "system", "content": prompt},
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
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                plan = json.loads(json_match.group())
                if "steps" not in plan:
                    plan["steps"] = []
                return plan
            except:
                pass
        
        return {
            "task": "",
            "goal": response[:200],
            "steps": [],
            "required_tools": [],
            "reason": "解析失败"
        }
