"""
StudyQuest CLI 入口

直接命令行测试各 Agent，无需启动 Flask 服务。
所有请求通过 LangGraph 工作流路由。

使用示例:
  python main.py plan --user user_001 --goal "3小时复习数学函数" --hours 3
  python main.py upload --user user_001 --files ./test.pdf ./notes.jpg
  python main.py qa --user user_001 --question "二次函数单调性怎么判断？" --mode explain
  python main.py review --user user_001 --session sess_abc123
  python main.py chat --user user_001 --message "帮我规划3小时复习数学函数"
"""
import sys
import json
import argparse
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from config import ensure_directories
from database.connection import ensure_database, ensure_tables
from schemas import StudyQuestRequest, RequestType, AnswerMode
from graph.state import build_state_from_request
from graph.workflow import get_graph
from utils.logger import setup_logger


logger = setup_logger("StudyQuest.CLI")


def init_system():
    """初始化基础设施"""
    ensure_directories()
    try:
        ensure_database()
        ensure_tables()
    except Exception as e:
        logger.warning(f"MySQL 初始化失败: {e}")
    # 预热 LangGraph
    try:
        get_graph()
        logger.info("LangGraph 工作流已编译")
    except Exception as e:
        logger.error(f"LangGraph 编译失败: {e}")
    logger.info("系统初始化完成")


def _invoke_graph(req: StudyQuestRequest) -> dict:
    """统一入口：StudyQuestRequest → LangGraph → final_state"""
    initial_state = build_state_from_request(req)
    graph = get_graph()
    return graph.invoke(initial_state)


def cmd_plan(args):
    """执行规划"""
    req = StudyQuestRequest(
        request_type=RequestType.PLAN,
        user_id=args.user,
        goal_text=args.goal,
        available_hours=args.hours or 2.0,
        constraints=json.loads(args.constraints) if args.constraints else {},
    )
    final_state = _invoke_graph(req)
    _print_response(final_state, args)


def cmd_upload(args):
    """执行资料上传"""
    files = args.files.split(",") if args.files else []
    req = StudyQuestRequest(
        request_type=RequestType.UPLOAD,
        user_id=args.user,
        file_paths=[f.strip() for f in files if f.strip()],
        context=args.context or {},
    )
    final_state = _invoke_graph(req)
    _print_response(final_state, args)


def cmd_qa(args):
    """执行答疑"""
    mode = AnswerMode(args.mode) if args.mode else AnswerMode.AUTO
    req = StudyQuestRequest(
        request_type=RequestType.QA,
        user_id=args.user,
        question=args.question,
        answer_mode=mode,
        active_task_id=args.task_id,
    )
    final_state = _invoke_graph(req)
    _print_response(final_state, args)


def cmd_review(args):
    """执行复盘"""
    req = StudyQuestRequest(
        request_type=RequestType.REVIEW,
        user_id=args.user,
        review_session_id=args.session,
        review_task_id=args.task_id,
        review_time_range=args.time_range or "7d",
    )
    final_state = _invoke_graph(req)
    _print_response(final_state, args)


def cmd_chat(args):
    """执行 chat — 自然语言输入，自动分类到对应 Agent"""
    req = StudyQuestRequest(
        request_type=RequestType.CHAT,
        user_id=args.user,
        goal_text=args.message,
    )
    final_state = _invoke_graph(req)
    _print_response(final_state, args)


def _print_response(final_state: dict, args):
    """从 LangGraph final_state 提取并输出响应"""
    success = final_state.get("error") is None
    data = final_state.get("final_response") or {}
    message = final_state.get("response_message", "")
    error = final_state.get("error")
    rt = final_state.get("request_type", "plan")

    if args.json_output:
        print(json.dumps({
            "success": success,
            "request_type": rt,
            "data": data,
            "message": message,
            "error": error,
        }, ensure_ascii=False, indent=2))
        return

    from rich.console import Console
    from rich.panel import Panel
    from rich.json import JSON

    console = Console()

    if success:
        console.print(Panel.fit(
            f"[bold green]✓ {message}[/bold green]",
            title="StudyQuest",
        ))
        if data:
            if rt == "plan" and "tasks" in data:
                console.print(f"\n[bold]关卡列表 ({len(data['tasks'])} 关):[/bold]")
                for t in data["tasks"]:
                    icon = {"understand": "📖", "practice": "✏️", "memorize": "🧠",
                            "correct": "🔧", "review": "📊", "break": "☕"}.get(
                        t.get("task_type", ""), "📌")
                    console.print(
                        f"  {icon} [{t.get('subject', '')}] {t.get('title', '')} "
                        f"({t.get('estimated_minutes', 0)}min) [dim]优先级:{t.get('priority', 1)}[/dim]"
                    )
            elif rt == "qa":
                console.print(f"\n[bold]回答 (模式: {data.get('answer_mode', '')}):[/bold]")
                console.print(data.get("answer", ""))
                if data.get("sources"):
                    console.print("\n[dim]引用来源:[/dim]")
                    for s in data["sources"]:
                        console.print(f"  • {s['filename']} (相关度: {s['similarity']})")
            elif rt == "review":
                console.print(f"\n[bold]学习报告:[/bold]")
                console.print(f"  完成率: {data.get('completion_rate', 0):.0%}")
                console.print(f"  总时长: {data.get('total_minutes', 0)} 分钟")
                console.print(f"\n[bold]薄弱点:[/bold]")
                for wp in data.get("weak_points", []):
                    console.print(f"  • {wp['knowledge_point']} (频率: {wp.get('frequency', 0)})")
                console.print(f"\n[bold]明日建议:[/bold]")
                console.print(data.get("next_tasks_suggestion", ""))
            elif rt == "upload":
                console.print(f"\n[bold]处理结果:[/bold]")
                for m in data.get("materials", []):
                    console.print(
                        f"  • {m['filename']} → {m.get('subject', '')} > "
                        f"{m.get('chapter', '')} > {m.get('knowledge_point', '')}"
                    )
                if data.get("errors"):
                    console.print(f"\n[red]失败: {data['errors']}[/red]")
            else:
                console.print(JSON(json.dumps(data, ensure_ascii=False)))
    else:
        console.print(Panel.fit(
            f"[bold red]✗ {error}[/bold red]",
            title="StudyQuest Error",
        ))


def main():
    parser = argparse.ArgumentParser(
        description="StudyQuest - 学习助手多智能体系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json-output", action="store_true", help="以 JSON 格式输出")

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # plan
    p_plan = subparsers.add_parser("plan", help="规划学习关卡")
    p_plan.add_argument("--user", required=True, help="用户 ID")
    p_plan.add_argument("--goal", required=True, help="学习目标描述")
    p_plan.add_argument("--hours", type=float, help="可用时间（小时）")
    p_plan.add_argument("--constraints", help="约束条件 JSON")

    # upload
    p_upload = subparsers.add_parser("upload", help="上传学习资料")
    p_upload.add_argument("--user", required=True, help="用户 ID")
    p_upload.add_argument("--files", help="文件路径列表，逗号分隔")

    # qa
    p_qa = subparsers.add_parser("qa", help="AI 答疑")
    p_qa.add_argument("--user", required=True, help="用户 ID")
    p_qa.add_argument("--question", required=True, help="提问内容")
    p_qa.add_argument("--mode", choices=["hint", "explain", "review", "auto"], default="auto")
    p_qa.add_argument("--task-id", help="关联关卡 ID")

    # review
    p_review = subparsers.add_parser("review", help="生成学习报告")
    p_review.add_argument("--user", required=True, help="用户 ID")
    p_review.add_argument("--session", help="会话 ID")
    p_review.add_argument("--task-id", help="关卡 ID")
    p_review.add_argument("--time-range", default="7d", help="时间范围")

    # chat
    p_chat = subparsers.add_parser("chat", help="自然语言输入，自动分类")
    p_chat.add_argument("--user", required=True, help="用户 ID")
    p_chat.add_argument("--message", required=True, help="自然语言描述的学习需求")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    init_system()

    commands = {
        "plan": cmd_plan,
        "upload": cmd_upload,
        "qa": cmd_qa,
        "review": cmd_review,
        "chat": cmd_chat,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
