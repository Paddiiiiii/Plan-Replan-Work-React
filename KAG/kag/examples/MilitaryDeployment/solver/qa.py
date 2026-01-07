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
import asyncio
import logging
from kag.common.registry import import_modules_from_path
from kag.interface import SolverPipelineABC
from kag.common.conf import KAG_CONFIG

logger = logging.getLogger(__name__)


def query(question: str):
    """使用KAG推理引擎回答问题"""
    solver = SolverPipelineABC.from_config(
        KAG_CONFIG.all_config["kag_solver_pipeline"]
    )
    
    # KAG的pipeline使用异步方法
    result = asyncio.run(solver.ainvoke(question))
    
    logger.info(f"\n问题: {question}")
    logger.info(f"答案: {result}")
    
    # 标准化返回格式
    if isinstance(result, str):
        return {
            "answer": result,
            "references": []
        }
    elif isinstance(result, dict):
        return result
    else:
        return {
            "answer": str(result),
            "references": []
        }


if __name__ == "__main__":
    import_modules_from_path(".")
    import sys
    
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "轻步兵应该部署在什么位置？"
    
    query(question)

