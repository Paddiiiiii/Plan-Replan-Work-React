# Copyright 2023 OpenSPG Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

from typing import Union, Iterable
from openai import OpenAI, AsyncOpenAI, AzureOpenAI, AsyncAzureOpenAI
from kag.interface import VectorizeModelABC, EmbeddingVector
from typing import Callable
import logging
import time
from collections import deque
from threading import Lock

logger = logging.getLogger(__name__)

# 最大token数限制（保守估计，中文1 token ≈ 1-2字符，设置400字符确保不超过512 tokens）
MAX_TOKENS = 512
MAX_CHARS = 400  # 保守估计，确保不超过512 tokens


@VectorizeModelABC.register("openai")
class OpenAIVectorizeModel(VectorizeModelABC):
    """
    A class that extends the VectorizeModelABC base class.
    It invokes OpenAI or OpenAI-compatible embedding services to convert texts into embedding vectors.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str = None,
        base_url: str = "",
        vector_dimensions: int = None,
        timeout: float = None,
        max_rate: float = 30,  # 默认30请求/秒，避免超限
        time_period: float = 1,
        max_tokens: int = MAX_TOKENS,
        max_chars: int = MAX_CHARS,
        **kwargs,
    ):
        """
        Initializes the OpenAIVectorizeModel instance.

        Args:
            model (str, optional): The model to use for embedding. Defaults to "text-embedding-3-small".
            api_key (str, optional): The API key for accessing the OpenAI service. Defaults to "".
            base_url (str, optional): The base URL for the OpenAI service. Defaults to "".
            vector_dimensions (int, optional): The number of dimensions for the embedding vectors. Defaults to None.
            max_tokens (int, optional): Maximum tokens per text. Defaults to 512.
            max_chars (int, optional): Maximum characters per text (conservative estimate). Defaults to 400.
            max_rate (float, optional): Maximum requests per second. Defaults to 30 to avoid rate limiting.
            time_period (float, optional): Time window in seconds. Defaults to 1.
        """
        api_key = api_key if api_key else "abc123"
        name = self.generate_key(base_url, model, api_key)
        super().__init__(name, vector_dimensions, max_rate, time_period)
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.max_chars = max_chars
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=self.timeout)
        self.aclient = AsyncOpenAI(
            api_key=api_key, base_url=base_url, timeout=self.timeout
        )
        
        # 速率限制相关
        self.max_rate = max_rate
        self.time_period = time_period
        self.request_times = deque()  # 记录请求时间
        self.rate_limit_lock = Lock()

    @classmethod
    def generate_key(cls, base_url, model, api_key, *args, **kwargs) -> str:
        return f"{cls}_{base_url}_{model}_{api_key}"

    def _rate_limit(self):
        """实现速率限制"""
        with self.rate_limit_lock:
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
    
    def _truncate_text(self, text: str) -> str:
        """
        Truncate text to ensure it doesn't exceed max_chars limit.
        
        Args:
            text: The text to truncate.
            
        Returns:
            Truncated text.
        """
        if len(text) <= self.max_chars:
            return text
        # Truncate and add ellipsis
        truncated = text[:self.max_chars - 3] + "..."
        logger.warning(f"Text truncated from {len(text)} to {len(truncated)} characters to meet token limit")
        return truncated

    def vectorize(
        self, texts: Union[str, Iterable[str]]
    ) -> Union[EmbeddingVector, Iterable[EmbeddingVector]]:
        """
        Vectorizes a text string into an embedding vector or multiple text strings into multiple embedding vectors.

        Args:
            texts (Union[str, Iterable[str]]): The text or texts to vectorize.

        Returns:
            Union[EmbeddingVector, Iterable[EmbeddingVector]]: The embedding vector(s) of the text(s).
        """
        # 应用速率限制
        self._rate_limit()

        try:
            # Handle empty strings in the input
            if isinstance(texts, list):
                # Create a map of original indices to track empty strings
                empty_indices = {i: text.strip() == "" for i, text in enumerate(texts)}
                # Filter out empty strings and truncate texts
                filtered_texts = [
                    self._truncate_text(text) if not empty_indices[i] else ""
                    for i, text in enumerate(texts)
                ]
                # Remove empty strings for the API call
                filtered_texts = [text for text in filtered_texts if text.strip() != ""]

                if not filtered_texts:
                    return [[] for _ in texts]  # Return empty vectors for all inputs

                results = self.client.embeddings.create(
                    input=filtered_texts, model=self.model
                )

                # Reconstruct the results with empty lists for empty strings
                embeddings = [item.embedding for item in results.data]
                full_results = []
                embedding_idx = 0

                for i in range(len(texts)):
                    if empty_indices[i]:
                        full_results.append([])  # Empty embedding for empty string
                    else:
                        full_results.append(embeddings[embedding_idx])
                        embedding_idx += 1

                return full_results
            elif isinstance(texts, str) and not texts.strip():
                return []  # Return empty vector for empty string
            else:
                truncated_text = self._truncate_text(texts)
                results = self.client.embeddings.create(input=truncated_text, model=self.model)
                results = [item.embedding for item in results.data]
                assert len(results) == 1
                return results[0]
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error: {e}")
            logger.error(f"input: {texts}")
            logger.error(f"model: {self.model}")
            logger.error(f"timeout: {self.timeout}")
            
            # 如果是速率限制错误，返回空向量避免后续错误
            if "403" in error_msg or "429" in error_msg or "rate limit" in error_msg.lower() or "rpm limit" in error_msg.lower():
                logger.warning("检测到速率限制错误，返回空向量")
                if isinstance(texts, str):
                    return [0.0] * (self.vector_dimensions or 1024)
                else:
                    return [[0.0] * (self.vector_dimensions or 1024) for _ in texts]
            
            # 其他错误抛出异常
            raise

    async def avectorize(
        self, texts: Union[str, Iterable[str]]
    ) -> Union[EmbeddingVector, Iterable[EmbeddingVector]]:
        """
        Vectorizes a text string into an embedding vector or multiple text strings into multiple embedding vectors.

        Args:
            texts (Union[str, Iterable[str]]): The text or texts to vectorize.

        Returns:
            Union[EmbeddingVector, Iterable[EmbeddingVector]]: The embedding vector(s) of the text(s).
        """
        # 应用速率限制
        self._rate_limit()
        
        async with self.limiter:
            # Truncate texts to ensure they don't exceed token limit
            if isinstance(texts, list):
                texts = [
                    self._truncate_text(text) if text.strip() != "" else "none"
                    for text in texts
                ]
            elif isinstance(texts, str):
                texts = self._truncate_text(texts) if texts.strip() != "" else "none"
            try:
                results = await self.aclient.embeddings.create(
                    input=texts, model=self.model
                )
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error: {e}")
                logger.error(f"input: {texts}")
                logger.error(f"model: {self.model}")
                logger.error(f"timeout: {self.timeout}")
                
                # 如果是速率限制错误，返回空向量
                if "403" in error_msg or "429" in error_msg or "rate limit" in error_msg.lower() or "rpm limit" in error_msg.lower():
                    logger.warning("检测到速率限制错误，返回空向量")
                    if isinstance(texts, str):
                        return [0.0] * (self.vector_dimensions or 1024)
                    else:
                        return [[0.0] * (self.vector_dimensions or 1024) for _ in texts]
                
                raise
        results = [item.embedding for item in results.data]
        if isinstance(texts, str):
            assert len(results) == 1
            return results[0]
        else:
            assert len(results) == len(texts)
            return results


@VectorizeModelABC.register("azure_openai")
class AzureOpenAIVectorizeModel(VectorizeModelABC):
    """A class that extends the VectorizeModelABC base class.
    It invokes Azure OpenAI or Azure OpenAI-compatible embedding services to convert texts into embedding vectors.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "text-embedding-ada-002",
        api_version: str = "2024-12-01-preview",
        vector_dimensions: int = None,
        timeout: float = None,
        azure_deployment: str = None,
        azure_ad_token: str = None,
        azure_ad_token_provider: Callable = None,
        max_rate: float = 1000,
        time_period: float = 1,
    ):
        """
        Initializes the AzureOpenAIVectorizeModel instance.

        Args:
            model (str, optional): The model to use for embedding. Defaults to "text-embedding-3-small".
            api_key (str, optional): The API key for accessing the Azure OpenAI service. Defaults to "".
            api_version (str): The API version for the Azure OpenAI API (eg. "2024-12-01-preview, 2024-10-01-preview,2024-05-01-preview").
            base_url (str, optional): The base URL for the Azure OpenAI service. Defaults to "".
            vector_dimensions (int, optional): The number of dimensions for the embedding vectors. Defaults to None.
            azure_ad_token: Your Azure Active Directory token, https://www.microsoft.com/en-us/security/business/identity-access/microsoft-entra-id
            azure_ad_token_provider: A function that returns an Azure Active Directory token, will be invoked on every request.
            azure_deployment: A model deployment, if given sets the base client URL to include `/deployments/{azure_deployment}`.
                Note: this means you won't be able to use non-deployment endpoints. Not supported with Assistants APIs.
        """
        name = self.generate_key(api_key, base_url, model)
        super().__init__(name, vector_dimensions, max_rate, time_period)
        self.model = model
        self.timeout = timeout
        self.client = AzureOpenAI(
            api_key=api_key,
            base_url=base_url,
            azure_deployment=azure_deployment,
            model=model,
            api_version=api_version,
            azure_ad_token=azure_ad_token,
            azure_ad_token_provider=azure_ad_token_provider,
            timeout=self.timeout,
        )
        self.aclient = AsyncAzureOpenAI(
            api_key=api_key,
            base_url=base_url,
            azure_deployment=azure_deployment,
            model=model,
            api_version=api_version,
            azure_ad_token=azure_ad_token,
            azure_ad_token_provider=azure_ad_token_provider,
            timeout=self.timeout,
        )

    @classmethod
    def generate_key(cls, base_url, api_key, model, *args, **kwargs) -> str:
        return f"{cls}_{base_url}_{api_key}_{model}"

    def vectorize(
        self, texts: Union[str, Iterable[str]]
    ) -> Union[EmbeddingVector, Iterable[EmbeddingVector]]:
        """
        Vectorizes a text string into an embedding vector or multiple text strings into multiple embedding vectors.

        Args:
            texts (Union[str, Iterable[str]]): The text or texts to vectorize.

        Returns:
            Union[EmbeddingVector, Iterable[EmbeddingVector]]: The embedding vector(s) of the text(s).
        """
        results = self.client.embeddings.create(input=texts, model=self.model)
        results = [item.embedding for item in results.data]
        if isinstance(texts, str):
            assert len(results) == 1
            return results[0]
        else:
            assert len(results) == len(texts)
            return results

    async def avectorize(
        self, texts: Union[str, Iterable[str]]
    ) -> Union[EmbeddingVector, Iterable[EmbeddingVector]]:
        """
        Vectorizes a text string into an embedding vector or multiple text strings into multiple embedding vectors.

        Args:
            texts (Union[str, Iterable[str]]): The text or texts to vectorize.

        Returns:
            Union[EmbeddingVector, Iterable[EmbeddingVector]]: The embedding vector(s) of the text(s).
        """
        async with self.limiter:
            results = await self.aclient.embeddings.create(
                input=texts, model=self.model
            )
        results = [item.embedding for item in results.data]
        if isinstance(texts, str):
            assert len(results) == 1
            return results[0]
        else:
            assert len(results) == len(texts)
            return results


if __name__ == "__main__":
    vectorize_model = OpenAIVectorizeModel(
        model="bge-m3", base_url="http://localhost:11434/v1"
    )
    texts = ["Hello, world!", "Hello, world!", "Hello, world!"]
    embeddings = vectorize_model.vectorize("texts")
    print(embeddings)
