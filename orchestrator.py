from typing import Dict
from plan import PlanModule
from replan import ReplanModule
from work.agent import WorkAgent
from context_manager import ContextManager


class Orchestrator:
    def __init__(self):
        self.context_manager = ContextManager()
        self.plan_module = PlanModule(self.context_manager)
        self.replan_module = ReplanModule(self.context_manager)
        self.work_agent = WorkAgent(self.context_manager)
    
    def generate_plan(self, user_task: str) -> Dict:
        plan = self.plan_module.generate_plan(user_task)
        return {
            "success": True,
            "plan": plan,
            "stage": "plan"
        }
    
    def replan_with_feedback(self, original_plan: Dict, feedback: str) -> Dict:
        available_tools = list(self.work_agent.tools.keys())
        new_plan = self.replan_module.replan_with_feedback(original_plan, feedback, available_tools)
        return {
            "success": True,
            "plan": new_plan,
            "stage": "replan"
        }
    
    def execute_plan(self, plan: Dict) -> Dict:
        work_result = self.work_agent.execute_plan(plan)
        
        if "sub_results" in work_result:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"多任务执行模式，子结果数: {len(work_result.get('sub_results', []))}")
            for i, sub_result in enumerate(work_result.get('sub_results', [])):
                logger.info(f"子结果[{i+1}] 单位: {sub_result.get('unit', 'N/A')}, 成功: {sub_result.get('success', False)}")
        
        max_iterations = 3
        iteration = 0
        
        while not work_result.get("success", False) and iteration < max_iterations:
            if self.replan_module.should_replan(work_result):
                available_tools = list(self.work_agent.tools.keys())
                plan = self.replan_module.replan(plan, work_result, available_tools)
                work_result = self.work_agent.execute_plan(plan)
            iteration += 1
        
        return {
            "success": work_result.get("success", False),
            "plan": plan,
            "result": work_result,
            "iterations": iteration + 1
        }
    
    def execute_task(self, user_task: str) -> Dict:
        plan = self._plan_phase(user_task)
        work_result = self._work_phase(plan)
        
        if "sub_results" in work_result:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"多任务执行模式，子结果数: {len(work_result.get('sub_results', []))}")
            for i, sub_result in enumerate(work_result.get('sub_results', [])):
                logger.info(f"子结果[{i+1}] 单位: {sub_result.get('unit', 'N/A')}, 成功: {sub_result.get('success', False)}")
        
        max_iterations = 3
        iteration = 0
        
        while not work_result.get("success", False) and iteration < max_iterations:
            if self.replan_module.should_replan(work_result):
                plan = self._replan_phase(plan, work_result)
                work_result = self._work_phase(plan)
            iteration += 1
        
        return {
            "success": work_result.get("success", False),
            "plan": plan,
            "result": work_result,
            "iterations": iteration + 1
        }
    
    def _plan_phase(self, user_task: str) -> Dict:
        return self.plan_module.generate_plan(user_task)
    
    def _work_phase(self, plan: Dict) -> Dict:
        return self.work_agent.execute_plan(plan)
    
    def _replan_phase(self, original_plan: Dict, work_result: Dict) -> Dict:
        available_tools = list(self.work_agent.tools.keys())
        return self.replan_module.replan(original_plan, work_result, available_tools)
