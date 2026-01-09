"""
LLM相关工具函数
"""
import json
import re
import logging
import requests
import time
import threading
from typing import Dict, List
from collections import deque
from config import LLM_CONFIG

logger = logging.getLogger(__name__)


class LLMRateLimiter:
    """LLM速率限制器，支持RPM和TPM双重限制"""
    
    def __init__(self, rpm: int = 2000, tpm: int = 500000):
        """
        初始化速率限制器
        
        Args:
            rpm: 每分钟最大请求数
            tpm: 每分钟最大tokens数
        """
        self.rpm = rpm
        self.tpm = tpm
        self.lock = threading.Lock()
        
        # 请求时间戳队列（用于RPM限制）
        self.request_timestamps = deque()
        
        # Token使用记录队列（用于TPM限制）
        # 每个元素是 (timestamp, token_count)
        self.token_usage_records = deque()
        
        # 时间窗口（60秒）
        self.time_window = 60.0
    
    def acquire(self, estimated_tokens: int = 0):
        """
        获取许可，如果超过限制则等待
        
        Args:
            estimated_tokens: 预估的token数量（用于TPM限制）
        """
        with self.lock:
            now = time.time()
            
            # 清理过期的请求记录（RPM限制）
            while (self.request_timestamps and 
                   now - self.request_timestamps[0] >= self.time_window):
                self.request_timestamps.popleft()
            
            # 清理过期的token使用记录（TPM限制）
            while (self.token_usage_records and 
                   now - self.token_usage_records[0][0] >= self.time_window):
                self.token_usage_records.popleft()
            
            # 检查RPM限制
            if len(self.request_timestamps) >= self.rpm:
                # 需要等待直到最早的请求退出时间窗口
                wait_time = self.request_timestamps[0] + self.time_window - now
                if wait_time > 0:
                    logger.debug(f"RPM限制：等待 {wait_time:.2f} 秒")
                    time.sleep(wait_time)
                    now = time.time()
                    # 重新清理过期记录
                    while (self.request_timestamps and 
                           now - self.request_timestamps[0] >= self.time_window):
                        self.request_timestamps.popleft()
            
            # 检查TPM限制
            current_tpm = sum(record[1] for record in self.token_usage_records)
            if current_tpm + estimated_tokens > self.tpm:
                # 需要等待直到有足够的token配额
                if self.token_usage_records:
                    # 计算需要等待的时间（直到最早的token使用记录过期）
                    wait_time = self.token_usage_records[0][0] + self.time_window - now
                    if wait_time > 0:
                        logger.debug(f"TPM限制：等待 {wait_time:.2f} 秒（当前使用: {current_tpm}, 需要: {estimated_tokens}）")
                        time.sleep(wait_time)
                        now = time.time()
                        # 重新清理过期记录
                        while (self.token_usage_records and 
                               now - self.token_usage_records[0][0] >= self.time_window):
                            self.token_usage_records.popleft()
            
            # 记录本次请求
            self.request_timestamps.append(now)
            if estimated_tokens > 0:
                self.token_usage_records.append((now, estimated_tokens))
    
    def record_token_usage(self, actual_tokens: int):
        """
        记录实际使用的token数量（用于更精确的TPM限制）
        
        Args:
            actual_tokens: 实际使用的token数量
        """
        with self.lock:
            now = time.time()
            # 如果实际token数量与预估不同，更新最后一条记录
            if self.token_usage_records:
                last_record = self.token_usage_records[-1]
                # 如果最后一条记录是最近1秒内的，更新它
                if now - last_record[0] < 1.0:
                    self.token_usage_records[-1] = (last_record[0], actual_tokens)
                else:
                    # 否则添加新记录
                    self.token_usage_records.append((now, actual_tokens))
            else:
                self.token_usage_records.append((now, actual_tokens))


# 创建全局速率限制器实例
_rate_limit_config = LLM_CONFIG.get("rate_limit", {})
_llm_rate_limiter = LLMRateLimiter(
    rpm=_rate_limit_config.get("rpm", 2000),
    tpm=_rate_limit_config.get("tpm", 500000)
)


def _estimate_tokens(messages: List[Dict]) -> int:
    """
    估算消息的token数量（简单估算：1 token ≈ 4 字符）
    
    Args:
        messages: 消息列表
        
    Returns:
        估算的token数量
    """
    total_chars = 0
    for msg in messages:
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
    # 简单估算：1 token ≈ 4 字符，加上一些开销
    estimated_tokens = int(total_chars / 4) + 100
    return estimated_tokens


def call_llm(messages: List[Dict], timeout: int = None) -> str:
    """
    调用LLM API（带速率限制）
    
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
    
    # 估算token数量
    estimated_tokens = _estimate_tokens(messages)
    
    # 应用速率限制
    _llm_rate_limiter.acquire(estimated_tokens)
    
    payload = {
        **LLM_CONFIG,
        "messages": messages
    }
    
    # 移除rate_limit配置，避免发送到API
    payload.pop("rate_limit", None)
    
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
        
        response_content = result["choices"][0]["message"]["content"]
        
        # 尝试获取实际使用的token数量（如果API返回了usage信息）
        if "usage" in result:
            usage = result["usage"]
            actual_tokens = usage.get("total_tokens", 0)
            if actual_tokens > 0:
                _llm_rate_limiter.record_token_usage(actual_tokens)
        
        return response_content
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
            logger.error(f"JSON字符串前1000字符: {json_str[:1000]}")
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
            logger.error(f"JSON字符串前1000字符: {json_str[:1000]}")
        except Exception as e:
            logger.error(f"解析JSON对象时发生其他错误: {e}", exc_info=True)
    
    # 如果无法解析，尝试查找可能的JSON开始位置
    # 查找最后一个包含"{"的完整行，可能JSON从这里开始但被截断了
    lines = response.split('\n')
    json_start_line = -1
    for i in range(len(lines) - 1, -1, -1):
        if '{' in lines[i] and ('"task"' in lines[i] or '"steps"' in lines[i] or '"sub_plans"' in lines[i]):
            json_start_line = i
            break
    
    if json_start_line >= 0:
        # 尝试从找到的行开始构建JSON
        json_candidate = '\n'.join(lines[json_start_line:])
        # 尝试补全可能的截断JSON
        if not json_candidate.rstrip().endswith('}'):
            # 尝试补全
            open_braces = json_candidate.count('{')
            close_braces = json_candidate.count('}')
            missing_braces = open_braces - close_braces
            if missing_braces > 0:
                json_candidate += '\n' + '}' * missing_braces
        
        try:
            json_str_clean = _clean_json_string(json_candidate)
            plan = json.loads(json_str_clean)
            logger.warning("从不完整的响应中成功解析JSON（可能被截断）")
            return _normalize_plan(plan, response, len('\n'.join(lines[:json_start_line])))
        except:
            pass
    
    # 如果完全无法解析，返回空结构并记录详细错误
    logger.error(f"无法解析LLM响应中的JSON")
    logger.error(f"响应总长度: {len(response)} 字符")
    logger.error(f"响应开头1000字符:\n{response[:1000]}")
    logger.error(f"响应结尾1000字符:\n{response[-1000:]}")
    # 检查是否包含关键词
    if '"task"' in response or '"steps"' in response or '"sub_plans"' in response:
        logger.warning("响应中包含JSON关键词，但无法解析为有效JSON")
    else:
        logger.warning("响应中未找到JSON关键词，LLM可能未按要求输出JSON格式")
    
    return {
        "task": "",
        "goal": "无法解析LLM响应",
        "steps": [],
        "estimated_steps": 0,
        "error": "无法解析LLM响应中的JSON格式，请检查prompt和LLM输出。响应可能被截断或格式不正确。"
    }


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

