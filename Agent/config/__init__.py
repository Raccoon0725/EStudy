"""
StudyQuest 全局配置模块
加载环境变量，提供统一配置入口
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# ============================================================
# LLM 配置
# LLM_PROVIDER: "anthropic" (原生 Anthropic SDK) 或 "openai" (OpenAI 兼容端点，如 DeepSeek)
# ============================================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

# Embedding 专用配置（独立于 OCR/Chat，可走不同端点）
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", OPENAI_API_KEY)
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", OPENAI_BASE_URL)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "Doubao-Seed-2.0-pro")

# ============================================================
# Tavily 搜索配置
# ============================================================
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ============================================================
# Qdrant 向量数据库配置
# ============================================================
QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "studyquest_knowledge")

# ============================================================
# MySQL 数据库配置
# ============================================================
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "studyquest")

MYSQL_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    f"?charset=utf8mb4"
)

# ============================================================
# Flask 配置
# ============================================================
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# ============================================================
# 文件存储路径
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", PROJECT_ROOT / "workspace" / "uploads"))
TASK_DIR = Path(os.getenv("TASK_DIR", PROJECT_ROOT / "workspace" / ".agent" / "tasks"))

# ============================================================
# RAG 配置
# ============================================================
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.65"))

# ============================================================
# 文件上传安全配置
# ============================================================
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".pdf", ".docx", ".doc", ".pptx", ".ppt",
    ".txt", ".md", ".markdown",
}
MAX_FILENAME_LENGTH = 255

# ============================================================
# 学习规则配置
# ============================================================
TASK_MIN_MINUTES = int(os.getenv("TASK_MIN_MINUTES", "20"))
TASK_MAX_MINUTES = int(os.getenv("TASK_MAX_MINUTES", "50"))
SAME_SUBJECT_MAX_MINUTES = int(os.getenv("SAME_SUBJECT_MAX_MINUTES", "90"))
BREAK_MINUTES = int(os.getenv("BREAK_MINUTES", "10"))
WEAK_POINT_DAYS = int(os.getenv("WEAK_POINT_DAYS", "7"))
WEAK_POINT_TOP_N = int(os.getenv("WEAK_POINT_TOP_N", "3"))


def ensure_directories():
    """确保必要的目录存在"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TASK_DIR.mkdir(parents=True, exist_ok=True)


def get_llm():
    """获取 LLM 实例（支持 Anthropic 原生和 OpenAI 兼容模式）"""
    if LLM_PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        kwargs = dict(
            model=ANTHROPIC_MODEL,
            api_key=ANTHROPIC_API_KEY,
            temperature=0.3,
            max_tokens=4096,
        )
        if ANTHROPIC_BASE_URL:
            kwargs["base_url"] = ANTHROPIC_BASE_URL
        return ChatOpenAI(**kwargs)
    else:
        from langchain_anthropic import ChatAnthropic
        kwargs = dict(
            model=ANTHROPIC_MODEL,
            api_key=ANTHROPIC_API_KEY,
            temperature=0.3,
            max_tokens=4096,
        )
        if ANTHROPIC_BASE_URL:
            kwargs["base_url"] = ANTHROPIC_BASE_URL
        return ChatAnthropic(**kwargs)


def get_embeddings():
    """获取 OpenAI Embeddings 实例（走独立的 Embedding 配置）"""
    from langchain_openai import OpenAIEmbeddings
    kwargs = dict(
        model=EMBEDDING_MODEL,
        api_key=EMBEDDING_API_KEY,
    )
    if EMBEDDING_BASE_URL:
        kwargs["base_url"] = EMBEDDING_BASE_URL
    return OpenAIEmbeddings(**kwargs)
