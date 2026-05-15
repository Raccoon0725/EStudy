"""
LangGraph 工作流定义

多 Agent 编排图：
  classifier (chat预处理) → supervisor (条件路由) → planner / librarian / coach / reviewer
    → format_response → END

设计参考：Agent系统通用设计模式 第七章 —— A2A 编排模式
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from graph.state import GraphState
import sqlite3
from pathlib import Path


# ============================================================
# Agent 节点函数
# 每个节点从 State 读取输入，执行后返回 State 更新
# ============================================================

def classifier_node(state: GraphState) -> dict:
    """
    Chat 分类节点：当 request_type 为 "chat" 时，调用 ClassifierAgent
    分析用户输入并改写 request_type 和对应参数字段。

    如果 request_type 不是 "chat"，直接透传。
    """
    request_type = state.get("request_type", "plan")

    if request_type != "chat":
        return {}

    from agents.classifier import ClassifierAgent

    # 取用户消息：优先 goal_text，其次 question_text
    message = state.get("goal_text") or state.get("question_text") or ""
    if not message.strip():
        return {"error": "[Classifier] chat 请求缺少消息内容"}

    try:
        agent = ClassifierAgent()
        result = agent.classify(message)

        classified_type = result.get("request_type", "qa")
        updates = {"request_type": classified_type}

        # 根据分类结果填充对应字段
        if classified_type == "plan":
            updates["goal_text"] = result.get("goal_text", message)
            updates["available_hours"] = result.get("available_hours", 2.0)
        elif classified_type == "qa":
            updates["question_text"] = result.get("question", message)
            updates["current_answer_mode"] = result.get("answer_mode", "auto")
        elif classified_type == "review":
            updates["review_time_range"] = result.get("review_time_range", "7d")
        elif classified_type == "upload":
            # upload 需要实际文件，chat 场景下通常无文件路径
            # 若 uploaded_files 和 uploaded_urls 均为空，降级为 qa
            has_files = state.get("uploaded_files") or state.get("uploaded_urls")
            if not has_files:
                updates["request_type"] = "qa"
                updates["question_text"] = message
                updates["current_answer_mode"] = "auto"
            else:
                updates["goal_text"] = message

        return updates
    except Exception as e:
        return {"error": f"[Classifier] {str(e)}"}


def supervisor_node(state: GraphState) -> dict:
    """
    Supervisor 节点：根据 request_type 决定路由到哪个 Agent。
    """
    request_type = state.get("request_type", "plan")
    return {"next_agent": request_type}


def planner_node(state: GraphState) -> dict:
    """Planner 节点：调用规划智能体"""
    from agents.planner import PlannerAgent

    try:
        agent = PlannerAgent()
        result = agent.plan(
            user_id=state["user_id"],
            goal_text=state.get("goal_text") or state.get("question_text") or "学习目标",
            available_hours=state.get("available_hours", 2.0),
            constraints=state.get("constraints"),
        )
        return {
            "planner_output": result,
            "session_id": result.get("session_id"),
        }
    except Exception as e:
        return {"error": f"[Planner] {str(e)}"}


def librarian_node(state: GraphState) -> dict:
    """Librarian 节点：调用资料智能体"""
    from agents.librarian import LibrarianAgent

    try:
        agent = LibrarianAgent()
        result = agent.process_files(
            user_id=state["user_id"],
            file_paths=state.get("uploaded_files", []),
            file_urls=state.get("uploaded_urls", []),
            context=state.get("context"),
        )
        return {"librarian_output": result}
    except Exception as e:
        return {"error": f"[Librarian] {str(e)}"}


def coach_node(state: GraphState) -> dict:
    """Coach 节点：调用答疑智能体"""
    from agents.coach import CoachAgent

    try:
        agent = CoachAgent()
        result = agent.answer(
            user_id=state["user_id"],
            question=state.get("question_text") or state.get("goal_text") or "",
            answer_mode=state.get("current_answer_mode", "auto"),
            active_task_id=state.get("active_task_id"),
        )
        return {"coach_output": result}
    except Exception as e:
        return {"error": f"[Coach] {str(e)}"}


def reviewer_node(state: GraphState) -> dict:
    """Reviewer 节点：调用复盘智能体"""
    from agents.reviewer import ReviewerAgent

    try:
        agent = ReviewerAgent()
        result = agent.review(
            user_id=state["user_id"],
            session_id=state.get("review_session_id") or state.get("session_id"),
            task_id=state.get("review_task_id") or state.get("active_task_id"),
            time_range=state.get("review_time_range", "7d"),
        )
        return {"reviewer_output": result}
    except Exception as e:
        return {"error": f"[Reviewer] {str(e)}"}


def format_response_node(state: GraphState) -> dict:
    """
    从 Agent 输出中提取最终响应，组装为等价于 StudyQuestResponse.data 的 dict。
    """
    error = state.get("error")
    rt = state.get("request_type", "plan")

    if error:
        # chat 分类失败的特例处理
        if rt == "chat":
            return {
                "final_response": {
                    "chat_processed": False,
                    "message": "chat 分类失败，请尝试使用具体功能（plan/qa/upload/review）",
                },
                "response_message": error,
                "error": None,  # 错误已被妥善处理，不应继续传播
            }
        return {
            "final_response": None,
            "response_message": error,
            "error": None,  # 错误已被妥善处理，不应继续传播
        }

    # 各 request_type 的成功消息
    messages = {
        "plan": "学习关卡规划完成",
        "upload": "资料处理完成",
        "qa": "答疑完成",
        "review": "学习报告生成完成",
    }

    if rt == "plan":
        po = state.get("planner_output") or {}
        data = {
            "session_id": po.get("session_id", ""),
            "tasks": po.get("tasks", []),
            "total_estimated_minutes": po.get("total_estimated_minutes", 0),
            "knowledge_summary": po.get("knowledge_summary", ""),
            "web_search_used": po.get("web_search_used", False),
            "created_at": po.get("created_at", ""),
        }
    elif rt == "upload":
        lo = state.get("librarian_output") or {}
        data = {
            "materials": lo.get("materials", []),
            "total_chunks": lo.get("total_chunks", 0),
            "errors": lo.get("errors", []),
        }
    elif rt == "qa":
        co = state.get("coach_output") or {}
        data = {
            "answer": co.get("answer", ""),
            "answer_mode": co.get("answer_mode", ""),
            "sources": co.get("sources", []),
            "confidence": co.get("confidence", "medium"),
            "qa_log_id": co.get("qa_log_id", ""),
            "web_search_used": co.get("web_search_used", False),
        }
    elif rt == "review":
        ro = state.get("reviewer_output") or {}
        data = {
            "report_id": ro.get("report_id", ""),
            "tasks_completed": ro.get("tasks_completed", 0),
            "tasks_total": ro.get("tasks_total", 0),
            "total_minutes": ro.get("total_minutes", 0),
            "completion_rate": ro.get("completion_rate", 0.0),
            "weak_points": ro.get("weak_points", []),
            "recommended_material_ids": ro.get("recommended_material_ids", []),
            "next_tasks_suggestion": ro.get("next_tasks_suggestion", ""),
            "created_at": ro.get("created_at", ""),
        }
    elif rt == "chat":
        # chat 正常不应到达此处（classifier 已改写或 error 路径已拦截）
        # 此处仅作极端兜底
        data = {}
        messages["chat"] = "chat 处理异常"
    else:
        data = {}
        messages[rt] = "处理完成"

    return {
        "final_response": data,
        "response_message": messages.get(rt, "处理完成"),
    }


# ============================================================
# 条件路由函数
# ============================================================

def route_after_classify(state: GraphState) -> Literal["supervisor", "format_response"]:
    """
    classifier 之后的分流：有错误直接跳到 format_response，
    避免浪费 LLM 调用。正常情况进入 supervisor 继续路由。
    """
    if state.get("error"):
        return "format_response"
    return "supervisor"


def route_by_request_type(state: GraphState) -> Literal["planner", "librarian", "coach", "reviewer"]:
    """
    根据 request_type 决定下一个 Agent 节点。

    映射关系：plan→planner, upload→librarian, qa→coach, review→reviewer
    chat 类型在进入 supervisor 前已被 classifier_node 改写，此处不应出现。
    """
    rt = state.get("request_type", "plan")

    route_map = {
        "plan": "planner",
        "upload": "librarian",
        "qa": "coach",
        "review": "reviewer",
        # 兼容旧节点名的直通
        "planner": "planner",
        "librarian": "librarian",
        "coach": "coach",
        "reviewer": "reviewer",
    }

    return route_map.get(rt, "planner")


# ============================================================
# 构建 Graph
# ============================================================

def build_graph() -> StateGraph:
    """
    构建 LangGraph 工作流图

    图结构：
      __start__
         │
         ▼
      classifier (chat→分类改写request_type, 其他透传)
         │
    ┌────┴────┐ error? → format_response
    ▼         ▼
    │    format_response
    │
    supervisor (条件路由)
         │
    ┌────┼────┬────┐
    ▼    ▼    ▼    ▼
    P    L    C    R
    │    │    │    │
    └────┴────┴────┘
         │
         ▼
      format_response
         │
         ▼
      __end__
    """
    workflow = StateGraph(GraphState)

    # 注册节点
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("librarian", librarian_node)
    workflow.add_node("coach", coach_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("format_response", format_response_node)

    # 入口 → classifier（chat 预处理）
    workflow.set_entry_point("classifier")

    # classifier → 条件分流：有错误直接到 format_response，正常到 supervisor
    workflow.add_conditional_edges(
        "classifier",
        route_after_classify,
        {
            "supervisor": "supervisor",
            "format_response": "format_response",
        }
    )

    # supervisor → 条件路由到对应 Agent
    workflow.add_conditional_edges(
        "supervisor",
        route_by_request_type,
        {
            "planner": "planner",
            "librarian": "librarian",
            "coach": "coach",
            "reviewer": "reviewer",
        }
    )

    # 每个 Agent → format_response
    for node_name in ["planner", "librarian", "coach", "reviewer"]:
        workflow.add_edge(node_name, "format_response")

    # format_response → END
    workflow.add_edge("format_response", END)

    return workflow


def compile_graph(with_checkpointer: bool = False) -> StateGraph:
    """
    编译图。

    默认不启用 checkpointer，以避免每次 invoke 都需要传 config.thread_id。
    需要暂停/恢复能力时传 with_checkpointer=True。
    """
    graph = build_graph()
    if with_checkpointer:
        checkpoint_path = str(Path(__file__).parent.parent / "workspace" / ".checkpoint.db")
        Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


# 全局编译好的 graph
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = compile_graph()
    return _graph
