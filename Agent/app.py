"""
StudyQuest Flask API 入口

启动方式:
  python app.py

API 端点:
  POST /api/studyquest  → 统一入口，通过 LangGraph 路由到对应 Agent
  GET  /api/health      → 健康检查
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask, request, jsonify
from flask_cors import CORS
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, ensure_directories
from database.connection import ensure_database, run_migrations
from schemas import StudyQuestRequest, RequestType
from graph.state import build_state_from_request
from graph.workflow import get_graph
from utils.logger import logger

app = Flask(__name__)
CORS(app)


@app.before_request
def log_request():
    logger.info(f"{request.method} {request.path}")


@app.route("/api/health", methods=["GET"])
def health_check():
    """健康检查"""
    from rag.qdrant_store import get_qdrant_store
    try:
        store = get_qdrant_store()
        qdrant_count = store.count()
        qdrant_status = "ok"
    except Exception as e:
        qdrant_count = 0
        qdrant_status = f"error: {str(e)}"

    return jsonify({
        "status": "ok",
        "service": "StudyQuest",
        "qdrant": qdrant_status,
        "qdrant_points": qdrant_count,
    })


@app.route("/api/studyquest", methods=["POST"])
def studyquest():
    """
    统一 API 入口 — 通过 LangGraph 工作流路由到对应 Agent。

    请求体示例:
    {
        "request_type": "plan",
        "user_id": "user_001",
        "goal_text": "3小时复习数学函数",
        "available_hours": 3.0
    }

    返回:
    {
        "success": true,
        "request_type": "plan",
        "data": { ... },
        "message": "学习关卡规划完成"
    }
    """
    try:
        body = request.get_json(force=True)
        if not body:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        # 解析请求
        sq_request = StudyQuestRequest(**body)
        logger.info(f"收到请求: type={sq_request.request_type}, user={sq_request.user_id}")

        # 转换为 GraphState 并调用 LangGraph
        initial_state = build_state_from_request(sq_request)
        graph = get_graph()
        final_state = graph.invoke(initial_state)

        # 从 final_state 提取响应
        success = final_state.get("error") is None
        response_data = final_state.get("final_response")
        message = final_state.get("response_message", "")

        return jsonify({
            "success": success,
            "request_type": final_state.get("request_type", str(sq_request.request_type.value)),
            "data": response_data,
            "message": message,
            "error": final_state.get("error"),
        }), 200 if success else 500

    except Exception as e:
        logger.error(f"处理请求失败: {str(e)}", exc_info=True)
        # 对路径遍历等安全错误，返回通用消息避免泄漏内部路径
        error_msg = str(e)
        if any(kw in error_msg.lower() for kw in ("path", "file", "directory", "traversal")):
            error_msg = "请求参数无效"
        return jsonify({
            "success": False,
            "request_type": "unknown",
            "error": error_msg,
        }), 400


def init():
    """初始化系统"""
    logger.info("=" * 50)
    logger.info("StudyQuest 学习助手多智能体系统 启动中...")
    logger.info("=" * 50)

    ensure_directories()
    logger.info("目录结构已就绪")

    try:
        ensure_database()
        run_migrations()
        logger.info("MySQL 数据库已就绪")
    except Exception as e:
        logger.warning(f"MySQL 初始化失败（可能没有运行）: {e}")

    try:
        from rag.qdrant_store import get_qdrant_store
        store = get_qdrant_store()
        count = store.count()
        logger.info(f"Qdrant 向量数据库已就绪 (已存储 {count} 条向量)")
    except Exception as e:
        logger.warning(f"Qdrant 初始化失败（可能没有运行 Docker）: {e}")

    # 编译 LangGraph（预热，验证图结构正确）
    try:
        from graph.workflow import get_graph
        get_graph()
        logger.info("LangGraph 工作流已编译")
    except Exception as e:
        logger.error(f"LangGraph 编译失败: {e}")

    logger.info("所有 Agent 模块已加载")
    logger.info(f"Flask API 启动在 http://{FLASK_HOST}:{FLASK_PORT}")


if __name__ == "__main__":
    init()
    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=FLASK_DEBUG,
    )
