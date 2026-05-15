"""
LangGraph State 定义

共享 State 在 Agent 节点之间流转，每个节点读取需要的字段并返回更新。

设计参考：Agent系统通用设计模式 7.3 节
"""
from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class GraphState(TypedDict):
    """LangGraph 工作流的共享状态"""

    # 消息历史（累加语义，operator='+'）
    messages: Annotated[List[BaseMessage], add_messages]

    # 用户和会话
    user_id: str
    session_id: Optional[str]

    # 请求类型
    request_type: str

    # Planner 输入
    goal_text: str
    available_hours: float
    constraints: Dict[str, Any]

    # Coach 输入
    question_text: str
    current_answer_mode: str  # hint / explain / review / auto

    # Librarian 输入
    uploaded_files: List[str]
    uploaded_urls: List[str]
    context: Optional[str]

    # Reviewer 输入
    review_session_id: Optional[str]
    review_task_id: Optional[str]
    review_time_range: str

    # 当前活跃关卡信息
    active_task_id: Optional[str]
    active_task_info: Optional[Dict[str, Any]]

    # 各 Agent 输出
    planner_output: Optional[Dict[str, Any]]
    coach_output: Optional[Dict[str, Any]]
    librarian_output: Optional[Dict[str, Any]]
    reviewer_output: Optional[Dict[str, Any]]

    # Supervisor 路由决策
    next_agent: Optional[str]

    # 最终输出
    final_response: Optional[Dict[str, Any]]
    response_message: str

    # 错误处理
    error: Optional[str]


def create_initial_state(
    user_id: str,
    request_type: str = "plan",
    goal_text: str = "",
    question_text: str = "",
    available_hours: float = 2.0,
    constraints: Dict[str, Any] = None,
    uploaded_files: List[str] = None,
    uploaded_urls: List[str] = None,
    active_task_id: str = None,
    current_answer_mode: str = "auto",
    review_session_id: str = None,
    review_task_id: str = None,
    review_time_range: str = "7d",
) -> GraphState:
    """创建初始 State"""
    return {
        "messages": [],
        "user_id": user_id,
        "session_id": None,
        "request_type": request_type,
        "goal_text": goal_text,
        "question_text": question_text,
        "available_hours": available_hours,
        "constraints": constraints or {},
        "uploaded_files": uploaded_files or [],
        "uploaded_urls": uploaded_urls or [],
        "active_task_id": active_task_id,
        "active_task_info": None,
        "current_answer_mode": current_answer_mode,
        "review_session_id": review_session_id,
        "review_task_id": review_task_id,
        "review_time_range": review_time_range,
        "planner_output": None,
        "coach_output": None,
        "librarian_output": None,
        "reviewer_output": None,
        "next_agent": None,
        "final_response": None,
        "response_message": "",
        "error": None,
    }


def build_state_from_request(req) -> GraphState:
    """
    将 StudyQuestRequest (Pydantic) 转换为 GraphState

    这是 app.py / main.py 连接 LangGraph 的桥梁。
    """
    from schemas import RequestType

    answer_mode = "auto"
    if req.answer_mode:
        answer_mode = req.answer_mode.value if hasattr(req.answer_mode, "value") else str(req.answer_mode)

    return {
        "messages": [],
        "user_id": req.user_id,
        "session_id": req.session_id,
        "request_type": req.request_type.value if hasattr(req.request_type, "value") else str(req.request_type),
        "goal_text": req.goal_text or "",
        "question_text": req.question or "",
        "available_hours": req.available_hours or 2.0,
        "constraints": req.constraints or {},
        "uploaded_files": req.file_paths or [],
        "uploaded_urls": req.file_urls or [],
        "context": getattr(req, "context", None) or "",
        "active_task_id": req.active_task_id,
        "active_task_info": None,
        "current_answer_mode": answer_mode,
        "review_session_id": req.review_session_id,
        "review_task_id": req.review_task_id,
        "review_time_range": req.review_time_range or "7d",
        "planner_output": None,
        "coach_output": None,
        "librarian_output": None,
        "reviewer_output": None,
        "next_agent": None,
        "final_response": None,
        "response_message": "",
        "error": None,
    }
