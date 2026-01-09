from typing import Dict, List
from context_manager import ContextManager
from utils.llm_utils import call_llm
import logging
import re
import json

logger = logging.getLogger(__name__)

class PlanModule:
    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager

    def generate_plan(self, user_task: str) -> Dict:
        """
        生成计划：将用户问题拆分成子问题，调用KAG获取知识，然后传递给Work模块
        
        Args:
            user_task: 用户任务描述
            
        Returns:
            包含原始问题、子问题列表、KAG结果和合并答案的字典
        """
        logger.info(f"Plan阶段 - 开始处理用户任务: {user_task[:100]}...")
        
        # 1. 拆分问题：将用户问题拆分成2-3个适合KAG知识召回的子问题
        sub_questions = self._split_question(user_task)
        logger.info(f"Plan阶段 - 拆分成 {len(sub_questions)} 个子问题")
        for i, q in enumerate(sub_questions, 1):
            logger.info(f"Plan阶段 - 子问题{i}: {q}")
        
        # 2. 对每个子问题调用KAG获取知识
        kag_results = self._call_kag_for_questions(sub_questions)
        logger.info(f"Plan阶段 - KAG调用完成，获得 {len(kag_results)} 个结果")
        
        # 3. 合并所有KAG答案
        combined_kag_answers = self._combine_kag_answers(kag_results)
        logger.info(f"Plan阶段 - 合并后的KAG答案长度: {len(combined_kag_answers)}")
        
        # 4. 构建返回结构
        plan = {
            "original_query": user_task,
            "sub_questions": sub_questions,
            "kag_results": kag_results,
            "combined_kag_answers": combined_kag_answers
        }
        
        # 在终端显示Plan结果
        print("\n" + "=" * 80)
        print("📋 Plan阶段结果（问题拆分 + KAG知识召回）")
        print("=" * 80)
        print(f"原始问题: {user_task}")
        print(f"\n拆分后的子问题（共{len(sub_questions)}个）:")
        for i, q in enumerate(sub_questions, 1):
            print(f"  {i}. {q}")
        print(f"\nKAG知识召回结果（共{len(kag_results)}个）:")
        for i, result in enumerate(kag_results, 1):
            answer_preview = result.get("answer", "")[:100]
            if len(result.get("answer", "")) > 100:
                answer_preview += "..."
            print(f"  问题{i}: {result.get('question', '')[:50]}...")
            print(f"  答案{i}: {answer_preview}")
        print("=" * 80 + "\n")
        
        return plan
    
    def _split_question(self, user_task: str) -> List[str]:
        """
        将用户问题拆分成2-3个高度相关的子问题（适合KAG知识召回）
        
        Args:
            user_task: 用户原始问题
            
        Returns:
            子问题列表
        """
        prompt = self.context_manager.load_static_context("plan_prompt")
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"请将以下用户问题拆分成2-3个高度相关的子问题，这些子问题应该适合从知识库中进行知识召回。\n\n用户问题: {user_task}"}
        ]
        
        response = call_llm(messages)
        logger.info(f"Plan阶段 - 问题拆分LLM响应长度: {len(response)}")
        
        # 解析LLM响应，提取子问题
        sub_questions = self._parse_sub_questions(response, user_task)
        
        # 确保至少有1个问题，最多3个问题
        if len(sub_questions) == 0:
            # 如果无法拆分，返回原问题
            logger.warning("Plan阶段 - 无法拆分问题，使用原问题")
            return [user_task]
        elif len(sub_questions) > 3:
            # 如果超过3个，取前3个
            logger.warning(f"Plan阶段 - 拆分出{len(sub_questions)}个子问题，只取前3个")
            return sub_questions[:3]
        
        return sub_questions
    
    def _parse_sub_questions(self, response: str, user_task: str) -> List[str]:
        """
        解析LLM响应，提取子问题列表
        
        Args:
            response: LLM响应文本
            user_task: 原始用户问题（作为fallback）
            
        Returns:
            子问题列表
        """
        # 尝试从JSON中解析
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                if "sub_questions" in data and isinstance(data["sub_questions"], list):
                    return [q.strip() for q in data["sub_questions"] if q.strip()]
                if "questions" in data and isinstance(data["questions"], list):
                    return [q.strip() for q in data["questions"] if q.strip()]
        except Exception as e:
            logger.warning(f"Plan阶段 - 无法从JSON解析子问题: {e}")
        
        # 尝试从编号列表中解析（如 "1. 问题1\n2. 问题2"）
        lines = response.split('\n')
        questions = []
        for line in lines:
            line = line.strip()
            # 匹配 "1. 问题" 或 "问题1: 内容" 格式
            match = re.match(r'^\d+[\.、:]\s*(.+)', line)
            if match:
                q = match.group(1).strip()
                if q:
                    questions.append(q)
        
        if questions:
            return questions
        
        # 如果都无法解析，尝试按句子拆分（作为最后手段）
        sentences = re.split(r'[。！？\n]', response)
        questions = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        if questions:
            return questions[:3]  # 最多3个
        
        # 最后fallback：返回原问题
        return [user_task]
    
    def _call_kag_for_questions(self, questions: List[str]) -> List[Dict]:
        """
        对每个子问题调用KAG获取知识
        
        Args:
            questions: 子问题列表
            
        Returns:
            KAG结果列表，每个元素包含 question, answer, tasks, input_query
        """
        kag_results = []
        
        for question in questions:
            try:
                logger.info(f"Plan阶段 - 调用KAG查询: {question[:50]}...")
                
                # 调用KAG（不使用缓存，确保每个问题都获取最新结果）
                rag_context = self.context_manager.load_dynamic_context(
                    question,
                    top_k=5,
                    use_cache=False
                )
                
                # 获取KAG的完整结果
                kag_input_query = getattr(self.context_manager, "last_kag_input_query", question)
                kag_tasks = getattr(self.context_manager, "last_kag_tasks", [])
                kag_final_answer = getattr(self.context_manager, "last_kag_answer", "")
                
                # 清理KAG答案（移除reference标记等）
                clean_answer = self._clean_kag_answer(kag_final_answer)
                
                kag_results.append({
                    "question": question,
                    "answer": clean_answer,
                    "tasks": kag_tasks,
                    "input_query": kag_input_query,
                    "references": rag_context  # 保留原始引用信息
                })
                
                logger.info(f"Plan阶段 - KAG查询完成，答案长度: {len(clean_answer)}")
                
            except Exception as e:
                logger.error(f"Plan阶段 - KAG查询失败 (问题: {question[:50]}): {e}", exc_info=True)
                # 如果KAG调用失败，仍添加一个空结果，确保流程继续
                kag_results.append({
                    "question": question,
                    "answer": "",
                    "tasks": [],
                    "input_query": question,
                    "references": []
                })
        
        return kag_results
    
    def _clean_kag_answer(self, answer: str) -> str:
        """
        清理KAG答案，移除reference标记等格式字符
        
        Args:
            answer: 原始KAG答案
            
        Returns:
            清理后的答案
        """
        if not answer:
            return ""
        
        # 移除reference标记
        clean = re.sub(r'<reference[^>]*></reference>', '', answer)
        
        # 移除可能的"Final Answer:"前缀
        clean = re.sub(r'Final\s+Answer\s*:?\s*', '', clean, flags=re.IGNORECASE)
        
        # 清理多余空白
        clean = re.sub(r'\n\s*\n', '\n\n', clean)  # 多个换行合并为两个
        clean = clean.strip()
        
        return clean
    
    def _combine_kag_answers(self, kag_results: List[Dict]) -> str:
        """
        合并所有KAG答案为一个文本
        
        Args:
            kag_results: KAG结果列表
            
        Returns:
            合并后的答案文本
        """
        combined_parts = []
        
        for i, result in enumerate(kag_results, 1):
            question = result.get("question", "")
            answer = result.get("answer", "")
            
            if answer:
                combined_parts.append(f"子问题{i}: {question}\n答案{i}: {answer}")
            else:
                combined_parts.append(f"子问题{i}: {question}\n答案{i}: （无相关信息）")
        
        return "\n\n".join(combined_parts)
