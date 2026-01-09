from typing import Dict, List, Any, Optional, Tuple
from work.tools import BufferFilterTool, ElevationFilterTool, SlopeFilterTool, VegetationFilterTool, RelativePositionFilterTool
from context_manager import ContextManager
from config import LLM_CONFIG
from utils.llm_utils import call_llm, parse_plan_response
from utils.tool_utils import get_tools_schema_text, prepare_step_input_path
from utils.geojson_generator import generate_initial_geojson
import json
import logging
import re

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
    
    def _format_tools_schema_for_prompt(self) -> str:
        """
        格式化工具schema为prompt友好的格式
        
        Returns:
            格式化的工具说明文本
        """
        tool_descriptions = []
        
        # 工具类型到工具名称的映射
        type_mapping = {
            "buffer": "buffer_filter_tool",
            "elevation": "elevation_filter_tool",
            "slope": "slope_filter_tool",
            "vegetation": "vegetation_filter_tool",
            "relative_position": "relative_position_filter_tool"
        }
        
        for step_type, tool_name in type_mapping.items():
            if tool_name in self.tools:
                tool = self.tools[tool_name]
                schema = tool.get_schema()
                
                # 格式化参数说明
                params_desc = []
                for param_name, param_info in schema.get("parameters", {}).items():
                    param_type = param_info.get("type", "unknown")
                    param_desc = param_info.get("description", "")
                    if param_name == "input_geojson_path":
                        params_desc.append(f"  - `{param_name}`: {param_desc}（系统自动填充，无需在计划中指定）")
                    else:
                        # 判断是否必需参数
                        required_params = {
                            "buffer": ["buffer_distance"],
                            "elevation": [],
                            "slope": [],
                            "vegetation": [],
                            "relative_position": ["reference_point", "reference_direction", "position_types"]
                        }
                        required = param_name in required_params.get(step_type, [])
                        required_text = "必需" if required else "可选"
                        params_desc.append(f"  - `{param_name}` ({required_text}, 类型: {param_type}): {param_desc}")
                
                tool_descriptions.append(
                    f"### 工具类型: `{step_type}`\n"
                    f"- **工具名称**: {tool_name}\n"
                    f"- **功能**: {schema.get('description', '')}\n"
                    f"- **参数**:\n" + "\n".join(params_desc)
                )
        
        return "\n\n".join(tool_descriptions)
    
    def _generate_tool_plan(self, user_query: str, kag_answers: str, kag_results: List[Dict] = None) -> Dict:
        """
        基于用户问题和KAG知识生成工具调用计划（两轮思考模式）
        
        Args:
            user_query: 用户原始问题
            kag_answers: KAG合并后的答案文本
            kag_results: KAG结果列表（可选，用于提供更多上下文）
            
        Returns:
            工具调用计划字典（格式与原来plan相同）
        """
        # ========== 第一轮思考：工具选择和参数提取 ==========
        logger.info("Work阶段 - 第一轮思考：工具选择和参数提取")
        
        first_prompt = self.context_manager.load_static_context("work_first_think_prompt")
        
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
        
        first_user_content = f"用户任务: {user_query}{knowledge_text}\n\n请分析需要哪些工具，并提取具体的参数值。在响应最后输出JSON格式的工具选择和参数。"
        
        first_messages = [
            {"role": "system", "content": first_prompt},
            {"role": "user", "content": first_user_content}
        ]
        
        logger.info(f"Work阶段 - 第一轮LLM调用，用户问题: {user_query[:100]}...")
        first_response = call_llm(first_messages)
        logger.info(f"Work阶段 - 第一轮LLM响应长度: {len(first_response)}")
        
        # 解析第一轮思考的结果
        first_think_result = self._parse_first_think_response(first_response)
        if not first_think_result or "error" in first_think_result:
            logger.error(f"Work阶段 - 第一轮思考失败: {first_think_result.get('error', '未知错误')}")
            return {
                "error": "第一轮思考失败",
                "error_detail": first_think_result.get("error", "无法解析第一轮思考结果")
            }
        
        logger.info(f"Work阶段 - 第一轮思考成功，工具数量: {len(first_think_result.get('tools', []))}")
        
        # ========== 第二轮思考：编织工具调用计划 ==========
        logger.info("Work阶段 - 第二轮思考：编织工具调用计划")
        
        second_prompt = self.context_manager.load_static_context("work_second_think_prompt")
        
        # 将第一轮思考结果格式化为JSON字符串
        first_think_json = json.dumps(first_think_result, ensure_ascii=False, indent=2)
        
        second_user_content = f"""用户任务: {user_query}

第一轮思考结果（工具选择和参数）:
```json
{first_think_json}
```

请基于第一轮思考的结果，生成标准的工具调用计划（steps格式）。在响应最后输出JSON格式的计划。"""
        
        second_messages = [
            {"role": "system", "content": second_prompt},
            {"role": "user", "content": second_user_content}
        ]
        
        logger.info("Work阶段 - 第二轮LLM调用")
        second_response = call_llm(second_messages)
        logger.info(f"Work阶段 - 第二轮LLM响应长度: {len(second_response)}")
        
        # 解析第二轮思考的结果
        tool_plan = parse_plan_response(second_response)
        
        # 验证计划格式
        if not tool_plan or ("steps" not in tool_plan and "sub_plans" not in tool_plan):
            logger.error(f"Work阶段 - 无法解析工具调用计划")
            logger.error(f"Work阶段 - 完整LLM响应长度: {len(second_response)}")
            logger.error(f"Work阶段 - LLM响应开头500字符: {second_response[:500]}")
            logger.error(f"Work阶段 - LLM响应结尾1000字符: {second_response[-1000:]}")
            return {
                "error": "无法生成有效的工具调用计划",
                "llm_response": second_response,
                "error_detail": "第二轮思考中未找到有效的JSON格式工具调用计划"
            }
        
        # 验证计划的有效性和工具参数
        validation_result = self._validate_tool_plan(tool_plan)
        if not validation_result.get("valid"):
            error_msg = validation_result.get("error", "未知验证错误")
            logger.error(f"Work阶段 - 工具调用计划验证失败: {error_msg}")
            logger.error(f"Work阶段 - 工具计划内容: {json.dumps(tool_plan, ensure_ascii=False, indent=2)[:1000]}")
            return {
                "error": "工具调用计划验证失败",
                "error_detail": error_msg,
                "tool_plan": tool_plan,
                "llm_response": second_response
            }
        
        logger.info(f"Work阶段 - 成功生成并验证工具调用计划")
        if "sub_plans" in tool_plan:
            logger.info(f"Work阶段 - 多任务模式，子计划数: {len(tool_plan.get('sub_plans', []))}")
        else:
            steps = tool_plan.get('steps', [])
            logger.info(f"Work阶段 - 单任务模式，步骤数: {len(steps)}")
        
        return tool_plan
    
    def _validate_tool_plan(self, plan: Dict) -> Dict[str, Any]:
        """
        验证工具调用计划的有效性
        
        Args:
            plan: 工具调用计划字典
            
        Returns:
            验证结果字典 {"valid": bool, "error": str}
        """
        valid_tool_types = ["buffer", "elevation", "slope", "vegetation", "relative_position"]
        required_params = {
            "buffer": ["buffer_distance"],
            "relative_position": ["reference_point", "reference_direction", "position_types"]
        }
        
        def validate_step(step: Dict, step_index: int = None) -> Tuple[bool, str]:
            """验证单个步骤"""
            if not isinstance(step, dict):
                return False, f"步骤{step_index + 1 if step_index is not None else ''}必须是字典类型"
            
            # 检查必需字段
            if "type" not in step:
                return False, f"步骤{step_index + 1 if step_index is not None else ''}缺少type字段"
            
            step_type = step.get("type")
            if step_type not in valid_tool_types:
                return False, f"步骤{step_index + 1 if step_index is not None else ''}的type '{step_type}'无效，必须是以下之一: {', '.join(valid_tool_types)}"
            
            # 检查params字段
            if "params" not in step:
                return False, f"步骤{step_index + 1 if step_index is not None else ''}缺少params字段"
            
            params = step.get("params", {})
            if not isinstance(params, dict):
                return False, f"步骤{step_index + 1 if step_index is not None else ''}的params必须是字典类型"
            
            # 检查必需参数
            if step_type in required_params:
                missing_params = []
                for req_param in required_params[step_type]:
                    if req_param not in params or params[req_param] is None:
                        missing_params.append(req_param)
                
                if missing_params:
                    return False, f"步骤{step_index + 1 if step_index is not None else ''}的type '{step_type}'缺少必需参数: {', '.join(missing_params)}"
            
            # 特殊验证：relative_position的reference_point格式
            if step_type == "relative_position":
                ref_point = params.get("reference_point")
                if not isinstance(ref_point, dict):
                    return False, f"步骤{step_index + 1 if step_index is not None else ''}的reference_point必须是对象类型 {{'lon': float, 'lat': float}}"
                
                if "lon" not in ref_point or "lat" not in ref_point:
                    return False, f"步骤{step_index + 1 if step_index is not None else ''}的reference_point必须包含lon和lat字段"
                
                try:
                    float(ref_point["lon"])
                    float(ref_point["lat"])
                except (ValueError, TypeError):
                    return False, f"步骤{step_index + 1 if step_index is not None else ''}的reference_point的lon和lat必须是数字类型"
                
                ref_direction = params.get("reference_direction")
                if not isinstance(ref_direction, (int, float)):
                    return False, f"步骤{step_index + 1 if step_index is not None else ''}的reference_direction必须是数字类型"
                
                position_types = params.get("position_types")
                if not isinstance(position_types, list):
                    return False, f"步骤{step_index + 1 if step_index is not None else ''}的position_types必须是数组类型"
                
                if len(position_types) == 0:
                    return False, f"步骤{step_index + 1 if step_index is not None else ''}的position_types数组不能为空"
            
            # 特殊验证：buffer的buffer_distance
            if step_type == "buffer":
                buffer_distance = params.get("buffer_distance")
                if buffer_distance is None:
                    return False, f"步骤{step_index + 1 if step_index is not None else ''}的buffer_distance不能为空"
                if not isinstance(buffer_distance, (int, float)) or buffer_distance <= 0:
                    return False, f"步骤{step_index + 1 if step_index is not None else ''}的buffer_distance必须是正数"
            
            # 验证step_id
            if "step_id" not in step:
                return False, f"步骤{step_index + 1 if step_index is not None else ''}缺少step_id字段"
            
            step_id = step.get("step_id")
            if not isinstance(step_id, int) or step_id <= 0:
                return False, f"步骤{step_index + 1 if step_index is not None else ''}的step_id必须是正整数"
            
            return True, ""
        
        # 验证单任务模式
        if "steps" in plan:
            steps = plan.get("steps", [])
            if not isinstance(steps, list):
                return {"valid": False, "error": "steps字段必须是数组类型"}
            
            if len(steps) == 0:
                return {"valid": False, "error": "steps数组不能为空"}
            
            for i, step in enumerate(steps):
                is_valid, error_msg = validate_step(step, i)
                if not is_valid:
                    return {"valid": False, "error": error_msg}
        
        # 验证多任务模式
        elif "sub_plans" in plan:
            sub_plans = plan.get("sub_plans", [])
            if not isinstance(sub_plans, list):
                return {"valid": False, "error": "sub_plans字段必须是数组类型"}
            
            if len(sub_plans) == 0:
                return {"valid": False, "error": "sub_plans数组不能为空"}
            
            for sub_plan in sub_plans:
                if not isinstance(sub_plan, dict):
                    return {"valid": False, "error": "sub_plans中的每个元素必须是字典类型"}
                
                if "steps" not in sub_plan:
                    return {"valid": False, "error": "sub_plan缺少steps字段"}
                
                sub_steps = sub_plan.get("steps", [])
                if not isinstance(sub_steps, list):
                    return {"valid": False, "error": "sub_plan的steps字段必须是数组类型"}
                
                if len(sub_steps) == 0:
                    return {"valid": False, "error": "sub_plan的steps数组不能为空"}
                
                for i, step in enumerate(sub_steps):
                    is_valid, error_msg = validate_step(step, i)
                    if not is_valid:
                        unit = sub_plan.get("unit", "未知单位")
                        return {"valid": False, "error": f"{unit}的子计划中: {error_msg}"}
        else:
            return {"valid": False, "error": "计划必须包含steps或sub_plans字段"}
        
        return {"valid": True}
    
    def _parse_first_think_response(self, response: str) -> Dict:
        """
        解析第一轮思考的响应（工具选择和参数）
        
        Args:
            response: LLM响应文本
            
        Returns:
            解析后的工具选择和参数字典
        """
        # 首先尝试从代码块中提取JSON
        json_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
        if json_block_match:
            try:
                json_str = json_block_match.group(1)
                result = json.loads(json_str)
                if "tools" in result:
                    logger.info("成功从JSON代码块解析第一轮思考结果")
                    return result
            except json.JSONDecodeError as e:
                logger.error(f"解析JSON代码块失败: {e}")
        
        # 尝试从文本中提取JSON对象
        json_match = None
        matches = list(re.finditer(r'\{[\s\S]*\}', response))
        for match in reversed(matches):
            try:
                json_str = match.group()
                test_json = json.loads(json_str)
                if "tools" in test_json:
                    json_match = match
                    break
            except:
                continue
        
        if json_match:
            try:
                json_str = json_match.group()
                result = json.loads(json_str)
                logger.info("成功从文本中解析第一轮思考结果")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"解析JSON失败: {e}")
        
        return {
            "error": "无法解析第一轮思考结果",
            "response": response
        }
    
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
        initial_geojson_path = None  # 跟踪初始GeoJSON文件路径

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
                # 注意：初始GeoJSON文件不立即添加到待清理列表，而是在所有步骤完成后才删除
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
                    
                    # 如果出错，清理已保存的中间文件（不包括初始GeoJSON，因为它可能还在被使用）
                    self._cleanup_intermediate_files(intermediate_geojson_paths)
                    # 如果初始GeoJSON存在且不在中间文件列表中，也删除它（因为已经失败，不会继续使用）
                    if initial_geojson_path:
                        self._cleanup_intermediate_files([initial_geojson_path])
                    
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
                
                # 如果出错，清理已保存的中间文件（不包括初始GeoJSON，因为它可能还在被使用）
                self._cleanup_intermediate_files(intermediate_geojson_paths)
                # 如果初始GeoJSON存在且不在中间文件列表中，也删除它（因为已经失败，不会继续使用）
                if initial_geojson_path:
                    self._cleanup_intermediate_files([initial_geojson_path])
                
                return {
                    "success": False,
                    "error": error_msg,
                    "completed_steps": results,
                    "results": results
                }

        # 所有步骤执行成功，删除中间步骤保存的geojson文件
        self._cleanup_intermediate_files(intermediate_geojson_paths)
        # 删除初始GeoJSON文件（所有步骤已完成，不再需要）
        if initial_geojson_path:
            self._cleanup_intermediate_files([initial_geojson_path])

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

    def _prepare_step_params(self, step_type: str, params: Dict) -> Dict:
        """
        准备步骤参数，确保格式正确
        
        Args:
            step_type: 步骤类型
            params: 原始参数字典
            
        Returns:
            处理后的参数字典，如果出错返回包含error键的字典
        """
        prepared_params = params.copy()
        
        # input_geojson_path由系统自动管理，不需要验证或处理
        # 它会在_execute_steps中自动填充
        
        # 针对relative_position的特殊处理
        if step_type == "relative_position":
            # 确保reference_point是字典格式
            if "reference_point" in prepared_params:
                ref_point = prepared_params["reference_point"]
                if isinstance(ref_point, dict):
                    # 确保lon和lat是float类型
                    if "lon" in ref_point:
                        try:
                            prepared_params["reference_point"]["lon"] = float(ref_point["lon"])
                        except (ValueError, TypeError):
                            return {"error": f"reference_point.lon必须是数字类型，当前值: {ref_point.get('lon')}"}
                    if "lat" in ref_point:
                        try:
                            prepared_params["reference_point"]["lat"] = float(ref_point["lat"])
                        except (ValueError, TypeError):
                            return {"error": f"reference_point.lat必须是数字类型，当前值: {ref_point.get('lat')}"}
                else:
                    return {"error": f"reference_point必须是对象类型，当前类型: {type(ref_point).__name__}"}
            
            # 确保reference_direction是数字
            if "reference_direction" in prepared_params:
                try:
                    prepared_params["reference_direction"] = float(prepared_params["reference_direction"])
                except (ValueError, TypeError):
                    return {"error": f"reference_direction必须是数字类型，当前值: {prepared_params.get('reference_direction')}"}
            
            # 确保position_types是列表
            if "position_types" in prepared_params:
                if not isinstance(prepared_params["position_types"], list):
                    return {"error": f"position_types必须是数组类型，当前类型: {type(prepared_params['position_types']).__name__}"}
        
        # 针对buffer的特殊处理
        if step_type == "buffer":
            if "buffer_distance" in prepared_params:
                try:
                    prepared_params["buffer_distance"] = float(prepared_params["buffer_distance"])
                    if prepared_params["buffer_distance"] <= 0:
                        return {"error": f"buffer_distance必须是正数，当前值: {prepared_params['buffer_distance']}"}
                except (ValueError, TypeError):
                    return {"error": f"buffer_distance必须是数字类型，当前值: {prepared_params.get('buffer_distance')}"}
        
        return prepared_params
    
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
            
            # 再次验证参数（在工具调用前进行最后的参数格式检查）
            if not step_params:
                return {
                    "success": False,
                    "error": f"步骤 {step_type} 缺少必需参数，计划中的params为空。请重新生成包含具体参数的计划。"
                }
            
            # 确保params中的参数格式正确（特别是复杂对象）
            validated_params = self._prepare_step_params(step_type, step_params)
            if "error" in validated_params:
                return {
                    "success": False,
                    "error": validated_params["error"]
                }
            
            return self._act({
                "tool": tool_name,
                "params": validated_params
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
