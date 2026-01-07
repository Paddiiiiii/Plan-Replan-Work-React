"""
带限流的Embedding模型包装器
只对在线API进行速率限制，避免超限
"""
import time
import logging
from typing import Union, Iterable
from collections import deque
from threading import Lock
from kag.interface import VectorizeModelABC, EmbeddingVector

logger = logging.getLogger(__name__)


@VectorizeModelABC.register("rate_limited")
class RateLimitedVectorizeModel(VectorizeModelABC):
    """
    带限流的Embedding模型包装器
    对在线API进行速率限制，避免超限
    """
    
    def __init__(
        self,
        model: dict,  # 被包装的模型配置（在线API）
        max_rate: float = 30,  # 每秒最大请求数
        time_period: float = 1.0,  # 时间窗口（秒）
        vector_dimensions: int = 1024,
        **kwargs
    ):
        """
        初始化RateLimitedVectorizeModel
        
        Args:
            model: 被包装的模型配置（在线API）
            max_rate: 每秒最大请求数
            time_period: 时间窗口（秒）
            vector_dimensions: 向量维度
        """
        model_type = model.get("type", "openai")
        model_name = model.get("model", "unknown")
        name = f"rate_limited_{model_type}_{model_name}"
        super().__init__(name, vector_dimensions, max_rate, time_period)
        
        # 初始化被包装的模型
        self.wrapped_model = VectorizeModelABC.from_config(model)
        
        # 限流相关
        self.max_rate = max_rate
        self.time_period = time_period
        self.request_times = deque()  # 记录请求时间
        self.lock = Lock()
        
        logger.info(f"RateLimitedVectorizeModel初始化: 模型={model_type}, 限流={max_rate}/秒")
    
    def _rate_limit(self):
        """实现速率限制"""
        with self.lock:
            now = time.time()
            # 移除超出时间窗口的请求记录
            while self.request_times and self.request_times[0] < now - self.time_period:
                self.request_times.popleft()
            
            # 检查是否超过速率限制
            if len(self.request_times) >= self.max_rate:
                # 需要等待
                wait_time = self.request_times[0] + self.time_period - now
                if wait_time > 0:
                    logger.debug(f"速率限制：等待 {wait_time:.2f} 秒")
                    time.sleep(wait_time)
                    # 重新计算
                    now = time.time()
                    while self.request_times and self.request_times[0] < now - self.time_period:
                        self.request_times.popleft()
            
            # 记录本次请求时间
            self.request_times.append(time.time())
    
    def vectorize(
        self, texts: Union[str, Iterable[str]]
    ) -> Union[EmbeddingVector, Iterable[EmbeddingVector]]:
        """
        向量化文本，带限流
        
        Args:
            texts: 文本或文本列表
            
        Returns:
            向量或向量列表
        """
        # 应用速率限制
        self._rate_limit()
        
        # 调用被包装的模型
        try:
            result = self.wrapped_model.vectorize(texts)
            
            # 如果返回None，返回空向量避免后续错误
            if result is None:
                logger.warning("模型返回None，返回空向量")
                if isinstance(texts, str):
                    return [0.0] * self.vector_dimensions
                else:
                    return [[0.0] * self.vector_dimensions for _ in texts]
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"模型调用失败: {error_msg[:200]}")
            
            # 如果是速率限制错误，返回空向量
            if "403" in error_msg or "429" in error_msg or "rate limit" in error_msg.lower() or "rpm limit" in error_msg.lower():
                logger.warning("检测到速率限制错误，返回空向量")
                if isinstance(texts, str):
                    return [0.0] * self.vector_dimensions
                else:
                    return [[0.0] * self.vector_dimensions for _ in texts]
            
            # 其他错误也返回空向量，避免崩溃
            logger.warning(f"模型调用失败，返回空向量: {error_msg[:100]}")
            if isinstance(texts, str):
                return [0.0] * self.vector_dimensions
            else:
                return [[0.0] * self.vector_dimensions for _ in texts]
    
    async def avectorize(
        self, texts: Union[str, Iterable[str]]
    ) -> Union[EmbeddingVector, Iterable[EmbeddingVector]]:
        """
        异步向量化文本，带限流
        """
        # 应用速率限制
        self._rate_limit()
        
        try:
            if hasattr(self.wrapped_model, 'avectorize'):
                result = await self.wrapped_model.avectorize(texts)
            else:
                result = self.wrapped_model.vectorize(texts)
            
            if result is None:
                if isinstance(texts, str):
                    return [0.0] * self.vector_dimensions
                else:
                    return [[0.0] * self.vector_dimensions for _ in texts]
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"模型调用失败: {error_msg[:200]}")
            
            if "403" in error_msg or "429" in error_msg or "rate limit" in error_msg.lower() or "rpm limit" in error_msg.lower():
                logger.warning("检测到速率限制错误，返回空向量")
                if isinstance(texts, str):
                    return [0.0] * self.vector_dimensions
                else:
                    return [[0.0] * self.vector_dimensions for _ in texts]
            
            if isinstance(texts, str):
                return [0.0] * self.vector_dimensions
            else:
                return [[0.0] * self.vector_dimensions for _ in texts]

