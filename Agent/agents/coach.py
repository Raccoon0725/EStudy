"""
Coach（答疑智能体）

职责：RAG 增强答疑，三种应答模式：
- 提示模式：只给解题思路，不给完整答案（作业/练习题）
- 讲解模式：分步骤详细解释知识点和过程（概念理解）
- 复盘模式：总结同类题型的通用方法和易错点（错题回顾）

核心流程：
1. 接收问题 + 关卡上下文
2. RAG 检索相关资料片段
3. 根据 AnswerMode 组装不同的系统指令
4. LLM 生成回答，标注来源
5. 记录到 MySQL 提问日志
"""
import uuid
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base import BaseAgent
from rag.retriever import get_retriever
from database.repository import insert_qa_log, get_task
from tools.web_search import get_web_search_tool


class CoachAgent(BaseAgent):
    """答疑智能体：RAG 增强 + 三种应答模式"""

    ANSWER_MODE_PROMPTS = {
        "hint": """【提示模式】
你是一个启发式导师。学生正在做作业/练习题，你的任务是引导他们自己找到答案。

要求：
1. 绝对不能给出完整答案或最终结果
2. 只提供解题思路、关键公式、思考方向
3. 用提问的方式引导学生（如"你注意到题目中的...条件了吗？"）
4. 如果学生追问，可以进一步缩小提示范围
5. 引用资料时标注来源文件名""",

        "explain": """【讲解模式】
你是一个耐心的知识讲解员。学生想要理解某个概念或知识点。

要求：
1. 分步骤详细解释，每步一个要点
2. 用通俗易懂的语言，配合举例说明
3. 可以给出完整答案，但要确保学生理解推导过程
4. 对关键概念给出定义，对公式给出含义解释
5. 引用资料时标注来源文件名和位置""",

        "review": """【复盘模式】
你是一个学习策略分析师。学生正在回顾错题，需要总结方法论。

要求：
1. 总结同类题型的通用解题方法（不限于本题）
2. 指出常见易错点和陷阱
3. 给出知识图谱：这个知识点关联哪些其他概念
4. 建议针对性的练习方向
5. 引用资料时标注来源文件名""",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rag = get_retriever()
        self.web_search = get_web_search_tool()

    def answer(
        self,
        user_id: str,
        question: str,
        answer_mode: str = "auto",
        active_task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行 RAG 增强答疑

        参数:
            user_id: 用户标识
            question: 用户提问
            answer_mode: 应答模式 (hint/explain/review/auto)
            active_task_id: 当前活跃关卡 ID

        返回:
            CoachOutput 的字典形式
        """
        # Step 1: 获取当前关卡上下文
        task_context = ""
        task_info = None
        if active_task_id:
            task_info = get_task(active_task_id)
            if task_info:
                task_context = (
                    f"当前关卡：{task_info.get('subject', '')} - {task_info.get('title', '')}\n"
                    f"关卡类型：{task_info.get('task_type', '')}\n"
                    f"关卡描述：{task_info.get('description', '')}"
                )
            else:
                self.log(f"关卡不存在: {active_task_id}，忽略关卡上下文", "WARN")
                active_task_id = None  # 防止 FK 约束失败

        # Step 2: RAG 检索相关资料，无结果时回退到联网搜索
        self.log(f"RAG 检索问题: {question[:100]}")
        rag_docs = self.rag.retrieve(question, user_id, top_k=5)

        web_search_used = False
        if rag_docs:
            knowledge_context = self.rag.format_retrieved_context(rag_docs)
            self.log(f"RAG 找到 {len(rag_docs)} 条相关片段")
        else:
            self.log("RAG 无结果，回退到 Tavily 联网搜索")
            knowledge_context = self.web_search._run(
                query=f"{question} 知识点 解题方法",
                max_results=5,
            )
            if not knowledge_context.startswith("[WebSearch 不可用]") and not knowledge_context.startswith("[WebSearch 失败]"):
                web_search_used = True
                self.log("联网搜索成功")
            else:
                self.log(f"联网搜索不可用: {knowledge_context}", "WARN")

        # 提取来源信息供返回
        sources = [
            {
                "filename": d["filename"],
                "chunk_index": d["chunk_index"],
                "similarity": d["similarity"],
                "preview": d["content"][:150],
            }
            for d in rag_docs
        ]

        # Step 3: 自动判定应答模式
        if answer_mode == "auto":
            answer_mode = self._auto_detect_mode(question, task_info)

        self.log(f"应答模式: {answer_mode}")

        # Step 4: 组装 prompt
        mode_prompt = self.ANSWER_MODE_PROMPTS.get(
            answer_mode, self.ANSWER_MODE_PROMPTS["explain"]
        )

        system_prompt = f"""{mode_prompt}

引用格式要求：当答案中使用了资料片段中的内容时，必须在对应位置标注 [来源: 文件名]。

知识库检索结果：
{knowledge_context}

{task_context}"""

        user_prompt = f"学生提问：{question}"

        # Step 5: LLM 生成回答
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        answer_text = response.content

        # Step 6: 置信度评估
        confidence = self._assess_confidence(rag_docs)

        # Step 7: 写入 MySQL 提问日志
        log_id = insert_qa_log(
            user_id=user_id,
            question=question,
            answer=answer_text,
            answer_mode=answer_mode,
            source_docs=sources,
            task_id=active_task_id,
            confidence=confidence,
        )

        return {
            "answer": answer_text,
            "answer_mode": answer_mode,
            "sources": sources,
            "confidence": confidence,
            "qa_log_id": log_id,
            "web_search_used": web_search_used,
        }

    def _auto_detect_mode(
        self, question: str, task_info: Optional[Dict[str, Any]]
    ) -> str:
        """根据问题措辞和关卡类型自动判定应答模式"""
        hint_keywords = ["提示", "给个思路", "怎么做", "不会做", "这题", "解答题", "作业"]
        review_keywords = ["错题", "为什么错了", "总结", "归纳", "回顾", "老是错", "容易错"]
        explain_keywords = ["是什么", "为什么", "解释", "理解", "概念", "定义", "原理", "讲讲"]

        q_lower = question.lower()

        hint_score = sum(1 for k in hint_keywords if k in q_lower)
        review_score = sum(1 for k in review_keywords if k in q_lower)
        explain_score = sum(1 for k in explain_keywords if k in q_lower)

        # 关卡类型加权
        if task_info:
            task_type = task_info.get("task_type", "")
            if task_type == "practice":
                hint_score += 2
            elif task_type == "correct":
                review_score += 2
            elif task_type == "review":
                review_score += 2

        if review_score >= hint_score and review_score >= explain_score:
            return "review"
        elif hint_score >= explain_score:
            return "hint"
        else:
            return "explain"

    def _assess_confidence(self, rag_docs: list) -> str:
        """根据 RAG 检索结果评估置信度"""
        if not rag_docs:
            return "low"
        avg_sim = sum(d.get("similarity", 0) for d in rag_docs) / len(rag_docs)
        if avg_sim >= 0.8:
            return "high"
        elif avg_sim >= 0.65:
            return "medium"
        return "low"
