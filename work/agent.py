from typing import Dict, List, Any, Optional
from work.tools import BufferFilterTool, ElevationFilterTool, SlopeFilterTool, VegetationFilterTool, RelativePositionFilterTool
from context_manager import ContextManager
from config import LLM_CONFIG
from utils.llm_utils import call_llm, parse_plan_response
from utils.tool_utils import get_tools_schema_text, prepare_step_input_path
from utils.geojson_generator import generate_initial_geojson
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
            "vegetation_filter_tool": VegetationFilterTool(),
            "relative_position_filter_tool": RelativePositionFilterTool()
        }

    def execute_plan(self, plan: Dict) -> Dict[str, Any]:
        """
        执行计划：基于KAG知识生成工具调用计划，然后执行
        
        Args:
            plan: Plan模块返回的字典，包含original_query、combined_kag_answers等信息
            
        Returns:
            执行结果字典
        """
        # 检查plan是否包含工具调用计划（向后兼容）
        if "steps" in plan or "sub_plans" in plan:
            # 如果是旧的plan格式（直接包含工具调用计划），直接执行
            logger.info("Work阶段 - 检测到旧格式plan（包含工具调用计划），直接执行")
            if "sub_plans" in plan:
                return self._execute_sub_plans(plan)
            else:
                return self._execute_single_plan(plan)
        
        # 新格式：plan包含问题和KAG答案，需要生成工具调用计划
        original_query = plan.get("original_query", "")
        combined_kag_answers = plan.get("combined_kag_answers", "")
        kag_results = plan.get("kag_results", [])
        
        if not original_query:
            return {
                "success": False,
                "error": "Plan中缺少original_query字段"
            }
        
        if not combined_kag_answers:
            logger.warning("Work阶段 - combined_kag_answers为空，将基于问题本身生成工具计划")
        
        logger.info("Work阶段 - 开始基于KAG知识生成工具调用计划")
        
        # 生成工具调用计划
        tool_plan = self._generate_tool_plan(original_query, combined_kag_answers, kag_results)
        
        if not tool_plan or "error" in tool_plan:
            return {
                "success": False,
                "error": tool_plan.get("error", "无法生成工具调用计划")
            }
        
        # 在终端显示工具调用计划
        print("\n" + "=" * 80)
        print("🔧 工具调用计划（JSON格式）")
        print("=" * 80)
        
        display_plan = {}
        if "sub_plans" in tool_plan:
            display_plan["模式"] = f"多任务模式（{len(tool_plan.get('sub_plans', []))}个子计划）"
            display_plan["sub_plans"] = []
            for sub_plan in tool_plan.get('sub_plans', []):
                display_sub_plan = {
                    "unit": sub_plan.get('unit', '未知单位'),
                    "steps": []
                }
                for step in sub_plan.get('steps', []):
                    display_step = {
                        "step_id": step.get('step_id'),
                        "description": step.get('description', '无描述'),
                        "type": step.get('type', 'N/A'),
                        "params": step.get('params', {})
                    }
                    # 移除input_geojson_path（系统自动填充）
                    if "params" in display_step and "input_geojson_path" in display_step["params"]:
                        del display_step["params"]["input_geojson_path"]
                    display_sub_plan["steps"].append(display_step)
                display_plan["sub_plans"].append(display_sub_plan)
        else:
            display_plan["模式"] = "单任务模式"
            display_plan["steps"] = []
            for step in tool_plan.get('steps', []):
                display_step = {
                    "step_id": step.get('step_id'),
                    "description": step.get('description', '无描述'),
                    "type": step.get('type', 'N/A'),
                    "params": step.get('params', {})
                }
                # 移除input_geojson_path（系统自动填充）
                if "params" in display_step and "input_geojson_path" in display_step["params"]:
                    del display_step["params"]["input_geojson_path"]
                display_plan["steps"].append(display_step)
        
        # 打印JSON格式的计划
        print(json.dumps(display_plan, ensure_ascii=False, indent=2))
        print("=" * 80 + "\n")
        
        # 执行工具调用计划
        if "sub_plans" in tool_plan:
            return self._execute_sub_plans(tool_plan)
        else:
            return self._execute_single_plan(tool_plan)
    
    def _generate_tool_plan(self, user_query: str, kag_answers: str, kag_results: List[Dict] = None) -> Dict:
        """
        基于用户问题和KAG知识生成工具调用计划
        
        Args:
            user_query: 用户原始问题
            kag_answers: KAG合并后的答案文本
            kag_results: KAG结果列表（可选，用于提供更多上下文）
            
        Returns:
            工具调用计划字典（格式与原来plan相同）
        """
        prompt = self.context_manager.load_static_context("work_prompt")
        
        # 获取工具schema信息
        tools_schema_text = get_tools_schema_text(self.tools)
        prompt_with_schema = f"{prompt}\n\n## 工具参数规范（动态获取）\n{tools_schema_text}"
        
        # 构建用户消息，包含问题和KAG知识
        knowledge_text = f"\n\nKAG知识库检索结果:\n{kag_answers}" if kag_answers else ""
        
        # 如果有kag_results，提供更详细的信息
        if kag_results:
            knowledge_text += "\n\n详细KAG检索结果:\n"
            for i, result in enumerate(kag_results, 1):
                question = result.get("question", "")
                answer = result.get("answer", "")
                if answer:
                    knowledge_text += f"\n子问题{i}: {question}\n答案{i}: {answer}\n"
        
        user_content = f"用户任务: {user_query}{knowledge_text}"
        
        messages = [
            {"role": "system", "content": prompt_with_schema},
            {"role": "user", "content": user_content}
        ]
        
        logger.info(f"Work阶段 - 调用LLM生成工具计划，用户问题: {user_query[:100]}...")
        response = call_llm(messages)
        logger.info(f"Work阶段 - LLM响应长度: {len(response)}")
        logger.info(f"Work阶段 - LLM响应前1000字符: {response[:1000]}")
        
        # 解析LLM响应为工具调用计划
        tool_plan = parse_plan_response(response)
        
        # 验证计划格式
        if not tool_plan or ("steps" not in tool_plan and "sub_plans" not in tool_plan):
            logger.error(f"Work阶段 - 无法解析工具调用计划，响应: {response[:500]}")
            return {
                "error": "无法生成有效的工具调用计划",
                "llm_response": response
            }
        
        logger.info(f"Work阶段 - 成功生成工具调用计划")
        if "sub_plans" in tool_plan:
            logger.info(f"Work阶段 - 多任务模式，子计划数: {len(tool_plan.get('sub_plans', []))}")
        else:
            steps = tool_plan.get('steps', [])
            logger.info(f"Work阶段 - 单任务模式，步骤数: {len(steps)}")
        
        return tool_plan
    
    def _execute_single_plan(self, plan: Dict) -> Dict[str, Any]:
        """执行单任务计划"""
        print("\n开始执行计划...")
        print("-" * 80)
        result = self._execute_steps(plan.get("steps", []), plan)
        if result.get("success"):
            print("\n✓ 计划执行成功")
        else:
            print(f"\n✗ 计划执行失败: {result.get('error', '未知错误')}")
        return result
    
    def _execute_sub_plans(self, plan: Dict) -> Dict[str, Any]:
        """执行多任务计划"""
        sub_plans = plan.get("sub_plans", [])
        sub_results = []
        all_success = True

        for sub_plan in sub_plans:
            unit = sub_plan.get("unit", "未知单位")
            print(f"\n执行子计划: {unit}")
            print("-" * 80)
            step_results = self._execute_steps(sub_plan.get("steps", []), sub_plan, unit=unit)
            
            if step_results.get("success"):
                print(f"✓ {unit} 执行成功")
                sub_results.append({
                    "unit": unit,
                    "success": True,
                    "result_path": step_results.get("final_result_path"),
                    "steps": step_results.get("results", [])
                })
            else:
                all_success = False
                print(f"✗ {unit} 执行失败: {step_results.get('error', '未知错误')}")
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
        intermediate_geojson_paths = []  # 跟踪中间步骤保存的geojson文件

        # 如果第一个步骤需要input_geojson_path，先生成初始GeoJSON
        # 需要初始GeoJSON的步骤类型：buffer, relative_position, elevation, slope, vegetation
        first_step_type = steps[0].get("type") if steps else None
        needs_initial_geojson = first_step_type in ["buffer", "relative_position", "elevation", "slope", "vegetation"]
        
        if steps and needs_initial_geojson:
            try:
                first_step_params = steps[0].get("params", {})
                utm_crs = first_step_params.get("utm_crs")
                initial_geojson_path = generate_initial_geojson(utm_crs=utm_crs)
                last_result_path = initial_geojson_path
                # 确保第一步的params存在
                if "params" not in steps[0]:
                    steps[0]["params"] = {}
                # 将初始GeoJSON路径填充到第一步的params中（如果还没有）
                if "input_geojson_path" not in steps[0]["params"] or not steps[0]["params"]["input_geojson_path"]:
                    steps[0]["params"]["input_geojson_path"] = initial_geojson_path
                logger.info(f"生成初始GeoJSON文件: {initial_geojson_path}")
            except Exception as e:
                logger.error(f"生成初始GeoJSON失败: {e}")
                return {
                    "success": False,
                    "error": f"生成初始GeoJSON失败: {str(e)}",
                    "results": results
                }

        for i, step in enumerate(steps):
            # 准备链式调用的输入路径
            prepare_step_input_path(step, last_result_path, self.tools)

            try:
                step_result = self._execute_step(step)
                results.append(step_result)

                if step_result.get("success") and step_result.get("result", {}).get("result_path"):
                    result_path = step_result["result"]["result_path"]
                    # 记录中间步骤的geojson文件（除了最后一步）
                    if i < len(steps) - 1:  # 不是最后一步
                        intermediate_geojson_paths.append(result_path)
                    last_result_path = result_path

                if not step_result.get("success", False):
                    error_msg = f"执行步骤 {i+1} 时出错"
                    if unit:
                        error_msg = f"执行{unit}步骤 {i+1} 时出错"
                    
                    # 如果出错，清理已保存的中间文件
                    self._cleanup_intermediate_files(intermediate_geojson_paths)
                    
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
                
                # 如果出错，清理已保存的中间文件
                self._cleanup_intermediate_files(intermediate_geojson_paths)
                
                return {
                    "success": False,
                    "error": error_msg,
                    "completed_steps": results,
                    "results": results
                }

        # 所有步骤执行成功，删除中间步骤保存的geojson文件
        self._cleanup_intermediate_files(intermediate_geojson_paths)

        return {
            "success": True,
            "results": results,
            "plan": plan,
            "final_result_path": last_result_path
        }
    
    def _cleanup_intermediate_files(self, file_paths: List[str]):
        """
        删除中间步骤保存的geojson文件
        
        Args:
            file_paths: 要删除的文件路径列表
        """
        from pathlib import Path
        import os
        
        for file_path in file_paths:
            if file_path:
                try:
                    path = Path(file_path)
                    if path.exists() and path.is_file():
                        os.remove(file_path)
                        logger.info(f"已删除中间步骤文件: {file_path}")
                except Exception as e:
                    logger.warning(f"删除中间步骤文件失败 {file_path}: {e}")

    def _execute_step(self, step: Dict) -> Dict[str, Any]:
        """执行单个步骤"""
        step_type = step.get("type", "")
        step_params = step.get("params", {})

        type_to_tool = {
            "buffer": "buffer_filter_tool",
            "elevation": "elevation_filter_tool",
            "slope": "slope_filter_tool",
            "vegetation": "vegetation_filter_tool",
            "relative_position": "relative_position_filter_tool"
        }

        # 如果step中直接指定了tool，使用它
        if step.get("tool"):
            return self._act({
                "tool": step["tool"],
                "params": step_params
            })

        # 如果step有type，映射到对应的工具
        if step_type and step_type in type_to_tool:
            tool_name = type_to_tool[step_type]
            # 检查必需参数是否缺失
            if not step_params:
                return {
                    "success": False,
                    "error": f"步骤 {step_type} 缺少必需参数，计划中的params为空。请重新生成包含具体参数的计划。"
                }
            return self._act({
                "tool": tool_name,
                "params": step_params
            })

        # 如果既没有tool也没有type，返回错误
        return {
            "success": False,
            "error": f"步骤缺少type或tool字段，无法确定执行动作。步骤: {step}"
        }

    def _act(self, action: Dict) -> Dict[str, Any]:
        """执行工具调用"""
        tool_name = action.get("tool")
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"工具不存在: {tool_name}"
            }

        tool = self.tools[tool_name]
        params = action.get("params", {})

        if not tool.validate_params(**params):
            # 记录详细的参数信息以便调试
            logger.error(f"工具 {tool_name} 参数验证失败，参数: {params}")
            return {
                "success": False,
                "error": f"参数验证失败: 工具 {tool_name} 的参数不满足要求。参数: {params}"
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
            logger.error(f"工具 {tool_name} 执行异常: {error_msg}", exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
