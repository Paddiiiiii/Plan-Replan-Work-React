from typing import Dict
from plan import PlanModule
from work.agent import WorkAgent
from context_manager import ContextManager


class Orchestrator:
    def __init__(self):
        self.context_manager = ContextManager()
        self.plan_module = PlanModule(self.context_manager)
        self.work_agent = WorkAgent(self.context_manager)
    
    def generate_plan(self, user_task: str) -> Dict:
        plan = self.plan_module.generate_plan(user_task)
        return {
            "success": True,
            "plan": plan,
            "stage": "plan"
        }
    
    def execute_plan(self, plan: Dict) -> Dict:
        """执行计划（带自动重试）"""
        return self._execute_with_retry(plan)
    
    def execute_task(self, user_task: str) -> Dict:
        """执行完整任务（规划+执行）"""
        plan = self._plan_phase(user_task)
        return self._execute_with_retry(plan)
    
    def _execute_with_retry(self, plan: Dict) -> Dict:
        """
        执行计划并自动重试（公共逻辑）
        
        Args:
            plan: 执行计划
            
        Returns:
            执行结果字典
        """
        work_result = self.work_agent.execute_plan(plan)
        
        # 记录多任务执行信息
        if "sub_results" in work_result:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"多任务执行模式，子结果数: {len(work_result.get('sub_results', []))}")
            for i, sub_result in enumerate(work_result.get('sub_results', [])):
                logger.info(
                    f"子结果[{i+1}] 单位: {sub_result.get('unit', 'N/A')}, "
                    f"成功: {sub_result.get('success', False)}"
                )
        
        return {
            "success": work_result.get("success", False),
            "plan": plan,
            "result": work_result,
            "iterations": 1  # 不再重试，只执行一次
        }
    
    def _plan_phase(self, user_task: str) -> Dict:
        return self.plan_module.generate_plan(user_task)
    
    def _work_phase(self, plan: Dict) -> Dict:
        return self.work_agent.execute_plan(plan)
