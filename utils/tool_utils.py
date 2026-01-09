"""
工具相关工具函数
"""
import json
from typing import Dict, List


def get_tools_schema_text(tools: Dict) -> str:
    """
    获取所有工具的schema文本
    
    Args:
        tools: 工具字典，key为工具名，value为工具实例
        
    Returns:
        格式化的工具schema文本
    """
    tools_schema = []
    for tool_name, tool in tools.items():
        schema = tool.get_schema()
        tools_schema.append(json.dumps(schema, ensure_ascii=False, indent=2))
    
    return "\n\n".join(tools_schema)


def prepare_step_input_path(
    step: Dict, 
    last_result_path: str, 
    tools: Dict,
    chainable_types: List[str] = None
) -> None:
    """
    为步骤准备input_geojson_path参数（链式调用支持）
    
    Args:
        step: 步骤字典
        last_result_path: 上一步的输出路径
        tools: 工具字典
        chainable_types: 支持链式调用的步骤类型列表
    """
    if not last_result_path:
        return
    
    if chainable_types is None:
        chainable_types = ["elevation", "slope", "vegetation", "relative_position"]
    
    # 确保params存在
    if "params" not in step:
        step["params"] = {}
    
    # 如果步骤指定了tool，检查工具参数
    tool_name = step.get("tool")
    if tool_name and tool_name in tools:
        tool = tools[tool_name]
        tool_params = tool.parameters
        if "input_geojson_path" in tool_params:
            if "input_geojson_path" not in step["params"] or not step["params"]["input_geojson_path"]:
                step["params"]["input_geojson_path"] = last_result_path
            return
    
    # 如果步骤类型支持链式调用，自动填充
    step_type = step.get("type")
    if step_type in chainable_types:
        if "input_geojson_path" not in step["params"] or not step["params"]["input_geojson_path"]:
            step["params"]["input_geojson_path"] = last_result_path

