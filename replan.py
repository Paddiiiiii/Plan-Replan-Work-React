from typing import Dict, List
from context_manager import ContextManager
from work.tools import BufferFilterTool, ElevationFilterTool, SlopeFilterTool, VegetationFilterTool
from utils.llm_utils import call_llm, parse_plan_response
from utils.tool_utils import get_tools_schema_text
import json
import logging

logger = logging.getLogger(__name__)

class ReplanModule:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
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

        tools_schema_text = get_tools_schema_text(self.tools)
        prompt_with_schema = f"{prompt_template}\n\n## 工具参数规范（动态获取）\n{tools_schema_text}"

        plan_text = json.dumps(original_plan, ensure_ascii=False)
        rag_context = self.context_manager.load_dynamic_context(
            plan_text,
            top_k=3
        )

        plan_str = json.dumps(original_plan, ensure_ascii=False, indent=2)
        result_str = json.dumps(work_result, ensure_ascii=False, indent=2)

        knowledge_text = ""
        if rag_context:
            knowledge_text = "\n\n相关知识:\n" + "\n".join([ctx.get("text", "") for ctx in rag_context])

        user_content = f"请根据原计划和执行结果重写 JSON 计划\n\n原计划:\n{plan_str}\n\n执行结果:\n{result_str}{knowledge_text}"

        messages = [
            {"role": "system", "content": prompt_with_schema},
            {"role": "user", "content": user_content}
        ]

        response = call_llm(messages)
        logger.info(f"LLM响应长度: {len(response)}")
        new_plan = parse_plan_response(response)
        
        # 保存LLM响应，供前端展示
        new_plan["llm_response"] = response

        return new_plan

    def replan_with_feedback(self, original_plan: Dict, feedback: str, available_tools: List[str]) -> Dict:
        try:
            logger.info(f"开始重新规划，反馈: {feedback[:50]}...")

            prompt_template = self.context_manager.load_static_context("replan_prompt")

            tools_schema_text = get_tools_schema_text(self.tools)
            prompt_with_schema = f"{prompt_template}\n\n## 工具参数规范（动态获取）\n{tools_schema_text}"

            plan_text = json.dumps(original_plan, ensure_ascii=False)
            rag_context = self.context_manager.load_dynamic_context(
                plan_text,
                top_k=3
            )

            plan_str = json.dumps(original_plan, ensure_ascii=False, indent=2)

            knowledge_text = ""
            if rag_context:
                knowledge_text = "\n\n相关知识:\n" + "\n".join([ctx.get("text", "") for ctx in rag_context])

            user_content = f"请根据原计划和用户反馈重写 JSON 计划\n\n原计划:\n{plan_str}\n\n用户反馈:\n{feedback}{knowledge_text}"

            messages = [
                {"role": "system", "content": prompt_with_schema},
                {"role": "user", "content": user_content}
            ]

            logger.info("调用LLM生成新计划...")
            response = call_llm(messages)
            logger.info(f"LLM响应长度: {len(response)}")

            new_plan = parse_plan_response(response)

            if not new_plan:
                raise ValueError("解析计划失败，返回的计划为空")

            if "steps" not in new_plan:
                new_plan["steps"] = []
            
            # 保存LLM响应，供前端展示
            new_plan["llm_response"] = response

            logger.info(f"重新规划成功，新计划包含 {len(new_plan.get('steps', []))} 个步骤")
            return new_plan

        except Exception as e:
            logger.error(f"重新规划失败: {str(e)}", exc_info=True)
            raise Exception(f"重新规划失败: {str(e)}")

