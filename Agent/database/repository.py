"""
数据库 CRUD 操作层
提供所有表的高层读写接口
"""
import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import text
from database.connection import get_session


# ============================================================
# 用户
# ============================================================
def ensure_user(user_id: str, username: str = "default") -> str:
    """确保用户存在"""
    with get_session() as sess:
        row = sess.execute(text("SELECT id FROM users WHERE id = :uid"), {"uid": user_id}).fetchone()
        if not row:
            sess.execute(
                text("INSERT INTO users (id, username, password_hash) VALUES (:uid, :un, :ph)"),
                {"uid": user_id, "un": username, "ph": ""}
            )
            sess.commit()
    return user_id


# ============================================================
# Session
# ============================================================
def create_session(user_id: str, goal_text: str, planner_json: dict) -> str:
    """创建学习会话"""
    ensure_user(user_id)
    sid = f"sess_{uuid.uuid4().hex[:12]}"
    with get_session() as sess:
        sess.execute(
            text("""INSERT INTO sessions (id, user_id, goal_text, date, planner_json)
                    VALUES (:id, :uid, :goal, CURDATE(), :pj)"""),
            {"id": sid, "uid": user_id, "goal": goal_text, "pj": json.dumps(planner_json, ensure_ascii=False)}
        )
        sess.commit()
    return sid


def get_session_info(session_id: str) -> Optional[dict]:
    """获取会话信息"""
    with get_session() as sess:
        row = sess.execute(
            text("SELECT * FROM sessions WHERE id = :sid"),
            {"sid": session_id}
        ).fetchone()
        if row:
            return dict(row._mapping)
    return None


# ============================================================
# Tasks
# ============================================================
def insert_task(task_data: dict) -> str:
    """插入单个关卡"""
    ensure_user(task_data["user_id"])
    tid = task_data.get("id") or f"task_{uuid.uuid4().hex[:12]}"
    with get_session() as sess:
        sess.execute(
            text("""INSERT INTO tasks (id, user_id, session_id, parent_id, subject, title, description,
                    task_type, estimated_minutes, status, priority, sort_order, material_ids)
                    VALUES (:id, :uid, :sid, :pid, :subj, :title, :desc,
                    :tt, :est, :st, :pri, :so, :mids)"""),
            {
                "id": tid,
                "uid": task_data["user_id"],
                "sid": task_data.get("session_id"),
                "pid": task_data.get("parent_id"),
                "subj": task_data.get("subject", ""),
                "title": task_data["title"],
                "desc": task_data.get("description", ""),
                "tt": task_data.get("task_type", "understand"),
                "est": task_data.get("estimated_minutes", 30),
                "st": task_data.get("status", "pending"),
                "pri": task_data.get("priority", 1),
                "so": task_data.get("sort_order", 0),
                "mids": json.dumps(task_data.get("material_ids", []), ensure_ascii=False),
            }
        )
        sess.commit()
    return tid


def insert_tasks_batch(tasks: List[dict]) -> List[str]:
    """批量插入关卡"""
    ids = []
    for t in tasks:
        ids.append(insert_task(t))
    return ids


def update_task_status(task_id: str, status: str, actual_minutes: int = 0):
    """更新关卡状态"""
    with get_session() as sess:
        updates = ["status = :st"]
        params = {"tid": task_id, "st": status}
        if status == "completed":
            updates.append("completed_at = NOW()")
        if actual_minutes:
            updates.append("actual_minutes = :am")
            params["am"] = actual_minutes
        sess.execute(text(f"UPDATE tasks SET {', '.join(updates)} WHERE id = :tid"), params)
        sess.commit()


def get_tasks_by_session(session_id: str) -> List[dict]:
    """获取会话下所有关卡"""
    with get_session() as sess:
        rows = sess.execute(
            text("SELECT * FROM tasks WHERE session_id = :sid ORDER BY sort_order"),
            {"sid": session_id}
        ).fetchall()
        return [dict(r._mapping) for r in rows]


def get_task(task_id: str) -> Optional[dict]:
    """获取单个关卡"""
    with get_session() as sess:
        row = sess.execute(text("SELECT * FROM tasks WHERE id = :tid"), {"tid": task_id}).fetchone()
        return dict(row._mapping) if row else None


# ============================================================
# 答疑日志
# ============================================================
def insert_qa_log(user_id: str, question: str, answer: str, answer_mode: str,
                  source_docs: list, task_id: str = None, confidence: str = "medium") -> str:
    """记录提问日志"""
    ensure_user(user_id)
    log_id = f"qa_{uuid.uuid4().hex[:12]}"
    with get_session() as sess:
        sess.execute(
            text("""INSERT INTO qa_logs (id, user_id, task_id, question, answer, answer_mode, source_docs, confidence)
                    VALUES (:id, :uid, :tid, :q, :a, :am, :sd, :cf)"""),
            {
                "id": log_id, "uid": user_id, "tid": task_id,
                "q": question, "a": answer, "am": answer_mode,
                "sd": json.dumps(source_docs, ensure_ascii=False),
                "cf": confidence,
            }
        )
        sess.commit()
    return log_id


def get_recent_qa_logs(user_id: str, days: int = 7) -> List[dict]:
    """获取最近 N 天的提问记录（用于薄弱点分析）"""
    since = datetime.now() - timedelta(days=days)
    with get_session() as sess:
        rows = sess.execute(
            text("SELECT * FROM qa_logs WHERE user_id = :uid AND created_at >= :since ORDER BY created_at DESC"),
            {"uid": user_id, "since": since}
        ).fetchall()
        return [dict(r._mapping) for r in rows]


# ============================================================
# 资料
# ============================================================
def insert_material(data: dict) -> str:
    """插入资料记录"""
    ensure_user(data["user_id"])
    mid = data.get("id") or f"mat_{uuid.uuid4().hex[:12]}"
    with get_session() as sess:
        sess.execute(
            text("""INSERT INTO materials (id, user_id, filename, file_type, file_path,
                    subject, chapter, knowledge_point, ocr_text, chunk_count, qdrant_indexed)
                    VALUES (:id, :uid, :fn, :ft, :fp, :subj, :ch, :kp, :ot, :cc, :qi)"""),
            {
                "id": mid, "uid": data["user_id"],
                "fn": data["filename"], "ft": data["file_type"],
                "fp": data.get("file_path", ""),
                "subj": data.get("subject", ""), "ch": data.get("chapter", ""),
                "kp": data.get("knowledge_point", ""),
                "ot": data.get("ocr_text", ""), "cc": data.get("chunk_count", 0),
                "qi": 1 if data.get("qdrant_indexed") else 0,
            }
        )
        sess.commit()
    return mid


def insert_material_chunks(chunks: List[dict]):
    """批量插入文本块"""
    with get_session() as sess:
        for c in chunks:
            sess.execute(
                text("""INSERT INTO material_chunks (id, material_id, chunk_index, content, qdrant_point_id, embedding_model)
                        VALUES (:id, :mid, :ci, :ct, :qpi, :em)"""),
                {
                    "id": c["id"],
                    "mid": c["material_id"],
                    "ci": c["chunk_index"],
                    "ct": c["content"],
                    "qpi": c.get("qdrant_point_id", ""),
                    "em": c.get("embedding_model", ""),
                }
            )
        sess.commit()


def get_material(material_id: str) -> Optional[dict]:
    """获取单个资料"""
    with get_session() as sess:
        row = sess.execute(text("SELECT * FROM materials WHERE id = :mid"), {"mid": material_id}).fetchone()
        return dict(row._mapping) if row else None


def get_materials_by_ids(material_ids: List[str]) -> List[dict]:
    """批量获取资料"""
    if not material_ids:
        return []
    with get_session() as sess:
        placeholders = ",".join([f":mid{i}" for i in range(len(material_ids))])
        params = {f"mid{i}": mid for i, mid in enumerate(material_ids)}
        rows = sess.execute(
            text(f"SELECT * FROM materials WHERE id IN ({placeholders})"),
            params
        ).fetchall()
        return [dict(r._mapping) for r in rows]


# ============================================================
# 报告
# ============================================================
def insert_report(data: dict) -> str:
    """写入学习报告"""
    ensure_user(data["user_id"])
    rid = data.get("id") or f"rpt_{uuid.uuid4().hex[:12]}"
    with get_session() as sess:
        sess.execute(
            text("""INSERT INTO reports (id, user_id, session_id, task_id, completion,
                    weak_points, recommended_material_ids, next_tasks_suggestion)
                    VALUES (:id, :uid, :sid, :tid, :comp, :wp, :rmi, :nts)"""),
            {
                "id": rid, "uid": data["user_id"],
                "sid": data.get("session_id"), "tid": data.get("task_id"),
                "comp": json.dumps(data.get("completion", {}), ensure_ascii=False),
                "wp": json.dumps(data.get("weak_points", []), ensure_ascii=False),
                "rmi": json.dumps(data.get("recommended_material_ids", []), ensure_ascii=False),
                "nts": data.get("next_tasks_suggestion", ""),
            }
        )
        sess.commit()
    return rid
