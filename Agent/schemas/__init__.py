"""
请求/响应数据模型
使用 Pydantic v2 定义所有接口数据结构
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================
# RequestType 枚举 —— 中间件路由依据
# ============================================================
class RequestType(str, Enum):
    PLAN = "plan"           # → Planner 规划智能体
    UPLOAD = "upload"       # → Librarian 资料智能体
    QA = "qa"               # → Coach 答疑智能体
    REVIEW = "review"       # → Reviewer 复盘智能体
    CHAT = "chat"           # → Classifier 意图分类后改写为上述四种之一


# ============================================================
# 答疑模式枚举
# ============================================================
class AnswerMode(str, Enum):
    HINT = "hint"         # 提示模式：只给解题思路
    EXPLAIN = "explain"   # 讲解模式：分步骤详细解释
    REVIEW = "review"     # 复盘模式：总结通用方法和易错点
    AUTO = "auto"         # 自动判定


# ============================================================
# 任务类型枚举
# ============================================================
class TaskType(str, Enum):
    UNDERSTAND = "understand"   # 理解概念
    PRACTICE = "practice"       # 练习题
    MEMORIZE = "memorize"       # 记忆背诵
    CORRECT = "correct"         # 纠错订正
    REVIEW = "review"           # 复盘总结
    BREAK = "break"             # 休息


# ============================================================
# 任务/关卡状态
# ============================================================
class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ============================================================
# 通用请求体
# ============================================================
class StudyQuestRequest(BaseModel):
    """统一请求体，中间件根据 request_type 路由到对应 Agent"""
    request_type: RequestType = Field(..., description="请求类型，用于中间件路由")
    user_id: str = Field(..., description="用户唯一标识")
    session_id: Optional[str] = Field(None, description="学习会话 ID")

    # Planner 相关
    goal_text: Optional[str] = Field(None, description="学习目标描述")
    available_hours: Optional[float] = Field(None, description="可用时间（小时）")
    constraints: Optional[Dict[str, Any]] = Field(default_factory=dict, description="约束条件")

    # Coach 相关
    question: Optional[str] = Field(None, description="用户提问内容")
    answer_mode: Optional[AnswerMode] = Field(AnswerMode.AUTO, description="应答模式")
    active_task_id: Optional[str] = Field(None, description="当前活跃关卡 ID")

    # Librarian 相关
    file_paths: Optional[List[str]] = Field(None, description="上传的本地文件路径列表")
    file_urls: Optional[List[str]] = Field(None, description="上传的文件 URL 列表")
    context: Optional[str] = Field(None, description="关联的上下文")

    # Reviewer 相关
    review_task_id: Optional[str] = Field(None, description="要复盘的任务 ID")
    review_session_id: Optional[str] = Field(None, description="要复盘的会话 ID")
    review_time_range: Optional[str] = Field("7d", description="复盘时间范围")


# ============================================================
# 关卡/任务数据模型
# ============================================================
class QuestTask(BaseModel):
    """Planner 输出的单个关卡"""
    index: int = Field(..., description="序号")
    subject: str = Field(..., description="科目")
    title: str = Field(..., description="关卡标题")
    description: str = Field("", description="关卡描述")
    task_type: TaskType = Field(..., description="任务类型")
    estimated_minutes: int = Field(..., description="建议时长（分钟）")
    material_ids: List[str] = Field(default_factory=list, description="关联资料 ID 列表")
    priority: int = Field(1, description="优先级 1-5，越高越优先")
    status: TaskStatus = Field(TaskStatus.PENDING, description="关卡状态")


class PlannerOutput(BaseModel):
    """Planner 完整输出"""
    session_id: str = Field(..., description="学习会话 ID")
    tasks: List[QuestTask] = Field(..., description="关卡列表")
    total_estimated_minutes: int = Field(..., description="总预估时长")
    knowledge_summary: str = Field("", description="RAG 检索到的知识摘要")
    web_search_used: bool = Field(False, description="是否使用了联网搜索")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 资料数据模型
# ============================================================
class MaterialInfo(BaseModel):
    """Librarian 输出的资料信息"""
    material_id: str = Field(..., description="资料 ID")
    filename: str = Field(..., description="原始文件名")
    file_type: str = Field(..., description="文件类型")
    subject: str = Field("", description="科目（AI 分类）")
    chapter: str = Field("", description="章节（AI 分类）")
    knowledge_point: str = Field("", description="知识点（AI 分类）")
    ocr_text_preview: str = Field("", description="OCR/提取文本预览（前200字）")
    chunk_count: int = Field(0, description="文本块数量")
    qdrant_indexed: bool = Field(False, description="是否成功写入 Qdrant")
    uploaded_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class LibrarianOutput(BaseModel):
    """Librarian 完整输出"""
    materials: List[MaterialInfo] = Field(default_factory=list, description="处理结果列表")
    total_chunks: int = Field(0, description="总文本块数")
    errors: List[str] = Field(default_factory=list, description="处理失败的文件")


# ============================================================
# 答疑数据模型
# ============================================================
class SourceCitation(BaseModel):
    """RAG 引用的资料片段"""
    filename: str = Field(..., description="来源文件名")
    chunk_index: int = Field(0, description="文本块序号")
    similarity: float = Field(0.0, description="相似度分数")
    preview: str = Field("", description="引用内容预览")


class CoachOutput(BaseModel):
    """Coach 答疑输出"""
    answer: str = Field(..., description="LLM 生成的回答")
    answer_mode: AnswerMode = Field(..., description="使用的应答模式")
    sources: List[SourceCitation] = Field(default_factory=list, description="引用的资料来源")
    confidence: str = Field("medium", description="置信度 high/medium/low")
    qa_log_id: Optional[str] = Field(None, description="提问日志记录 ID")


# ============================================================
# 复盘报告数据模型
# ============================================================
class WeakPoint(BaseModel):
    """薄弱知识点"""
    knowledge_point: str = Field(..., description="知识点名称")
    frequency: int = Field(0, description="提问/标记频率")
    weight: float = Field(0.0, description="加权分数")


class ReviewReport(BaseModel):
    """Reviewer 输出的学习报告"""
    report_id: str = Field(..., description="报告 ID")
    user_id: str = Field(..., description="用户 ID")
    session_id: Optional[str] = Field(None, description="会话 ID")
    task_id: Optional[str] = Field(None, description="关卡 ID")

    # 完成情况
    tasks_completed: int = Field(0, description="完成关卡数")
    tasks_total: int = Field(0, description="总关卡数")
    total_minutes: int = Field(0, description="总学习时长（分钟）")
    interruption_count: int = Field(0, description="中断次数")
    completion_rate: float = Field(0.0, description="完成率")

    # 薄弱点分析
    weak_points: List[WeakPoint] = Field(default_factory=list, description="Top N 薄弱知识点")

    # 推荐
    recommended_material_ids: List[str] = Field(default_factory=list, description="推荐复习资料 ID")
    next_tasks_suggestion: str = Field("", description="明日学习建议")

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 统一响应体
# ============================================================
class StudyQuestResponse(BaseModel):
    """统一 API 响应"""
    success: bool = Field(True)
    request_type: RequestType = Field(..., description="处理的请求类型")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")
    message: str = Field("", description="附加消息")
    error: Optional[str] = Field(None, description="错误信息")
