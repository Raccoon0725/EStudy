"""
数据库 CRUD 操作层（SQLAlchemy ORM）
提供所有表的高层读写接口，与旧 raw-SQL 版本接口完全兼容
"""
import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from database.connection import get_session
from database.models import (
    User, Session, Task, QaLog, Material, MaterialChunk, Report, _uid,
)


def _to_dict(model) -> Optional[dict]:
    """将 ORM 模型实例转为 dict，兼容旧调用方的 dict 返回值"""
    if model is None:
        return None
    d = {}
    for c in model.__table__.columns:
        val = getattr(model, c.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        d[c.name] = val
    return d


# ============================================================
# 用户
# ============================================================
def ensure_user(user_id: str, username: str = "default") -> str:
    """确保用户存在"""
    with get_session() as sess:
        u = sess.get(User, user_id)
        if not u:
            u = User(id=user_id, username=username, password_hash="")
            sess.add(u)
    return user_id


# ============================================================
# Session
# ============================================================
def create_session(user_id: str, goal_text: str, planner_json: dict) -> str:
    """创建学习会话"""
    ensure_user(user_id)
    sid = _uid("sess")
    with get_session() as sess:
        sess.add(Session(
            id=sid,
            user_id=user_id,
            goal_text=goal_text,
            date=datetime.now().date(),
            planner_json=json.dumps(planner_json, ensure_ascii=False),
        ))
    return sid


def get_session_info(session_id: str) -> Optional[dict]:
    """获取会话信息"""
    with get_session() as sess:
        return _to_dict(sess.get(Session, session_id))


# ============================================================
# Tasks
# ============================================================
def insert_task(task_data: dict) -> str:
    """插入单个关卡"""
    ensure_user(task_data["user_id"])
    tid = task_data.get("id") or _uid("task")
    with get_session() as sess:
        sess.add(Task(
            id=tid,
            user_id=task_data["user_id"],
            session_id=task_data.get("session_id"),
            parent_id=task_data.get("parent_id"),
            subject=task_data.get("subject", ""),
            title=task_data["title"],
            description=task_data.get("description", ""),
            task_type=task_data.get("task_type", "understand"),
            estimated_minutes=task_data.get("estimated_minutes", 30),
            status=task_data.get("status", "pending"),
            priority=task_data.get("priority", 1),
            sort_order=task_data.get("sort_order", 0),
            material_ids=task_data.get("material_ids", []),
        ))
    return tid


def insert_tasks_batch(tasks: List[dict]) -> List[str]:
    """批量插入关卡（单次事务）"""
    ids = []
    with get_session() as sess:
        for t in tasks:
            ensure_user(t["user_id"])
            tid = t.get("id") or _uid("task")
            ids.append(tid)
            sess.add(Task(
                id=tid,
                user_id=t["user_id"],
                session_id=t.get("session_id"),
                parent_id=t.get("parent_id"),
                subject=t.get("subject", ""),
                title=t["title"],
                description=t.get("description", ""),
                task_type=t.get("task_type", "understand"),
                estimated_minutes=t.get("estimated_minutes", 30),
                status=t.get("status", "pending"),
                priority=t.get("priority", 1),
                sort_order=t.get("sort_order", 0),
                material_ids=t.get("material_ids", []),
            ))
    return ids


def update_task_status(task_id: str, status: str, actual_minutes: int = 0):
    """更新关卡状态"""
    with get_session() as sess:
        t = sess.get(Task, task_id)
        if not t:
            return
        t.status = status
        if status == "completed":
            t.completed_at = datetime.now()
        if actual_minutes:
            t.actual_minutes = actual_minutes


def get_tasks_by_session(session_id: str) -> List[dict]:
    """获取会话下所有关卡（按 sort_order 排序）"""
    with get_session() as sess:
        rows = (
            sess.query(Task)
            .filter(Task.session_id == session_id)
            .order_by(Task.sort_order)
            .all()
        )
        return [_to_dict(r) for r in rows]


def get_task(task_id: str) -> Optional[dict]:
    """获取单个关卡"""
    with get_session() as sess:
        return _to_dict(sess.get(Task, task_id))


# ============================================================
# 答疑日志
# ============================================================
def insert_qa_log(user_id: str, question: str, answer: str, answer_mode: str,
                  source_docs: list, task_id: str = None, confidence: str = "medium") -> str:
    """记录提问日志"""
    ensure_user(user_id)
    log_id = _uid("qa")
    with get_session() as sess:
        sess.add(QaLog(
            id=log_id,
            user_id=user_id,
            task_id=task_id,
            question=question,
            answer=answer,
            answer_mode=answer_mode,
            source_docs=source_docs,
            confidence=confidence,
        ))
    return log_id


def get_recent_qa_logs(user_id: str, days: int = 7) -> List[dict]:
    """获取最近 N 天的提问记录（用于薄弱点分析）"""
    since = datetime.now() - timedelta(days=days)
    with get_session() as sess:
        rows = (
            sess.query(QaLog)
            .filter(QaLog.user_id == user_id, QaLog.created_at >= since)
            .order_by(QaLog.created_at.desc())
            .all()
        )
        return [_to_dict(r) for r in rows]


# ============================================================
# 资料
# ============================================================
def insert_material(data: dict) -> str:
    """插入资料记录"""
    ensure_user(data["user_id"])
    mid = data.get("id") or _uid("mat")
    with get_session() as sess:
        sess.add(Material(
            id=mid,
            user_id=data["user_id"],
            filename=data["filename"],
            file_type=data["file_type"],
            file_path=data.get("file_path", ""),
            subject=data.get("subject", ""),
            chapter=data.get("chapter", ""),
            knowledge_point=data.get("knowledge_point", ""),
            ocr_text=data.get("ocr_text", ""),
            chunk_count=data.get("chunk_count", 0),
            qdrant_indexed=bool(data.get("qdrant_indexed")),
        ))
    return mid


def insert_material_chunks(chunks: List[dict]):
    """批量插入文本块（单次事务）"""
    with get_session() as sess:
        for c in chunks:
            sess.add(MaterialChunk(
                id=c["id"],
                material_id=c["material_id"],
                chunk_index=c["chunk_index"],
                content=c["content"],
                qdrant_point_id=c.get("qdrant_point_id", ""),
                embedding_model=c.get("embedding_model", ""),
            ))


def get_material(material_id: str) -> Optional[dict]:
    """获取单个资料"""
    with get_session() as sess:
        return _to_dict(sess.get(Material, material_id))


def get_materials_by_ids(material_ids: List[str]) -> List[dict]:
    """批量获取资料"""
    if not material_ids:
        return []
    with get_session() as sess:
        rows = sess.query(Material).filter(Material.id.in_(material_ids)).all()
        return [_to_dict(r) for r in rows]


# ============================================================
# 报告
# ============================================================
def insert_report(data: dict) -> str:
    """写入学习报告"""
    ensure_user(data["user_id"])
    rid = data.get("id") or _uid("rpt")
    with get_session() as sess:
        sess.add(Report(
            id=rid,
            user_id=data["user_id"],
            session_id=data.get("session_id"),
            task_id=data.get("task_id"),
            completion=data.get("completion", {}),
            weak_points=data.get("weak_points", []),
            recommended_material_ids=data.get("recommended_material_ids", []),
            next_tasks_suggestion=data.get("next_tasks_suggestion", ""),
        ))
    return rid
