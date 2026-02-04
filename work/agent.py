from typing import Dict, List, Any, Optional, Tuple
from work.tools import BufferFilterTool, ElevationFilterTool, SlopeFilterTool, VegetationFilterTool, RelativePositionFilterTool, DistanceFilterTool, AreaFilterTool
from context_manager import ContextManager
from config import LLM_CONFIG, GEO_BOUNDS, PATHS, TOOL_ENABLE_CONFIG
from utils.llm_utils import call_llm, parse_plan_response
from utils.tool_utils import get_tools_schema_text, prepare_step_input_path
from utils.geojson_generator import generate_initial_geojson
import json
import logging
import re
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class WorkAgent:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        # 根据配置只初始化启用的工具
        all_tools = {
            "buffer_filter_tool": BufferFilterTool(),
            "elevation_filter_tool": ElevationFilterTool(),
            "slope_filter_tool": SlopeFilterTool(),
            "vegetation_filter_tool": VegetationFilterTool(),
            "relative_position_filter_tool": RelativePositionFilterTool(),
            "distance_filter_tool": DistanceFilterTool(),
            "area_filter_tool": AreaFilterTool()
        }
        # 只保留启用的工具
        self.tools = {
            tool_name: tool for tool_name, tool in all_tools.items()
            if TOOL_ENABLE_CONFIG.get(tool_name, True)
        }
        logger.info(f"已启用的工具: {list(self.tools.keys())}")

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
        
        # 将原始plan中的kag_results等信息合并到tool_plan中，供前端展示
        tool_plan["original_query"] = original_query
        tool_plan["kag_results"] = kag_results
        tool_plan["combined_kag_answers"] = combined_kag_answers
        # 保留plan中的retrieved_entities和retrieved_relations，用于保存到kg_graph文件夹
        tool_plan["retrieved_entities"] = plan.get("retrieved_entities", [])
        tool_plan["retrieved_relations"] = plan.get("retrieved_relations", [])
        if plan.get("sub_questions"):
            tool_plan["sub_questions"] = plan.get("sub_questions")
        
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
            work_result = self._execute_sub_plans(tool_plan)
        else:
            work_result = self._execute_single_plan(tool_plan)
        
        # 将更新后的plan（包含kag_results和LLM响应）添加到work_result中
        work_result["updated_plan"] = tool_plan
        
        return work_result
    
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
            "relative_position": "relative_position_filter_tool",
            "distance": "distance_filter_tool",
            "area": "area_filter_tool"
        }
        
        for step_type, tool_name in type_mapping.items():
            # 检查工具是否启用
            if not TOOL_ENABLE_CONFIG.get(tool_name, True):
                continue  # 跳过未启用的工具
            
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
                            "relative_position": ["reference_point", "reference_direction", "position_types"],
                            "distance": ["reference_point", "max_distance"],
                            "area": ["min_area_km2"]
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
        
        # 保存第一轮和第二轮LLM响应，供前端展示
        tool_plan["first_llm_response"] = first_response
        tool_plan["second_llm_response"] = second_response
        
        return tool_plan
    
    def _validate_tool_plan(self, plan: Dict) -> Dict[str, Any]:
        """
        验证工具调用计划的有效性
        
        Args:
            plan: 工具调用计划字典
            
        Returns:
            验证结果字典 {"valid": bool, "error": str}
        """
        valid_tool_types = ["buffer", "elevation", "slope", "vegetation", "relative_position", "distance", "area"]
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

        # 如果第一个允许的步骤需要input_geojson_path，先生成初始GeoJSON
        # 需要初始GeoJSON的步骤类型：relative_position, distance, area
        allowed_tool_types = ["relative_position", "distance", "area"]
        first_allowed_step = None
        first_allowed_step_index = None
        for i, step in enumerate(steps):
            step_type = step.get("type", "")
            if step_type in allowed_tool_types:
                first_allowed_step = step
                first_allowed_step_index = i
                break
        
        needs_initial_geojson = first_allowed_step is not None and first_allowed_step.get("type") in ["relative_position", "distance", "area"]
        
        if needs_initial_geojson:
            try:
                first_step_params = first_allowed_step.get("params", {})
                utm_crs = first_step_params.get("utm_crs")
                initial_geojson_path = generate_initial_geojson(utm_crs=utm_crs)
                last_result_path = initial_geojson_path
                # 注意：初始GeoJSON文件不立即添加到待清理列表，而是在所有步骤完成后才删除
                # 确保第一步的params存在
                if "params" not in first_allowed_step:
                    first_allowed_step["params"] = {}
                # 将初始GeoJSON路径填充到第一个允许步骤的params中（如果还没有）
                if "input_geojson_path" not in first_allowed_step["params"] or not first_allowed_step["params"]["input_geojson_path"]:
                    first_allowed_step["params"]["input_geojson_path"] = initial_geojson_path
                logger.info(f"生成初始GeoJSON文件: {initial_geojson_path}")
            except Exception as e:
                logger.error(f"生成初始GeoJSON失败: {e}")
                return {
                    "success": False,
                    "error": f"生成初始GeoJSON失败: {str(e)}",
                    "results": results
                }

        # 根据配置决定允许的工具类型
        # 工具类型到工具名称的映射
        type_to_tool_mapping = {
            "buffer": "buffer_filter_tool",
            "elevation": "elevation_filter_tool",
            "slope": "slope_filter_tool",
            "vegetation": "vegetation_filter_tool",
            "relative_position": "relative_position_filter_tool",
            "distance": "distance_filter_tool",
            "area": "area_filter_tool"
        }
        
        # 根据TOOL_ENABLE_CONFIG筛选允许的工具类型
        allowed_tool_types = [
            tool_type for tool_type, tool_name in type_to_tool_mapping.items()
            if TOOL_ENABLE_CONFIG.get(tool_name, True)  # 默认启用
        ]
        
        logger.info(f"启用的工具类型: {allowed_tool_types}")
        
        # 找到最后一个允许的工具类型的索引
        last_allowed_step_index = None
        for i in range(len(steps) - 1, -1, -1):
            step_type = steps[i].get("type", "")
            if step_type in allowed_tool_types:
                last_allowed_step_index = i
                break
        
        for i, step in enumerate(steps):
            step_type = step.get("type", "")
            
            # 如果工具类型不在允许列表中，跳过该步骤
            if step_type and step_type not in allowed_tool_types:
                logger.info(f"跳过工具类型 '{step_type}'（不在允许的工具列表中）")
                # 记录跳过的步骤
                results.append({
                    "success": True,
                    "tool": step_type,
                    "skipped": True,
                    "message": f"工具类型 '{step_type}' 已跳过（不在允许的工具列表中）"
                })
                continue
            
            # 准备链式调用的输入路径
            prepare_step_input_path(step, last_result_path, self.tools)

            try:
                step_result = self._execute_step(step)
                results.append(step_result)

                if step_result.get("success") and step_result.get("result", {}).get("result_path"):
                    result_path = step_result["result"]["result_path"]
                    # 记录中间步骤的geojson文件（除了最后一个允许的工具类型）
                    if i != last_allowed_step_index:  # 不是最后一个允许的工具类型
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

        # 如果执行成功且有最终结果路径，保存metadata文件
        if last_result_path:
            try:
                kg_graph_image_filename = self._save_result_metadata(last_result_path, plan, results, unit)
                # 将图片文件名添加到plan中，供前端使用
                if kg_graph_image_filename:
                    plan["kg_graph_image_filename"] = kg_graph_image_filename
            except Exception as e:
                logger.warning(f"保存结果metadata失败: {e}", exc_info=True)
        
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
            "relative_position": "relative_position_filter_tool",
            "distance": "distance_filter_tool",
            "area": "area_filter_tool"
        }

        # 如果step中直接指定了tool，使用它
        if step.get("tool"):
            result = self._act({
                "tool": step["tool"],
                "params": step_params
            })
            # 如果步骤标记为使用默认值，将标记传递到结果中
            if step.get("is_default"):
                result["is_default"] = True
            return result

        # 如果step有type，映射到对应的工具
        if step_type and step_type in type_to_tool:
            tool_name = type_to_tool[step_type]
            
            # 检查工具是否启用
            if tool_name not in self.tools:
                return {
                    "success": False,
                    "error": f"工具 '{tool_name}' 未启用（在config.py的TOOL_ENABLE_CONFIG中设置为False）"
                }
            
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
            
            result = self._act({
                "tool": tool_name,
                "params": validated_params
            })
            # 如果步骤标记为使用默认值，将标记传递到结果中
            if step.get("is_default"):
                result["is_default"] = True
            return result

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
    
    def _save_result_metadata(self, result_path: str, plan: Dict, step_results: List[Dict], unit: str = None):
        """
        保存结果文件到不同的文件夹：
        - geojson: 结果GeoJSON文件（已由工具保存）
        - regions: 区域信息JSON文件
        - llm_thinking: LLM思考结果JSON文件
        - kg_graph: 实体关系图JSON文件
        
        Args:
            result_path: GeoJSON结果文件路径
            plan: 计划字典（包含kag_results等信息）
            step_results: 步骤执行结果列表
            unit: 单位名称（用于多任务模式）
        """
        try:
            from config import PATHS
            import json
            
            result_file = Path(result_path)
            if not result_file.exists():
                logger.warning(f"结果文件不存在，无法保存metadata: {result_path}")
                return
            
            # 获取基础文件名（不含扩展名）
            base_name = result_file.stem
            
            # 确保各个文件夹存在
            regions_dir = PATHS["result_regions_dir"]
            llm_thinking_dir = PATHS["result_llm_thinking_dir"]
            
            regions_dir.mkdir(parents=True, exist_ok=True)
            llm_thinking_dir.mkdir(parents=True, exist_ok=True)
            
            # 提取区域信息（从plan或session_state中获取，这里先尝试从plan中解析）
            regions = []
            original_query = plan.get("original_query", "")
            if original_query:
                # 尝试从查询中解析区域信息
                try:
                    regions = self._parse_regions_from_task(original_query)
                except:
                    pass
            
            # 提取参考点信息（从step_results中提取）
            reference_points = []
            for step_result in step_results:
                if step_result.get("success") and step_result.get("tool") == "relative_position_filter_tool":
                    step_params = step_result.get("params", {})
                    result_data = step_result.get("result", {})
                    # 优先使用结果中的参考点信息
                    ref_point = None
                    ref_dir = None
                    if result_data.get("reference_point"):
                        ref_point = result_data.get("reference_point")
                    elif step_params.get("reference_point"):
                        ref_point = step_params.get("reference_point")
                    if result_data.get("reference_direction") is not None:
                        ref_dir = result_data.get("reference_direction")
                    elif step_params.get("reference_direction") is not None:
                        ref_dir = step_params.get("reference_direction")
                    
                    if ref_point and ref_dir is not None:
                        reference_points.append({
                            "point": ref_point,
                            "direction": ref_dir
                        })
            
            # 提取KAG问答结果
            kag_results = plan.get("kag_results", [])
            kag_qa_results = []
            for kag_result in kag_results:
                kag_qa_results.append({
                    "question": kag_result.get("question", ""),
                    "answer": kag_result.get("answer", ""),
                    "input_query": kag_result.get("input_query", "")
                })
            
            # 提取与问题相关的子图谱
            retrieved_entities = []
            retrieved_relations = []
            
            # 1. 从原始问题中提取关键词
            original_query = plan.get("original_query", "")
            query_keywords = self._extract_keywords_from_query(original_query)
            logger.info(f"从问题中提取的关键词: {query_keywords}")
            
            if query_keywords:
                # 2. 优先从plan中获取实体和关系，然后过滤
                if plan.get("retrieved_entities") and plan.get("retrieved_relations"):
                    logger.info("从plan中获取实体和关系，然后过滤")
                    all_entities = plan.get("retrieved_entities", [])
                    all_relations = plan.get("retrieved_relations", [])
                    retrieved_entities, retrieved_relations = self._filter_relevant_subgraph(
                        all_entities, all_relations, query_keywords
                    )
                
                # 3. 如果过滤后没有结果，尝试从kag_solver的checkpoint中提取并过滤
                if not retrieved_entities and not retrieved_relations:
                    logger.info("从checkpoint中提取实体和关系，然后过滤")
                    try:
                        kg_data = self.context_manager.kag_solver.get_kg_data()
                        if kg_data and kg_data.get("entity_count", 0) > 0:
                            all_entities = kg_data.get("entities", [])
                            all_relations = kg_data.get("relations", [])
                            retrieved_entities, retrieved_relations = self._filter_relevant_subgraph(
                                all_entities, all_relations, query_keywords
                            )
                    except Exception as e:
                        logger.error(f"从checkpoint中提取实体和关系失败: {e}", exc_info=True)
                
                # 4. 如果仍然没有结果，尝试从kag_results中提取并过滤
                if not retrieved_entities and not retrieved_relations:
                    logger.info("从kag_results中提取实体和关系，然后过滤")
                    entity_id_set = set()  # 用于去重
                    relation_key_set = set()  # 用于去重
                    
                    # 从kag_results的tasks中提取检索到的实体和关系
                    all_entities = []
                    all_relations = []
                    for kag_result in kag_results:
                        tasks = kag_result.get("tasks", [])
                        for task in tasks:
                            # 从task的memory中提取
                            task_memory = task.get("memory", {})
                            if isinstance(task_memory, dict):
                                # 从retriever结果中提取实体和关系
                                if "retriever" in task_memory:
                                    retriever_output = task_memory["retriever"]
                                    self._extract_entities_relations_from_retriever_output(
                                        retriever_output, all_entities, all_relations, entity_id_set, relation_key_set
                                    )
                                
                                # 从graph_data中提取
                                if "graph_data" in task_memory:
                                    graph_data = task_memory["graph_data"]
                                    self._extract_entities_relations_from_graph_data(
                                        graph_data, all_entities, all_relations, entity_id_set, relation_key_set
                                    )
                            
                            # 从task的result中提取
                            task_result = task.get("result")
                            if task_result:
                                self._extract_entities_relations_from_retriever_output(
                                    task_result, all_entities, all_relations, entity_id_set, relation_key_set
                                )
                    
                    # 过滤提取的实体和关系
                    if all_entities and all_relations:
                        retrieved_entities, retrieved_relations = self._filter_relevant_subgraph(
                            all_entities, all_relations, query_keywords
                        )
            
            logger.info(f"过滤后的实体数量: {len(retrieved_entities)}, 关系数量: {len(retrieved_relations)}")
            
            # 提取筛选参数信息（从step_results中提取）
            filter_params_list = []
            for step_idx, step_result in enumerate(step_results):
                if step_result.get("success"):
                    tool_name = step_result.get("tool", "")
                    step_params = step_result.get("params", {})
                    is_default = step_result.get("is_default", False)
                    
                    # 跳过使用默认值的工具
                    if is_default:
                        continue
                    
                    # 为每个工具调用创建一个独立的参数字典
                    step_filter_params = {}
                    
                    if tool_name == "buffer_filter_tool":
                        buffer_dist = step_params.get("buffer_distance")
                        if buffer_dist is not None:
                            step_filter_params["缓冲区距离"] = f"{buffer_dist} 米"
                    elif tool_name == "elevation_filter_tool":
                        min_elev = step_params.get("min_elev")
                        max_elev = step_params.get("max_elev")
                        if min_elev is not None or max_elev is not None:
                            elev_str = ""
                            if min_elev is not None:
                                elev_str += f"{min_elev} 米"
                            if max_elev is not None:
                                if elev_str:
                                    elev_str += " - "
                                elev_str += f"{max_elev} 米"
                            step_filter_params["高程范围"] = elev_str
                    elif tool_name == "slope_filter_tool":
                        min_slope = step_params.get("min_slope")
                        max_slope = step_params.get("max_slope")
                        if min_slope is not None or max_slope is not None:
                            slope_str = ""
                            if min_slope is not None:
                                slope_str += f"{min_slope}°"
                            if max_slope is not None:
                                if slope_str:
                                    slope_str += " - "
                                slope_str += f"{max_slope}°"
                            step_filter_params["坡度范围"] = slope_str
                    elif tool_name == "vegetation_filter_tool":
                        veg_types = step_params.get("vegetation_types", [])
                        exclude_types = step_params.get("exclude_types", [])
                        if veg_types:
                            veg_names = {
                                10: "树", 20: "灌木", 30: "草地", 40: "耕地",
                                50: "建筑", 60: "裸地/稀疏植被", 70: "雪和冰",
                                80: "水体", 90: "湿地", 95: "苔原", 100: "永久性水体"
                            }
                            veg_list = [veg_names.get(v, str(v)) for v in veg_types]
                            step_filter_params["植被类型"] = ", ".join(veg_list)
                        elif exclude_types:
                            veg_names = {
                                10: "树", 20: "灌木", 30: "草地", 40: "耕地",
                                50: "建筑", 60: "裸地/稀疏植被", 70: "雪和冰",
                                80: "水体", 90: "湿地", 95: "苔原", 100: "永久性水体"
                            }
                            exclude_list = [veg_names.get(v, str(v)) for v in exclude_types]
                            step_filter_params["排除植被类型"] = ", ".join(exclude_list)
                    elif tool_name == "relative_position_filter_tool":
                        reference_point = step_params.get("reference_point", {})
                        reference_direction = step_params.get("reference_direction")
                        position_types = step_params.get("position_types", [])
                        if reference_point:
                            lon = reference_point.get("lon")
                            lat = reference_point.get("lat")
                            if lon is not None and lat is not None:
                                step_filter_params["参考点坐标"] = f"({lon:.6f}, {lat:.6f})"
                        if reference_direction is not None:
                            step_filter_params["参考方向"] = f"{reference_direction}°"
                        if position_types:
                            step_filter_params["相对位置类型"] = ", ".join(position_types)
                    elif tool_name == "distance_filter_tool":
                        reference_point = step_params.get("reference_point", {})
                        max_distance = step_params.get("max_distance")
                        if reference_point:
                            lon = reference_point.get("lon")
                            lat = reference_point.get("lat")
                            if lon is not None and lat is not None:
                                step_filter_params["参考点坐标"] = f"({lon:.6f}, {lat:.6f})"
                        if max_distance is not None:
                            step_filter_params["最大距离"] = f"{max_distance} 米"
                    elif tool_name == "area_filter_tool":
                        min_area_km2 = step_params.get("min_area_km2")
                        if min_area_km2 is not None:
                            step_filter_params["最小面积"] = f"{min_area_km2} 平方公里"
                    
                    # 如果有参数，添加到列表
                    if step_filter_params:
                        filter_params_list.append({
                            "step": step_idx + 1,
                            "tool": tool_name,
                            "params": step_filter_params
                        })
            
            # 1. 保存区域信息到regions文件夹
            regions_data = {
                "result_file": result_file.name,
                "timestamp": datetime.now().isoformat(),
                "unit": unit,
                "original_query": original_query,
                "regions": regions,
                "reference_points": reference_points,
                "filter_params": filter_params_list
            }
            regions_path = regions_dir / f"{base_name}.json"
            with open(regions_path, "w", encoding="utf-8") as f:
                json.dump(regions_data, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存区域信息: {regions_path}")
            
            # 2. 保存LLM思考结果到llm_thinking文件夹
            llm_thinking_data = {
                "result_file": result_file.name,
                "timestamp": datetime.now().isoformat(),
                "unit": unit,
                "original_query": original_query,
                "first_llm_response": plan.get("first_llm_response", ""),
                "second_llm_response": plan.get("second_llm_response", ""),
                "kag_qa_results": kag_qa_results,
                "retrieved_entities": retrieved_entities,
                "retrieved_relations": retrieved_relations
            }
            llm_thinking_path = llm_thinking_dir / f"{base_name}.json"
            with open(llm_thinking_path, "w", encoding="utf-8") as f:
                json.dump(llm_thinking_data, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存LLM思考结果: {llm_thinking_path}")
            
            # 3. 保存实体关系图到kg_graph_images文件夹（生成静态图片）
            kg_graph_image_filename = None
            if retrieved_entities or retrieved_relations:
                try:
                    import matplotlib.pyplot as plt
                    import matplotlib
                    import networkx as nx
                    
                    matplotlib.use('Agg')
                    
                    fig, ax = plt.subplots(figsize=(16, 12))
                    ax.set_facecolor('#f8f9fa')
                    
                    # 扩展实体类型颜色映射
                    entity_type_colors = {
                        "MilitaryUnit": "#FF6B6B",
                        "TerrainFeature": "#4ECDC4",
                        "Weapon": "#FFE66D",
                        "Obstacle": "#95E1D3",
                        "DefensePosition": "#F38181",
                        "CombatPosition": "#AA96DA",
                        "UnitOrganization": "#FCBAD3",
                        "CombatTask": "#A8E6CF",
                        "FireSupport": "#FFD3A5",
                        "ObservationPost": "#FD9853",
                        "KillZone": "#A8DADC",
                        "ObstacleBelt": "#457B9D",
                        "SupportPoint": "#E63946",
                        "ApproachRoute": "#F1FAEE",
                        "Person": "#FF9F1C",
                        "Organization": "#2EC4B6",
                        "Equipment": "#E76F51",
                        "Location": "#8338EC",
                        "Event": "#3A86FF",
                        "Concept": "#FB5607",
                        "Object": "#8AC926",
                        "Action": "#118AB2",
                        "Attribute": "#073B4C",
                        "Unknown": "#6C757D"
                    }
                    
                    G = nx.DiGraph()
                    
                    entity_map = {}
                    for entity in retrieved_entities:
                        entity_id = entity.get("id", "")
                        entity_name = entity.get("name", entity_id)
                        entity_type = entity.get("type", "Unknown")
                        
                        # 标准化实体类型名称（去除空格，转换为驼峰命名）
                        normalized_type = entity_type.strip()
                        
                        # 尝试获取颜色，如果没有匹配的类型，使用基于类型名称的哈希颜色
                        if normalized_type in entity_type_colors:
                            color = entity_type_colors[normalized_type]
                        else:
                            # 基于类型名称生成一致的颜色
                            import hashlib
                            hash_val = hashlib.md5(normalized_type.encode()).hexdigest()[:6]
                            color = f"#{hash_val}"
                        
                        G.add_node(
                            entity_id,
                            label=entity_name,
                            type=normalized_type,
                            color=color
                        )
                        entity_map[entity_id] = entity
                    
                    for relation in retrieved_relations:
                        source = relation.get("source", "")
                        target = relation.get("target", "")
                        relation_type = relation.get("type", "Unknown")
                        
                        if source in entity_map and target in entity_map:
                            G.add_edge(
                                source,
                                target,
                                label=relation_type
                            )
                    
                    if len(G.nodes()) > 0:
                        # 根据节点数量选择布局算法，优先保证节点不重叠
                        import numpy as np
                        
                        if len(G.nodes()) <= 10:
                            # 对于小型图，使用circular_layout（环形布局，节点间距均匀）
                            pos = nx.circular_layout(G, scale=2)
                        elif len(G.nodes()) <= 20:
                            # 对于中型图，使用shell_layout（分层布局）
                            # 计算层数
                            n = len(G.nodes())
                            layers = [list(G.nodes())[:n//2], list(G.nodes())[n//2:]]
                            pos = nx.shell_layout(G, nlist=layers, scale=2)
                        else:
                            # 对于大型图，使用spring_layout并大幅增加排斥力
                            pos = nx.spring_layout(G, k=2.0, iterations=300, scale=3, center=(0, 0))
                        
                        # 后处理：强制分离节点，确保最小距离
                        min_dist = 0.25  # 增加最小距离
                        nodes = list(G.nodes())
                        
                        # 多次迭代调整，确保所有节点都分开
                        for iteration in range(10):  # 最多迭代10次
                            moved = False
                            for i in range(len(nodes)):
                                for j in range(i + 1, len(nodes)):
                                    pos_i = np.array(pos[nodes[i]])
                                    pos_j = np.array(pos[nodes[j]])
                                    dist = np.linalg.norm(pos_i - pos_j)
                                    
                                    if dist < min_dist:
                                        # 计算需要移动的距离
                                        direction = pos_j - pos_i
                                        if np.linalg.norm(direction) > 0:
                                            direction = direction / np.linalg.norm(direction)
                                        else:
                                            # 随机方向
                                            direction = np.random.randn(2)
                                            direction = direction / np.linalg.norm(direction)
                                        
                                        # 计算需要移动的距离，稍微超过最小距离以确保分开
                                        move_dist = (min_dist - dist) / 2 + 0.02
                                        
                                        # 移动两个节点
                                        pos[nodes[i]] = pos_i - direction * move_dist
                                        pos[nodes[j]] = pos_j + direction * move_dist
                                        moved = True
                            
                            # 如果没有节点需要移动，提前结束
                            if not moved:
                                break
                        
                        # 最后调整：确保所有节点都在画布范围内
                        all_pos = np.array([pos[node] for node in G.nodes()])
                        min_pos = np.min(all_pos, axis=0)
                        max_pos = np.max(all_pos, axis=0)
                        
                        # 计算缩放因子，确保所有节点都在合理范围内
                        current_range = max(max_pos[0] - min_pos[0], max_pos[1] - min_pos[1])
                        if current_range > 4:
                            scale_factor = 4 / current_range
                            for node in G.nodes():
                                pos[node] = pos[node] * scale_factor
                        
                        node_colors = [G.nodes[node].get('color', '#6C757D') for node in G.nodes()]
                        node_labels = {node: G.nodes[node].get('label', node)[:20] for node in G.nodes()}
                        
                        # 绘制节点
                        nx.draw_networkx_nodes(
                            G, pos,
                            node_color=node_colors,
                            node_size=2200,
                            alpha=0.95,
                            edgecolors='#ffffff',
                            linewidths=2,
                            ax=ax
                        )
                        
                        # 绘制边
                        nx.draw_networkx_edges(
                            G, pos,
                            edge_color='#495057',
                            width=2.5,
                            alpha=0.8,
                            arrowsize=25,
                            arrowstyle='->',
                            connectionstyle='arc3,rad=0.1',
                            ax=ax
                        )
                        
                        # 绘制节点标签
                        nx.draw_networkx_labels(
                            G, pos,
                            labels=node_labels,
                            font_size=11,
                            font_weight='bold',
                            font_family='Microsoft YaHei',
                            ax=ax
                        )
                        
                        # 绘制边标签
                        edge_labels = nx.get_edge_attributes(G, 'label')
                        nx.draw_networkx_edge_labels(
                            G, pos,
                            edge_labels=edge_labels,
                            font_size=9,
                            font_color='#212529',
                            font_family='Microsoft YaHei',
                            bbox=dict(facecolor='white', alpha=0.9, edgecolor='none', boxstyle='round,pad=0.3'),
                            ax=ax
                        )
                        
                        # 添加图例
                        unique_types = set(G.nodes[node].get('type', 'Unknown') for node in G.nodes())
                        legend_elements = []
                        for entity_type in unique_types:
                            color = entity_type_colors.get(entity_type, '#6C757D')
                            legend_elements.append(
                                plt.Line2D([0], [0], marker='o', color='w', label=entity_type, 
                                          markerfacecolor=color, markersize=10, markeredgewidth=2, markeredgecolor='white')
                            )
                        
                        if legend_elements:
                            ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.25, 1), 
                                     title="实体类型", fontsize=9, title_fontsize=10)
                        
                        ax.set_title(f'实体关系图 ({len(retrieved_entities)} 个实体, {len(retrieved_relations)} 个关系)', 
                                   fontsize=18, fontweight='bold', pad=20, fontfamily='Microsoft YaHei')
                        ax.axis('off')
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        kg_graph_image_filename = f"kg_graph_{timestamp}.png"
                        
                        kg_graph_images_dir = PATHS["result_dir"] / "kg_graph_images"
                        kg_graph_images_dir.mkdir(parents=True, exist_ok=True)
                        kg_graph_image_path = kg_graph_images_dir / kg_graph_image_filename
                        
                        plt.tight_layout(rect=[0, 0, 0.8, 1])
                        plt.savefig(kg_graph_image_path, dpi=180, bbox_inches='tight', facecolor='white')
                        plt.close(fig)
                        
                        logger.info(f"已保存实体关系图: {kg_graph_image_path}")
                except Exception as e:
                    logger.error(f"保存实体关系图失败: {e}", exc_info=True)
            
            # 将图片文件名保存到llm_thinking_data中
            if kg_graph_image_filename:
                llm_thinking_data["kg_graph_image_filename"] = kg_graph_image_filename
                # 重新保存llm_thinking文件以包含图片文件名
                with open(llm_thinking_path, "w", encoding="utf-8") as f:
                    json.dump(llm_thinking_data, f, ensure_ascii=False, indent=2)
                logger.info(f"已更新LLM思考结果（包含图片文件名）: {llm_thinking_path}")
        except Exception as e:
            logger.error(f"保存结果metadata失败: {e}", exc_info=True)
            return None
        
        return kg_graph_image_filename
    
    def _extract_entities_relations_from_retriever_output(self, retriever_output, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set):
        """从retriever输出中提取实体和关系"""
        if isinstance(retriever_output, dict):
            # 检查是否有graph_data或kg_graph
            graph_data = retriever_output.get("graph_data") or retriever_output.get("kg_graph")
            if graph_data:
                self._extract_entities_relations_from_graph_data(
                    graph_data, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set
                )
            
            # 检查是否有chunks，从chunks中提取实体和关系
            chunks = retriever_output.get("chunks", [])
            for chunk in chunks:
                if isinstance(chunk, dict):
                    # 尝试从chunk的metadata中提取实体和关系
                    chunk_metadata = chunk.get("metadata", {})
                    if chunk_metadata:
                        # 检查是否有实体和关系信息
                        entities = chunk_metadata.get("entities", [])
                        relations = chunk_metadata.get("relations", [])
                        if entities:
                            for entity in entities:
                                if isinstance(entity, dict):
                                    entity_id = entity.get("id") or entity.get("name", "")
                                    if entity_id and entity_id not in entity_id_set:
                                        entity_id_set.add(entity_id)
                                        retrieved_entities.append({
                                            "id": entity_id,
                                            "name": entity.get("name", entity_id),
                                            "type": entity.get("type") or entity.get("label", "Unknown"),
                                            "properties": entity.get("properties", {})
                                        })
                        if relations:
                            for relation in relations:
                                if isinstance(relation, dict):
                                    source = relation.get("source") or relation.get("from_id") or relation.get("from", "")
                                    target = relation.get("target") or relation.get("to_id") or relation.get("to", "")
                                    relation_type = relation.get("type") or relation.get("label", "Unknown")
                                    if source and target:
                                        relation_key = f"{source}->{target}->{relation_type}"
                                        if relation_key not in relation_key_set:
                                            relation_key_set.add(relation_key)
                                            retrieved_relations.append({
                                                "source": source,
                                                "target": target,
                                                "type": relation_type,
                                                "properties": relation.get("properties", {})
                                            })
    
    def _extract_keywords_from_query(self, query):
        """从问题中提取关键词"""
        import re
        import jieba
        
        # 移除标点符号
        query = re.sub(r'[，。！？；：“”‘’（）【】]', ' ', query)
        
        # 使用jieba分词
        words = jieba.cut(query)
        
        # 过滤停用词和短词
        stop_words = {'我', '你', '他', '她', '它', '们', '的', '了', '是', '在', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        keywords = []
        
        for word in words:
            word = word.strip()
            if word and len(word) > 1 and word not in stop_words:
                keywords.append(word)
        
        # 去重并返回
        return list(set(keywords))
    
    def _filter_relevant_subgraph(self, all_entities, all_relations, query_keywords):
        """根据关键词过滤相关的子图谱"""
        relevant_entities = []
        relevant_relations = []
        
        if not all_entities or not query_keywords:
            return relevant_entities, relevant_relations
        
        # 1. 构建实体ID到实体的映射
        entity_map = {entity.get("id"): entity for entity in all_entities}
        
        # 2. 找出与关键词直接相关的实体（核心实体）
        core_entity_ids = set()
        for entity_id, entity in entity_map.items():
            entity_name = entity.get("name", "").lower()
            entity_type = entity.get("type", "").lower()
            
            # 检查实体名称或类型是否与关键词精确匹配
            for keyword in query_keywords:
                keyword_lower = keyword.lower()
                
                # 更精确的匹配逻辑：
                # 1. 完全匹配实体名称
                # 2. 实体名称是关键词的精确子词（不是子字符串）
                # 3. 完全匹配实体类型
                if (entity_name == keyword_lower or 
                    self._is_exact_subword(entity_name, keyword_lower) or 
                    entity_type == keyword_lower):
                    core_entity_ids.add(entity_id)
                    break
        
        # 3. 找出与核心实体直接相连的关系
        related_relation_keys = set()
        for relation in all_relations:
            source = relation.get("source")
            target = relation.get("target")
            
            # 如果关系的源或目标是核心实体，则保留该关系
            if source in core_entity_ids or target in core_entity_ids:
                # 生成关系键以去重
                relation_key = f"{source}->{target}->{relation.get('type', '')}"
                if relation_key not in related_relation_keys:
                    related_relation_keys.add(relation_key)
                    relevant_relations.append(relation)
        
        # 4. 找出与核心实体直接相连的其他实体（扩展实体）
        extended_entity_ids = set(core_entity_ids)
        for relation in relevant_relations:
            source = relation.get("source")
            target = relation.get("target")
            
            if source in entity_map:
                extended_entity_ids.add(source)
            if target in entity_map:
                extended_entity_ids.add(target)
        
        # 5. 收集所有相关实体（核心实体 + 直接相连的实体）
        for entity_id in extended_entity_ids:
            if entity_id in entity_map:
                relevant_entities.append(entity_map[entity_id])
        
        return relevant_entities, relevant_relations
    
    def _is_exact_subword(self, text, keyword):
        """检查keyword是否是text的精确子词（不是子字符串）"""
        import re
        
        # 边界匹配：关键词前后是词边界或标点符号
        # 例如："坦克" 是 "主战坦克" 的子词，但不是 "反坦克炮" 的子词
        pattern = r'(^|\W)' + re.escape(keyword) + r'(\W|$)'
        return bool(re.search(pattern, text))
    
    def _extract_entities_relations_from_graph_data(self, graph_data, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set):
        """从graph_data中提取实体和关系"""
        if isinstance(graph_data, dict):
            # 提取节点（实体）
            nodes = graph_data.get("nodes", graph_data.get("resultNodes", []))
            if not nodes and "result_nodes" in graph_data:
                nodes = graph_data.get("result_nodes", [])
            
            for node in nodes:
                if isinstance(node, dict):
                    entity_id = node.get("id") or node.get("name", "")
                    if entity_id and entity_id not in entity_id_set:
                        entity_id_set.add(entity_id)
                        retrieved_entities.append({
                            "id": entity_id,
                            "name": node.get("name", entity_id),
                            "type": node.get("type") or node.get("label", "Unknown"),
                            "properties": node.get("properties", {})
                        })
            
            # 提取边（关系）
            edges = graph_data.get("edges", graph_data.get("resultEdges", []))
            if not edges and "result_edges" in graph_data:
                edges = graph_data.get("result_edges", [])
            
            for edge in edges:
                if isinstance(edge, dict):
                    source = edge.get("from_id") or edge.get("from") or edge.get("source", "")
                    target = edge.get("to_id") or edge.get("to") or edge.get("target", "")
                    relation_type = edge.get("label") or edge.get("type", "Unknown")
                    if source and target:
                        relation_key = f"{source}->{target}->{relation_type}"
                        if relation_key not in relation_key_set:
                            relation_key_set.add(relation_key)
                            retrieved_relations.append({
                                "source": source,
                                "target": target,
                                "type": relation_type,
                                "properties": edge.get("properties", {})
                            })
        elif hasattr(graph_data, "result_nodes") and hasattr(graph_data, "result_edges"):
            # 如果是KgGraph对象，尝试转换为字典
            try:
                if hasattr(graph_data, "to_dict"):
                    graph_dict = graph_data.to_dict()
                    self._extract_entities_relations_from_graph_data(
                        graph_dict, retrieved_entities, retrieved_relations, entity_id_set, relation_key_set
                    )
                else:
                    # 直接从对象属性提取
                    nodes = getattr(graph_data, "result_nodes", [])
                    edges = getattr(graph_data, "result_edges", [])
                    for node in nodes:
                        if hasattr(node, "id"):
                            entity_id = getattr(node, "id", "")
                            if entity_id and entity_id not in entity_id_set:
                                entity_id_set.add(entity_id)
                                retrieved_entities.append({
                                    "id": entity_id,
                                    "name": getattr(node, "name", entity_id),
                                    "type": getattr(node, "label", "Unknown"),
                                    "properties": getattr(node, "properties", {}) if hasattr(node, "properties") else {}
                                })
                    for edge in edges:
                        if hasattr(edge, "from_id") or hasattr(edge, "_from"):
                            source = getattr(edge, "from_id", "") or getattr(edge, "_from", "")
                            target = getattr(edge, "to_id", "") or getattr(edge, "to", "")
                            relation_type = getattr(edge, "label", "Unknown")
                            if source and target:
                                relation_key = f"{source}->{target}->{relation_type}"
                                if relation_key not in relation_key_set:
                                    relation_key_set.add(relation_key)
                                    retrieved_relations.append({
                                        "source": source,
                                        "target": target,
                                        "type": relation_type,
                                        "properties": getattr(edge, "properties", {}) if hasattr(edge, "properties") else {}
                                    })
            except Exception as e:
                logger.debug(f"从graph_data对象提取实体和关系失败: {e}")
    
    def _parse_regions_from_task(self, task_text: str) -> List[Dict]:
        """
        从任务文本中解析区域信息（前沿区域、调整线S、调整线P、后方保障区）
        
        格式示例：
        前沿区域：左上角: (118.5, 31.5)右下角: (118.552, 31.545)
        调整线S：左上角: (118.5, 31.518)右下角: (118.552, 31.563)
        调整线P：左上角: (118.5, 31.536)右下角: (118.552, 31.581)
        后方保障区：左上角: (118.552, 31.581)右下角: (118.604, 31.626)
        
        Returns:
            List[Dict]: 区域信息列表，每个元素包含 name, top_left, bottom_right
        """
        regions = []
        
        # 匹配区域名称和坐标的模式
        # 匹配格式：区域名：左上角: (lon, lat)右下角: (lon, lat)
        pattern = r'([^：:]+)[：:]\s*左上角[：:]\s*\(([\d.]+),\s*([\d.]+)\)\s*右下角[：:]\s*\(([\d.]+),\s*([\d.]+)\)'
        
        matches = re.finditer(pattern, task_text)
        for match in matches:
            region_name = match.group(1).strip()
            top_left_lon = float(match.group(2))
            top_left_lat = float(match.group(3))
            bottom_right_lon = float(match.group(4))
            bottom_right_lat = float(match.group(5))
            
            regions.append({
                "name": region_name,
                "top_left": (top_left_lon, top_left_lat),
                "bottom_right": (bottom_right_lon, bottom_right_lat)
            })
        
        return regions
