from typing import Dict
from context_manager import ContextManager
from work.tools import BufferFilterTool, ElevationFilterTool, SlopeFilterTool, VegetationFilterTool
from utils.llm_utils import call_llm, parse_plan_response
from utils.tool_utils import get_tools_schema_text
import logging
import re

logger = logging.getLogger(__name__)

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
        # 统一知识库检索，不再区分collection
        rag_context = self.context_manager.load_dynamic_context(
            user_task,
            top_k=5
        )

        prompt = self.context_manager.load_static_context("plan_prompt")

        tools_schema_text = get_tools_schema_text(self.tools)
        prompt_with_schema = f"{prompt}\n\n## 工具参数规范（动态获取）\n{tools_schema_text}"

        knowledge_text = ""
        if rag_context:
            knowledge_text = "\n相关知识:\n" + "\n".join([ctx.get("text", "") for ctx in rag_context])

        messages = [
            {"role": "system", "content": prompt_with_schema},
            {"role": "user", "content": f"任务: {user_task}{knowledge_text}"}
        ]

        response = call_llm(messages)
        logger.info(f"Plan阶段 - LLM响应长度: {len(response)}")
        logger.info(f"Plan阶段 - LLM响应前500字符: {response[:500]}")

        plan = parse_plan_response(response)

        if "sub_plans" in plan:
            logger.info(f"Plan阶段 - 多任务模式，子计划数: {len(plan.get('sub_plans', []))}")
            for i, sub_plan in enumerate(plan.get('sub_plans', [])):
                logger.info(f"Plan阶段 - 子计划[{i+1}] 单位: {sub_plan.get('unit', 'N/A')}, 步骤数: {len(sub_plan.get('steps', []))}")
        else:
            logger.info(f"Plan阶段 - 单任务模式，解析后的步骤数: {len(plan.get('steps', []))}")
            logger.info(f"Plan阶段 - 步骤类型: {[s.get('type', 'N/A') for s in plan.get('steps', [])]}")
        plan["llm_response"] = response

        plan["matched_knowledge"] = []
        if rag_context:
            for ctx in rag_context:
                plan["matched_knowledge"].append({
                    "text": ctx.get("text", ""),
                    "metadata": ctx.get("metadata", {})
                })

        # 使用第一次KAG检索时缓存的答案，避免在plan阶段再次触发KAG推理
        try:
            answer = getattr(self.context_manager, "last_kag_answer", "") or ""
            if answer:
                # 提取"Final Answer:"后面的内容
                # 支持多种可能的格式：Final Answer:、Final Answer:、Final Answer等
                final_answer_match = re.search(
                    r"Final\s+Answer\s*:?\\s*(.*)",
                    answer,
                    re.IGNORECASE | re.DOTALL,
                )
                if final_answer_match:
                    kag_answer = final_answer_match.group(1).strip()
                    # 清理reference标记
                    kag_answer = re.sub(r"<reference[^>]*></reference>", "", kag_answer)
                    kag_answer = kag_answer.strip()
                    if kag_answer:
                        plan["kag_reasoning_answer"] = kag_answer
                        logger.info(
                            f"Plan阶段 - KAG推理答案已提取（使用缓存），长度: {len(kag_answer)}"
                        )
                else:
                    # 如果没有"Final Answer:"标记，直接使用整个答案（清理reference标记）
                    clean_answer = re.sub(
                        r"<reference[^>]*></reference>", "", answer
                    ).strip()
                    if clean_answer:
                        plan["kag_reasoning_answer"] = clean_answer
                        logger.info(
                            f"Plan阶段 - KAG推理答案已提取（缓存，无标记），长度: {len(clean_answer)}"
                        )
        except Exception as e:
            logger.warning(f"Plan阶段 - 处理KAG推理答案缓存失败: {e}")

        return plan

