# -*- coding: utf-8 -*-
"""
军事部署领域Prompt模块
注册自定义的军事部署领域prompt
"""
# 使用相对导入，确保在当前目录下能正确导入
try:
    from .military_deployment_ner import MilitaryDeploymentNERPrompt
    from .military_deployment_relation import MilitaryDeploymentRelationPrompt
    from .military_deployment_std import MilitaryDeploymentSTDPrompt
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    prompt_dir = Path(__file__).parent
    if str(prompt_dir) not in sys.path:
        sys.path.insert(0, str(prompt_dir))
    from military_deployment_ner import MilitaryDeploymentNERPrompt
    from military_deployment_relation import MilitaryDeploymentRelationPrompt
    from military_deployment_std import MilitaryDeploymentSTDPrompt

__all__ = [
    "MilitaryDeploymentNERPrompt",
    "MilitaryDeploymentRelationPrompt",
    "MilitaryDeploymentSTDPrompt",
]

