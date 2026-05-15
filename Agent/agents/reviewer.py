"""
Reviewer（复盘智能体）

职责：完成关卡或全部学习后，生成学习报告和下一轮推荐。

报告生成流程：
1. 收集数据：完成情况、提问记录、用时、中断次数
2. LLM 分析提问记录，提取频繁提问的知识点（薄弱项）
3. 结合历史薄弱点，生成资料召回请求 → 发给 Librarian
4. LLM 汇总为结构化报告
5. 写入 MySQL 的 report 表

薄弱点追踪：统计最近 7 天的提问关键词频率和错题标记次数，加权排序得出 Top 3
"""
import json
import uuid
from collections import Counter
from typing import Dict, Any, List, Optional
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from agents.base import BaseAgent
from database.repository import (
    get_tasks_by_session, get_recent_qa_logs, insert_report,
    get_session_info, get_materials_by_ids,
)
from utils.file_storage import save_report_json
from config import WEAK_POINT_DAYS, WEAK_POINT_TOP_N
from agents.librarian import LibrarianAgent


class ReviewerAgent(BaseAgent):
    """复盘智能体：学习报告 + 薄弱点分析 + 推荐"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.librarian = LibrarianAgent()

    def review(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        time_range: str = "7d",
    ) -> Dict[str, Any]:
        """
        生成学习报告

        参数:
            user_id: 用户标识
            session_id: 要复盘的会话 ID（复盘整个会话）
            task_id: 要复盘的任务 ID（复盘单个关卡）
            time_range: 时间范围（用于薄弱点分析，如 "7d"）

        返回:
            ReviewReport 的字典形式
        """
        report_id = f"rpt_{uuid.uuid4().hex[:12]}"

        # Step 1: 收集数据
        completion_data = self._collect_completion_data(user_id, session_id, task_id)
        qa_logs = self._collect_qa_logs(user_id, session_id, task_id)

        # Step 2: 薄弱点分析
        weak_points = self._analyze_weak_points(qa_logs)

        # Step 3: 生成资料召回请求 → 发给 Librarian
        kp_names = [wp["knowledge_point"] for wp in weak_points]
        recalled = self.librarian.recall_materials(user_id, kp_names)
        recommended_ids = list(set(d.get("material_id", "") for d in recalled if d.get("material_id")))

        # Step 4: LLM 汇总为结构化报告
        next_suggestion = self._generate_suggestion(
            completion_data, weak_points, recalled
        )

        # Step 5: 组装报告
        report = {
            "report_id": report_id,
            "user_id": user_id,
            "session_id": session_id,
            "task_id": task_id,
            "tasks_completed": completion_data.get("completed", 0),
            "tasks_total": completion_data.get("total", 0),
            "total_minutes": completion_data.get("total_minutes", 0),
            "interruption_count": completion_data.get("interruptions", 0),
            "completion_rate": completion_data.get("completion_rate", 0.0),
            "weak_points": weak_points,
            "recommended_material_ids": recommended_ids,
            "next_tasks_suggestion": next_suggestion,
            "created_at": datetime.now().isoformat(),
        }

        # Step 6: 写入 MySQL
        insert_report({
            "id": report_id,
            "user_id": user_id,
            "session_id": session_id,
            "task_id": task_id,
            "completion": {
                "completed": report["tasks_completed"],
                "total": report["tasks_total"],
                "total_minutes": report["total_minutes"],
                "interruptions": report["interruption_count"],
                "completion_rate": report["completion_rate"],
            },
            "weak_points": weak_points,
            "recommended_material_ids": recommended_ids,
            "next_tasks_suggestion": next_suggestion,
        })

        # 写入本地文件
        save_report_json(user_id, report_id, report)

        return report

    def _collect_completion_data(
        self, user_id: str, session_id: Optional[str], task_id: Optional[str]
    ) -> Dict[str, Any]:
        """收集关卡完成数据"""
        if task_id:
            from database.repository import get_task
            t = get_task(task_id)
            if not t:
                return {"completed": 0, "total": 0, "total_minutes": 0, "interruptions": 0, "completion_rate": 0.0}
            completed = 1 if t.get("status") == "completed" else 0
            return {
                "completed": completed,
                "total": 1,
                "total_minutes": t.get("actual_minutes", 0),
                "interruptions": 0,
                "completion_rate": completed / 1,
            }

        if session_id:
            tasks = get_tasks_by_session(session_id)
            if not tasks:
                return {"completed": 0, "total": 0, "total_minutes": 0, "interruptions": 0, "completion_rate": 0.0}
            total = len(tasks)
            completed = sum(1 for t in tasks if t.get("status") == "completed")
            total_min = sum(t.get("actual_minutes", 0) for t in tasks)
            return {
                "completed": completed,
                "total": total,
                "total_minutes": total_min,
                "interruptions": 0,
                "completion_rate": completed / total if total > 0 else 0.0,
            }

        return {"completed": 0, "total": 0, "total_minutes": 0, "interruptions": 0, "completion_rate": 0.0}

    def _collect_qa_logs(
        self, user_id: str, session_id: Optional[str], task_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """收集相关提问记录"""
        logs = get_recent_qa_logs(user_id, days=WEAK_POINT_DAYS)

        # 按 session/task 过滤
        if task_id:
            logs = [l for l in logs if l.get("task_id") == task_id]
        elif session_id:
            # 获取 session 下的所有 task
            tasks = get_tasks_by_session(session_id)
            task_ids = {t.get("id") for t in tasks}
            logs = [l for l in logs if l.get("task_id") in task_ids]

        return logs

    def _analyze_weak_points(self, qa_logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        薄弱点追踪：统计最近 7 天的提问关键词频率和错题标记次数
        加权排序得出 Top 3
        """
        if not qa_logs:
            return []

        # 简单关键词频率统计
        keyword_counter = Counter()
        error_keywords = ["错题", "不会", "不懂", "错了", "做错", "不会做"]

        for log in qa_logs:
            question = log.get("question", "")
            answer_mode = log.get("answer_mode", "")

            # 错题模式加权更高
            weight = 1.0
            if answer_mode == "review":
                weight = 2.0
            elif answer_mode == "hint":
                weight = 1.5

            # 从问题中提取关键词（简化版：使用 LLM 分类结果）
            # 实际生产中可以调用 LLM 提取知识点关键词
            for ek in error_keywords:
                if ek in question:
                    weight *= 1.5
                    break

            # 使用 LLM 提取问题中的知识点
            # MVP 版本：直接用问题的前几个词作为标识
            # 更好的做法是调用轻量 LLM 提取知识点
            keyword_counter[question[:30]] += weight

        # 取 Top N
        top_items = keyword_counter.most_common(WEAK_POINT_TOP_N)

        # 使用 LLM 将 top 问题片段提炼为知识点名称
        weak_points = []
        for question_snippet, freq in top_items:
            # 简单处理：取问题本身作为薄弱点标识
            wp = {
                "knowledge_point": question_snippet,
                "frequency": int(freq),
                "weight": round(freq, 2),
            }
            weak_points.append(wp)

        if qa_logs and len(qa_logs) >= 3:
            # 有足够数据时用 LLM 提炼
            try:
                refined = self._refine_weak_points_with_llm(qa_logs)
                if refined:
                    # 合并频率数据
                    for r in refined:
                        r["frequency"] = weak_points[0]["frequency"] if weak_points else 1
                        r["weight"] = round(r.get("frequency", 1) * 1.5, 2)
                    weak_points = refined
            except Exception:
                pass

        return weak_points

    def _refine_weak_points_with_llm(self, qa_logs: List[Dict]) -> List[Dict]:
        """使用 LLM 从提问记录中提炼薄弱知识点"""
        questions_text = "\n".join([
            f"- [{l.get('answer_mode', '')}] {l.get('question', '')}"
            for l in qa_logs[:20]
        ])

        system_prompt = """你是学习分析专家。从学生的提问记录中提炼薄弱知识点。

输出严格 JSON 数组格式，最多 3 个：
```json
[
  {"knowledge_point": "知识点名称（如：二次函数单调性）", "frequency": 提问次数},
  ...
]
```"""

        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"提问记录：\n{questions_text}\n\n请提炼薄弱知识点："),
        ])

        try:
            text = response.content.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return []

    def _generate_suggestion(
        self,
        completion: Dict,
        weak_points: List[Dict],
        recalled_materials: List[Dict],
    ) -> str:
        """LLM 生成明日学习建议"""
        if not weak_points and not completion.get("total"):
            return "暂无足够数据生成建议，请先完成一些学习任务。"

        wp_text = ", ".join(wp["knowledge_point"] for wp in weak_points) if weak_points else "暂无"
        mat_text = "\n".join(
            f"- {m.get('filename', '')} ({m.get('subject', '')} > {m.get('knowledge_point', '')})"
            for m in recalled_materials[:5]
        ) if recalled_materials else "暂无推荐资料"

        system_prompt = """你是学习策略顾问。根据学习数据，生成明日学习建议。
要求：
1. 针对薄弱点给出具体的复习计划
2. 建议的复习顺序和时长
3. 推荐的学习方法
4. 语气积极向上，鼓励学生"""

        user_prompt = f"""今日学习数据：
- 完成关卡：{completion.get('completed', 0)}/{completion.get('total', 0)}
- 总时长：{completion.get('total_minutes', 0)} 分钟
- 完成率：{completion.get('completion_rate', 0):.0%}

薄弱知识点：{wp_text}

推荐复习资料：
{mat_text}

请生成明日学习建议（200 字以内）。"""

        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        return response.content.strip()
