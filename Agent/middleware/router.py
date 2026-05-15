"""
[DEPRECATED] 中间件路由器 — 已被 graph/workflow.py 替代

所有路由逻辑已迁移至 LangGraph 工作流:
  - route() 分发 → classifier_node + supervisor_node + route_by_request_type
  - _handle_plan/upload/qa/review → planner/librarian/coach/reviewer_node
  - chat 类型由 classifier_node 预处理后改写为上述四种之一

保留此文件以备回退对比，新代码请使用:
  from graph.state import build_state_from_request
  from graph.workflow import get_graph

@app.route 示例:
  initial_state = build_state_from_request(sq_request)
  final_state = get_graph().invoke(initial_state)
"""
from typing import Dict, Any, Optional
from schemas import RequestType, StudyQuestRequest, StudyQuestResponse


class RequestRouter:
    """
    RequestType 中间件路由器

    路由映射：
      plan    → Planner
      upload  → Librarian
      qa      → Coach
      review  → Reviewer
      chat    → 应在 LangGraph classifier_node 被改写，不应到达此处
    """

    def __init__(self):
        self._planner = None
        self._librarian = None
        self._coach = None
        self._reviewer = None

    @property
    def planner(self):
        if self._planner is None:
            from agents.planner import PlannerAgent
            self._planner = PlannerAgent()
        return self._planner

    @property
    def librarian(self):
        if self._librarian is None:
            from agents.librarian import LibrarianAgent
            self._librarian = LibrarianAgent()
        return self._librarian

    @property
    def coach(self):
        if self._coach is None:
            from agents.coach import CoachAgent
            self._coach = CoachAgent()
        return self._coach

    @property
    def reviewer(self):
        if self._reviewer is None:
            from agents.reviewer import ReviewerAgent
            self._reviewer = ReviewerAgent()
        return self._reviewer

    def route(self, request: StudyQuestRequest) -> StudyQuestResponse:
        """
        根据 RequestType 路由到对应 Agent 并返回统一响应
        """
        try:
            rt = request.request_type

            if rt == RequestType.PLAN:
                data = self._handle_plan(request)
            elif rt == RequestType.UPLOAD:
                data = self._handle_upload(request)
            elif rt == RequestType.QA:
                data = self._handle_qa(request)
            elif rt == RequestType.REVIEW:
                data = self._handle_review(request)
            elif rt == RequestType.CHAT:
                # chat 应由 LangGraph classifier_node 预处理，不应到达此处
                return StudyQuestResponse(
                    success=False,
                    request_type=rt,
                    error="chat 请求未经过分类预处理，请使用 LangGraph 工作流入口",
                )
            else:
                return StudyQuestResponse(
                    success=False,
                    request_type=rt,
                    error=f"未知的 RequestType: {rt}",
                )

            return StudyQuestResponse(
                success=True,
                request_type=rt,
                data=data,
                message=self._get_success_message(rt),
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return StudyQuestResponse(
                success=False,
                request_type=request.request_type,
                error=str(e),
            )

    def _handle_plan(self, req: StudyQuestRequest) -> Dict[str, Any]:
        """处理规划请求"""
        result = self.planner.plan(
            user_id=req.user_id,
            goal_text=req.goal_text or "默认学习目标",
            available_hours=req.available_hours or 2.0,
            constraints=req.constraints,
        )
        # 确保 tasks 可序列化
        return {
            "session_id": result.get("session_id", ""),
            "tasks": result.get("tasks", []),
            "total_estimated_minutes": result.get("total_estimated_minutes", 0),
            "knowledge_summary": result.get("knowledge_summary", ""),
            "web_search_used": result.get("web_search_used", False),
            "created_at": result.get("created_at", ""),
        }

    def _handle_upload(self, req: StudyQuestRequest) -> Dict[str, Any]:
        """处理资料上传请求"""
        result = self.librarian.process_files(
            user_id=req.user_id,
            file_paths=req.file_paths,
            file_urls=req.file_urls,
        )
        return result

    def _handle_qa(self, req: StudyQuestRequest) -> Dict[str, Any]:
        """处理答疑请求"""
        result = self.coach.answer(
            user_id=req.user_id,
            question=req.question or "",
            answer_mode=req.answer_mode.value if req.answer_mode else "auto",
            active_task_id=req.active_task_id,
        )
        return result

    def _handle_review(self, req: StudyQuestRequest) -> Dict[str, Any]:
        """处理复盘请求"""
        result = self.reviewer.review(
            user_id=req.user_id,
            session_id=req.review_session_id,
            task_id=req.review_task_id,
            time_range=req.review_time_range or "7d",
        )
        return result

    def _get_success_message(self, request_type: RequestType) -> str:
        messages = {
            RequestType.PLAN: "学习关卡规划完成",
            RequestType.UPLOAD: "资料处理完成",
            RequestType.QA: "答疑完成",
            RequestType.REVIEW: "学习报告生成完成",
            RequestType.CHAT: "chat 已分类处理",
        }
        return messages.get(request_type, "处理完成")


# 全局单例
_router: Optional[RequestRouter] = None


def get_router() -> RequestRouter:
    global _router
    if _router is None:
        _router = RequestRouter()
    return _router
