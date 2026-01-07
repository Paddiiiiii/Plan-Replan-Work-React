"""
LLM相关工具函数
"""
import json
import re
import logging
import requests
from typing import Dict, List
from config import LLM_CONFIG

logger = logging.getLogger(__name__)


def call_llm(messages: List[Dict], timeout: int = None) -> str:
    """
    调用LLM API
    
    Args:
        messages: 消息列表
        timeout: 超时时间（秒），默认使用配置中的timeout
        
    Returns:
        LLM响应文本
        
    Raises:
        requests.exceptions.RequestException: API调用失败
        ValueError: 响应格式错误
    """
    if timeout is None:
        timeout = LLM_CONFIG.get("timeout", 120)
    
    payload = {
        **LLM_CONFIG,
        "messages": messages
    }
    
    try:
        response = requests.post(
            LLM_CONFIG["api_endpoint"], 
            json=payload, 
            timeout=timeout
        )
        response.raise_for_status()
        result = response.json()
        
        if "choices" not in result or len(result["choices"]) == 0:
            raise ValueError("LLM响应格式错误：缺少choices字段")
        
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        raise Exception(f"LLM API调用失败: {str(e)}")
    except (KeyError, IndexError) as e:
        raise Exception(f"LLM响应解析失败: {str(e)}, 响应: {result}")


def _clean_json_string(json_str: str) -> str:
    """清理JSON字符串，移除注释和其他无效字符"""
    # 移除单行注释 (// ...)
    json_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
    # 移除多行注释 (/* ... */)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
    # 移除尾随逗号（在}或]之前）
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    return json_str.strip()

def parse_plan_response(response: str) -> Dict:
    """
    解析LLM响应中的计划JSON
    
    Args:
        response: LLM响应文本
        
    Returns:
        解析后的计划字典
    """
    
    # 首先尝试从代码块中提取JSON
    json_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response)
    if json_block_match:
        try:
            json_str = json_block_match.group(1)
            # 清理JSON字符串（移除注释等）
            json_str = _clean_json_string(json_str)
            plan = json.loads(json_str)
            logger.info("成功从JSON代码块解析计划")
            return _normalize_plan(plan, response, json_block_match.start())
        except json.JSONDecodeError as e:
            logger.error(f"解析JSON代码块失败: {e}")
            logger.error(f"JSON字符串前500字符: {json_str[:500]}")
            # 尝试更激进的清理
            try:
                # 移除所有注释和尾随逗号后重试
                json_str_clean = _clean_json_string(json_block_match.group(1))
                plan = json.loads(json_str_clean)
                logger.info("清理后成功解析JSON代码块")
                return _normalize_plan(plan, response, json_block_match.start())
            except:
                pass
        except Exception as e:
            logger.error(f"解析JSON代码块时发生其他错误: {e}", exc_info=True)
    
    # 尝试从文本中提取JSON对象（从后往前找，通常JSON在最后）
    json_match = None
    matches = list(re.finditer(r'\{[\s\S]*\}', response))
    # 从后往前尝试解析
    for match in reversed(matches):
        try:
            json_str = match.group()
            # 清理JSON字符串
            json_str_clean = _clean_json_string(json_str)
            test_json = json.loads(json_str_clean)
            json_match = match
            break
        except:
            continue
    
    if json_match:
        try:
            json_str = json_match.group()
            # 清理JSON字符串
            json_str_clean = _clean_json_string(json_str)
            plan = json.loads(json_str_clean)
            logger.info("成功从文本中解析JSON对象")
            return _normalize_plan(plan, response, json_match.start())
        except json.JSONDecodeError as e:
            logger.error(f"解析JSON对象失败: {e}")
            logger.error(f"JSON字符串前500字符: {json_str[:500]}")
        except Exception as e:
            logger.error(f"解析JSON对象时发生其他错误: {e}", exc_info=True)
    
    # 如果无法解析，记录错误并返回默认结构
    logger.warning(f"无法解析LLM响应中的JSON，使用回退计划。响应前500字符: {response[:500]}")
    return _create_fallback_plan(response)


def _normalize_plan(plan: Dict, response: str, json_start_pos: int) -> Dict:
    """规范化计划结构"""
    # 处理多任务模式
    if "sub_plans" in plan:
        for sub_plan in plan.get("sub_plans", []):
            if "steps" not in sub_plan:
                sub_plan["steps"] = []
    else:
        # 单任务模式
        if "steps" not in plan:
            plan["steps"] = []
        if "estimated_steps" not in plan:
            plan["estimated_steps"] = len(plan.get("steps", []))
    
    # 处理goal字段：合并思考部分
    thinking_part = response[:json_start_pos].strip()
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


def _create_fallback_plan(response: str) -> Dict:
    """创建回退计划（基于关键词匹配）"""
    # 检查是否是多任务模式（包含多个单位）
    multi_unit_keywords = ["无人机", "坦克", "步兵", "多个", "分别", "各自", "sub_plans", "子计划"]
    is_multi_task = any(keyword in response for keyword in multi_unit_keywords)
    
    if is_multi_task:
        # 尝试从响应中提取单位信息
        units = []
        if "无人机" in response:
            units.append("无人机")
        if "坦克" in response:
            units.append("坦克")
        if "步兵" in response:
            units.append("步兵")
        
        # 如果没有找到具体单位，使用默认单位
        if not units:
            units = ["单位1", "单位2", "单位3"]
        
        # 为每个单位创建子计划
        sub_plans = []
        for unit in units:
            steps = []
            if "缓冲区" in response or "距离" in response:
                steps.append({
                    "step_id": 1, 
                    "description": "根据建筑和道路距离筛选空地", 
                    "type": "buffer", 
                    "tool": "buffer_filter_tool",
                    "params": {}
                })
            if "高程" in response or "海拔" in response:
                steps.append({
                    "step_id": len(steps) + 1, 
                    "description": "根据高程范围筛选", 
                    "type": "elevation", 
                    "tool": "elevation_filter_tool",
                    "params": {}
                })
            if "坡度" in response or "倾斜" in response:
                steps.append({
                    "step_id": len(steps) + 1, 
                    "description": "根据坡度范围筛选", 
                    "type": "slope", 
                    "tool": "slope_filter_tool",
                    "params": {}
                })
            
            # 植被类型关键词
            vegetation_keywords = [
                "植被", "草地", "林地", "树木", "耕地", "裸地", "水体", 
                "湿地", "苔原", "稀疏植被", "永久性水体", "雪和冰"
            ]
            if any(keyword in response for keyword in vegetation_keywords):
                steps.append({
                    "step_id": len(steps) + 1, 
                    "description": "根据植被类型筛选", 
                    "type": "vegetation", 
                    "tool": "vegetation_filter_tool",
                    "params": {}
                })
            
            sub_plans.append({
                "unit": unit,
                "steps": steps
            })
        
        return {
            "task": "",
            "goal": response,
            "sub_plans": sub_plans
        }
    else:
        # 单任务模式
        steps = []
        
        if "缓冲区" in response or "距离" in response:
            steps.append({
                "step_id": 1, 
                "description": "根据建筑和道路距离筛选空地", 
                "type": "buffer", 
                "tool": "buffer_filter_tool",
                "params": {}
            })
        if "高程" in response or "海拔" in response:
            steps.append({
                "step_id": len(steps) + 1, 
                "description": "根据高程范围筛选", 
                "type": "elevation", 
                "tool": "elevation_filter_tool",
                "params": {}
            })
        if "坡度" in response or "倾斜" in response:
            steps.append({
                "step_id": len(steps) + 1, 
                "description": "根据坡度范围筛选", 
                "type": "slope", 
                "tool": "slope_filter_tool",
                "params": {}
            })
        
        # 植被类型关键词
        vegetation_keywords = [
            "植被", "草地", "林地", "树木", "耕地", "裸地", "水体", 
            "湿地", "苔原", "稀疏植被", "永久性水体", "雪和冰"
        ]
        if any(keyword in response for keyword in vegetation_keywords):
            steps.append({
                "step_id": len(steps) + 1, 
                "description": "根据植被类型筛选", 
                "type": "vegetation", 
                "tool": "vegetation_filter_tool",
                "params": {}
            })
        
        return {
            "task": "",
            "goal": response,
            "steps": steps,
            "estimated_steps": len(steps)
        }

