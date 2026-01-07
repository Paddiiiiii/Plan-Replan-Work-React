from typing import Dict, List, Any, Optional
from work.tools import BufferFilterTool, ElevationFilterTool, SlopeFilterTool, VegetationFilterTool
from context_manager import ContextManager
from config import LLM_CONFIG
from utils.llm_utils import call_llm
from utils.tool_utils import get_tools_schema_text, prepare_step_input_path
import json
import logging

logger = logging.getLogger(__name__)

class WorkAgent:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        self.tools = {
            "buffer_filter_tool": BufferFilterTool(),
            "elevation_filter_tool": ElevationFilterTool(),
            "slope_filter_tool": SlopeFilterTool(),
            "vegetation_filter_tool": VegetationFilterTool()
        }

    def execute_plan(self, plan: Dict) -> Dict[str, Any]:
        if "sub_plans" in plan:
            return self._execute_sub_plans(plan)
        else:
            return self._execute_single_plan(plan)
    
    def _execute_single_plan(self, plan: Dict) -> Dict[str, Any]:
        """执行单任务计划"""
        return self._execute_steps(plan.get("steps", []), plan)
    
    def _execute_sub_plans(self, plan: Dict) -> Dict[str, Any]:
        """执行多任务计划"""
        sub_plans = plan.get("sub_plans", [])
        sub_results = []
        all_success = True

        for sub_plan in sub_plans:
            unit = sub_plan.get("unit", "未知单位")
            step_results = self._execute_steps(sub_plan.get("steps", []), sub_plan, unit=unit)
            
            if step_results.get("success"):
                sub_results.append({
                    "unit": unit,
                    "success": True,
                    "result_path": step_results.get("final_result_path"),
                    "steps": step_results.get("results", [])
                })
            else:
                all_success = False
                sub_results.append({
                    "unit": unit,
                    "success": False,
                    "error": step_results.get("error"),
                    "result_path": None,
                    "steps": step_results.get("results", [])
                })

        return {
            "success": all_success,
            "sub_results": sub_results,
            "plan": plan
        }
    
    def _execute_steps(self, steps: List[Dict], plan: Dict, unit: str = None) -> Dict[str, Any]:
        """
        执行步骤列表（公共逻辑）
        
        Args:
            steps: 步骤列表
            plan: 计划字典
            unit: 单位名称（用于多任务模式）
            
        Returns:
            执行结果字典
        """
        results = []
        last_result_path = None

        for i, step in enumerate(steps):
            # 准备链式调用的输入路径
            prepare_step_input_path(step, last_result_path, self.tools)

            try:
                step_result = self._execute_step(step)
                results.append(step_result)

                if step_result.get("success") and step_result.get("result", {}).get("result_path"):
                    last_result_path = step_result["result"]["result_path"]

                if not step_result.get("success", False):
                    error_msg = f"执行步骤 {i+1} 时出错"
                    if unit:
                        error_msg = f"执行{unit}步骤 {i+1} 时出错"
                    
                    return {
                        "success": False,
                        "error": step_result.get("error") or error_msg,
                        "completed_steps": results,
                        "results": results
                    }
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                error_msg = f"执行步骤 {i+1} 时出错: {str(e)}"
                if unit:
                    error_msg = f"执行{unit}步骤 {i+1} 时出错: {str(e)}"
                
                logger.error(error_msg)
                logger.error(error_detail)
                
                return {
                    "success": False,
                    "error": error_msg,
                    "completed_steps": results,
                    "results": results
                }

        return {
            "success": True,
            "results": results,
            "plan": plan,
            "final_result_path": last_result_path
        }

    def _execute_step(self, step: Dict) -> Dict[str, Any]:
        step_type = step.get("type", "")
        step_description = step.get("description", "")
        step_params = step.get("params", {})

        type_to_tool = {
            "buffer": "buffer_filter_tool",
            "elevation": "elevation_filter_tool",
            "slope": "slope_filter_tool",
            "vegetation": "vegetation_filter_tool"
        }

        if step.get("tool"):
            return self._act({
                "tool": step["tool"],
                "params": step_params
            })

        if step_type and step_type in type_to_tool and step_params:
            tool_name = type_to_tool[step_type]
            return self._act({
                "tool": tool_name,
                "params": step_params
            })

        # 执行阶段不再调用KAG，使用空上下文（plan阶段已经获取了所有需要的上下文）
        rag_context = []

        thought = self._think(step, rag_context)
        action = self._extract_action(thought)

        if action and step_params:
            merged_params = action.get("params", {})
            merged_params.update(step_params)
            action["params"] = merged_params

        if action is None and step_type in type_to_tool:
            tool_name = type_to_tool[step_type]
            action = {
                "tool": tool_name,
                "params": step_params if step_params else {}
            }

        if action is None:
            return {
                "success": False,
                "error": "无法确定执行动作或参数"
            }

        if action and action.get("tool"):
            result = self._act(action)
            if result.get("success") and result.get("result", {}).get("result_path"):
                step["last_result_path"] = result["result"]["result_path"]
            return result
        else:
            return {
                "success": False,
                "error": "无法确定执行动作"
            }

    def _think(self, step: Dict, rag_context: List[Dict]) -> str:
        prompt = self.context_manager.load_static_context("work_prompt")

        tools_schema_text = get_tools_schema_text(self.tools)
        prompt_with_schema = f"{prompt}\n\n工具参数规范:\n{tools_schema_text}"

        rag_text = ""
        if rag_context:
            rag_text = "\n相关执行历史:\n" + "\n".join([ctx.get("text", "") for ctx in rag_context[:3]])


        previous_result = step.get("last_result_path", "")
        if previous_result:
            rag_text += f"\n上一步的输出文件路径: {previous_result}"

        step_type = step.get("type", "")
        user_content = f"步骤: {json.dumps(step, ensure_ascii=False)}{rag_text}"
        if step_type:
            type_hint = f"\n\n注意：步骤类型(type)为'{step_type}'，对应工具映射：buffer->buffer_filter_tool, elevation->elevation_filter_tool, slope->slope_filter_tool, vegetation->vegetation_filter_tool"
            user_content += type_hint

        messages = [
            {"role": "system", "content": prompt_with_schema},
            {"role": "user", "content": user_content}
        ]

        response = call_llm(messages)
        return response

    def _extract_action(self, thought: str) -> Optional[Dict]:
        import re

        json_match = re.search(r'\{[\s\S]*\}', thought)
        if json_match:
            try:
                action = json.loads(json_match.group())
                return action
            except:
                pass

        return None

    def _act(self, action: Dict) -> Dict[str, Any]:
        tool_name = action.get("tool")
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"工具不存在: {tool_name}"
            }

        tool = self.tools[tool_name]
        params = action.get("params", {})

        if not tool.validate_params(**params):
            return {
                "success": False,
                "error": "参数验证失败"
            }

        try:
            result = tool.execute(**params)

            is_success = result.get("success", False)

            return {
                "success": is_success,
                "tool": tool_name,
                "params": params,
                "result": result,
                "error": result.get("error") if not is_success else None
            }
        except Exception as e:
            error_msg = str(e)
            return {
                "success": False,
                "error": error_msg
            }

