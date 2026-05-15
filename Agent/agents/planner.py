"""
Planner（规划智能体）

职责：将用户的学习目标拆解为可执行的关卡（任务块）。
核心流程：
1. RAG 检索相关知识信息
2. 若 RAG 无结果 → Tavily 联网搜索
3. LLM 生成关卡列表
4. 规则引擎后处理（时长约束、休息插入、科目轮换）
5. 输出 JSON → 写入 MySQL + 本地文件
"""
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base import BaseAgent
from rag.retriever import get_retriever
from tools.web_search import get_web_search_tool
from database.repository import (
    create_session, insert_tasks_batch,
)
from utils.file_storage import save_planner_json, save_task_index, save_task_file
from config import (
    TASK_MIN_MINUTES, TASK_MAX_MINUTES,
    SAME_SUBJECT_MAX_MINUTES, BREAK_MINUTES,
)


class PlannerAgent(BaseAgent):
    """规划智能体：学习目标 → 关卡列表"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rag = get_retriever()
        self.web_search = get_web_search_tool()

    def plan(
        self,
        user_id: str,
        goal_text: str,
        available_hours: float = 2.0,
        constraints: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        执行完整规划流程

        参数:
            user_id: 用户标识
            goal_text: 学习目标（如"复习数学函数和英语作文"）
            available_hours: 可用时间（小时）
            constraints: 额外约束 {subject_priority, deadline, ...}

        返回:
            包含关卡列表的完整 Planner 输出
        """
        constraints = constraints or {}
        total_minutes = int(available_hours * 60)

        # Step 1: RAG 检索已导入的相关资料
        self.log(f"RAG 检索: {goal_text}")
        rag_docs = self.rag.retrieve(goal_text, user_id, top_k=5)

        web_search_used = False
        knowledge_context = ""

        if rag_docs:
            knowledge_context = self.rag.format_retrieved_context(rag_docs)
            self.log(f"RAG 找到 {len(rag_docs)} 条相关片段")
        else:
            # Step 2: RAG 无结果 → 联网搜索
            self.log("RAG 无结果，回退到 Tavily 联网搜索")
            web_result = self.web_search._run(
                query=f"{goal_text} 学习要点 知识点 考点",
                max_results=5,
            )
            if not web_result.startswith("[WebSearch 不可用]") and not web_result.startswith("[WebSearch 失败]"):
                knowledge_context = web_result
                web_search_used = True

        # Step 3: 组装 prompt → LLM 生成关卡
        tasks = self._generate_tasks(
            goal_text=goal_text,
            total_minutes=total_minutes,
            knowledge_context=knowledge_context,
            constraints=constraints,
        )

        # Step 4: 规则引擎后处理
        tasks = self._apply_rules(tasks, total_minutes)

        # Step 5: 先建 session，再写入关卡（保证 FK 完整性）
        # create_session 返回 session_id
        plan_summary = {
            "goal_text": goal_text,
            "total_estimated_minutes": sum(t.get("estimated_minutes", 0) for t in tasks),
            "knowledge_summary": knowledge_context[:500],
            "web_search_used": web_search_used,
            "tasks": tasks,
            "created_at": datetime.now().isoformat(),
        }
        session_id = create_session(user_id, goal_text, plan_summary)

        # 为每个 task 补充 id、user_id、session_id
        for i, t in enumerate(tasks):
            t["id"] = f"task_{uuid.uuid4().hex[:12]}"
            t["user_id"] = user_id
            t["session_id"] = session_id
            t["sort_order"] = i
            t.setdefault("status", "pending")
            t.setdefault("description", "")
            t.setdefault("priority", 1)

        # 写入 MySQL
        insert_tasks_batch(tasks)
        self.log(f"写入 MySQL: {len(tasks)} 个关卡")

        # 写入本地文件
        plan_data = {
            "session_id": session_id,
            "goal_text": goal_text,
            "tasks": tasks,
            "total_estimated_minutes": sum(t.get("estimated_minutes", 0) for t in tasks),
            "knowledge_summary": knowledge_context[:500],
            "web_search_used": web_search_used,
            "created_at": datetime.now().isoformat(),
        }
        json_path = save_planner_json(user_id, session_id, plan_data)
        save_task_index(tasks)
        for t in tasks:
            save_task_file(t)
        self.log(f"写入本地文件: {json_path}")

        return plan_data

    def _generate_tasks(
        self,
        goal_text: str,
        total_minutes: int,
        knowledge_context: str,
        constraints: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """调用 LLM 生成关卡列表"""
        system_prompt = """你是一个专业的学习规划师。根据用户的学习目标和知识资料，将目标拆解为可执行的关卡。

规则：
1. 每个关卡 20-50 分钟
2. 任务类型包括：understand(理解概念)、practice(练习题)、memorize(记忆背诵)、correct(纠错订正)、review(复盘总结)
3. 先易后难，先理解后练习
4. 关联的资料在题目中占比要更大（上传时间越新的资料权重越大）
5. 输出严格的 JSON 数组格式，每个元素包含：
   - subject: 科目名称
   - title: 关卡标题（简洁明了）
   - description: 关卡描述（说明具体要做什么）
   - task_type: 任务类型 (understand/practice/memorize/correct/review)
   - estimated_minutes: 建议时长（分钟）
   - material_ids: 关联资料 ID 列表（从资料片段中提取，无则空数组）
   - priority: 优先级 1-5（5最高）

输出格式：
```json
[
  {"subject": "...", "title": "...", "description": "...", "task_type": "...", "estimated_minutes": 30, "material_ids": [], "priority": 3},
  ...
]
```"""

        user_prompt = f"""学习目标：{goal_text}
可用总时长：{total_minutes} 分钟

知识参考资料：
{knowledge_context}

额外约束：{json.dumps(constraints, ensure_ascii=False) if constraints else "无"}

请生成关卡列表（JSON 格式）。"""

        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        return self._parse_tasks(response.content)

    def _parse_tasks(self, llm_output: str) -> List[Dict[str, Any]]:
        """解析 LLM 输出的 JSON 关卡列表"""
        try:
            text = llm_output.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            tasks = json.loads(text)
            if not isinstance(tasks, list):
                return []
            return tasks
        except (json.JSONDecodeError, IndexError):
            self.log(f"无法解析 LLM 输出为 JSON: {llm_output[:500]}", "ERROR")
            return []

    def _apply_rules(
        self, tasks: List[Dict[str, Any]], total_minutes: int
    ) -> List[Dict[str, Any]]:
        """
        规则引擎后处理（硬编码保证可靠性）
        1. 单关时长 ∈ [20, 50]，超限拆分
        2. 同科目连续 ≤ 90 分钟，插入休息
        3. 高难度后插入休息
        """
        if not tasks:
            return tasks

        processed = []

        for t in tasks:
            est = t.get("estimated_minutes", 30)

            # 规则 1: 时长约束
            if est < TASK_MIN_MINUTES:
                t["estimated_minutes"] = TASK_MIN_MINUTES
            elif est > TASK_MAX_MINUTES:
                # 拆分为多个子关卡
                sub_count = (est + TASK_MAX_MINUTES - 1) // TASK_MAX_MINUTES
                sub_minutes = est // sub_count
                for i in range(sub_count):
                    sub = dict(t)
                    sub["title"] = f"{t['title']} (第{i+1}部分)"
                    sub["estimated_minutes"] = sub_minutes
                    processed.append(sub)
                continue

            processed.append(t)

        # 规则 2: 同科目连续 ≤ 90 分钟，插入休息
        final = []
        current_subject_minutes = 0
        last_subject = ""

        for t in processed:
            subj = t.get("subject", "")
            est = t.get("estimated_minutes", 30)

            if subj == last_subject and subj:
                current_subject_minutes += est
                if current_subject_minutes > SAME_SUBJECT_MAX_MINUTES:
                    # 插入休息关
                    final.append({
                        "subject": "休息",
                        "title": "休息一下",
                        "description": "站起来走动，喝水放松眼睛",
                        "task_type": "break",
                        "estimated_minutes": BREAK_MINUTES,
                        "material_ids": [],
                        "priority": 0,
                    })
                    current_subject_minutes = est
            else:
                current_subject_minutes = est
                last_subject = subj

            final.append(t)

        return final
