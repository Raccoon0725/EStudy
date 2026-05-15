"""
SQLAlchemy 声明式 ORM 模型
七张表：User, Session, Task, QaLog, Material, MaterialChunk, Report
"""
from sqlalchemy import (
    Column, String, Integer, Text, Date, DateTime, Enum, ForeignKey, Index,
    JSON, Float, Boolean,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

# ---------------------------------------------------------------------------
# 通用：生成业务 ID（前缀 + 12 位 hex）
# ---------------------------------------------------------------------------
def _uid(prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# 1. User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    username = Column(String(128), nullable=False)
    password_hash = Column(String(256), nullable=False)
    avatar = Column(String(512), default="")
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)

    # 关系
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    qa_logs = relationship("QaLog", back_populates="user", cascade="all, delete-orphan")
    materials = relationship("Material", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_username", "username"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )


# ---------------------------------------------------------------------------
# 2. Session
# ---------------------------------------------------------------------------
class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    goal_text = Column(Text)
    date = Column(Date, nullable=False, server_default=func.current_timestamp())
    total_minutes = Column(Integer, default=0)
    status = Column(
        Enum("active", "completed", "cancelled", name="session_status"),
        default="active",
    )
    planner_json = Column(Text)  # LONGTEXT in MySQL
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    user = relationship("User", back_populates="sessions")
    tasks = relationship("Task", back_populates="session", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="session")

    __table_args__ = (
        Index("idx_user_date", "user_id", "date"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )


# ---------------------------------------------------------------------------
# 3. Task
# ---------------------------------------------------------------------------
class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String(64), ForeignKey("sessions.id", ondelete="SET NULL"))
    parent_id = Column(String(64), default=None)
    subject = Column(String(128), nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text)
    task_type = Column(
        Enum("understand", "practice", "memorize", "correct", "review", "break", name="task_type"),
        default="understand",
    )
    estimated_minutes = Column(Integer, default=30)
    actual_minutes = Column(Integer, default=0)
    status = Column(
        Enum("pending", "in_progress", "completed", "cancelled", name="task_status"),
        default="pending",
    )
    priority = Column(Integer, default=1)
    sort_order = Column(Integer, default=0)
    material_ids = Column(JSON)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="tasks")
    session = relationship("Session", back_populates="tasks")
    qa_logs = relationship("QaLog", back_populates="task")

    __table_args__ = (
        Index("idx_user", "user_id"),
        Index("idx_session", "session_id"),
        Index("idx_status", "user_id", "status"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )


# ---------------------------------------------------------------------------
# 4. QaLog
# ---------------------------------------------------------------------------
class QaLog(Base):
    __tablename__ = "qa_logs"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(64), ForeignKey("tasks.id", ondelete="SET NULL"))
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    answer_mode = Column(
        Enum("hint", "explain", "review", name="qa_answer_mode"),
        default="explain",
    )
    source_docs = Column(JSON, comment="引用的资料来源列表")
    confidence = Column(String(16), default="medium")
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)

    user = relationship("User", back_populates="qa_logs")
    task = relationship("Task", back_populates="qa_logs")

    __table_args__ = (
        Index("idx_user", "user_id"),
        Index("idx_task", "task_id"),
        Index("idx_created", "created_at"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )


# ---------------------------------------------------------------------------
# 5. Material
# ---------------------------------------------------------------------------
class Material(Base):
    __tablename__ = "materials"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(512), nullable=False)
    file_type = Column(String(32), nullable=False)
    file_path = Column(String(1024), nullable=False)
    subject = Column(String(128), default="")
    chapter = Column(String(256), default="")
    knowledge_point = Column(String(256), default="")
    ocr_text = Column(Text)
    chunk_count = Column(Integer, default=0)
    qdrant_indexed = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)

    user = relationship("User", back_populates="materials")
    chunks = relationship("MaterialChunk", back_populates="material", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user", "user_id"),
        Index("idx_subject", "user_id", "subject"),
        Index("idx_knowledge", "user_id", "knowledge_point"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )


# ---------------------------------------------------------------------------
# 6. MaterialChunk
# ---------------------------------------------------------------------------
class MaterialChunk(Base):
    __tablename__ = "material_chunks"

    id = Column(String(64), primary_key=True)
    material_id = Column(String(64), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    qdrant_point_id = Column(String(128), default="")
    embedding_model = Column(String(64), default="")
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)

    material = relationship("Material", back_populates="chunks")

    __table_args__ = (
        Index("idx_material", "material_id"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )


# ---------------------------------------------------------------------------
# 7. Report
# ---------------------------------------------------------------------------
class Report(Base):
    __tablename__ = "reports"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String(64), ForeignKey("sessions.id", ondelete="SET NULL"))
    task_id = Column(String(64), ForeignKey("tasks.id", ondelete="SET NULL"))
    completion = Column(JSON, comment="完成情况")
    weak_points = Column(JSON, comment="薄弱点列表")
    recommended_material_ids = Column(JSON)
    next_tasks_suggestion = Column(Text)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)

    user = relationship("User", back_populates="reports")
    session = relationship("Session", back_populates="reports")

    __table_args__ = (
        Index("idx_user", "user_id"),
        Index("idx_session", "session_id"),
        Index("idx_task", "task_id"),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )
