"""
MySQL 数据库连接与迁移管理
- ensure_database(): 确保数据库存在
- run_migrations(): 通过 Alembic + SQLAlchemy ORM 自动迁移
- get_session(): 上下文管理器，获取数据库会话
"""
import sys
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from config import MYSQL_URL, MYSQL_DATABASE

# ---------------------------------------------------------------------------
# 引擎
# ---------------------------------------------------------------------------
_base_url = MYSQL_URL.rsplit("/", 1)[0]
_base_engine = create_engine(_base_url, pool_pre_ping=True, pool_recycle=3600)

engine = create_engine(
    MYSQL_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ---------------------------------------------------------------------------
# 确保数据库存在
# ---------------------------------------------------------------------------
def ensure_database():
    """确保数据库存在，不存在则创建"""
    with _base_engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        result = conn.execute(
            text("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = :db"),
            {"db": MYSQL_DATABASE}
        )
        if not result.fetchone():
            conn.execute(text(f"CREATE DATABASE `{MYSQL_DATABASE}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            print(f"[DB] Created database: {MYSQL_DATABASE}")
    _base_engine.dispose()


# ---------------------------------------------------------------------------
# Alembic 自动迁移（基于 ORM models）
# ---------------------------------------------------------------------------
def run_migrations():
    """
    基于 SQLAlchemy ORM 模型的 Alembic 自动迁移。

    处理三种场景：
    1. 新数据库：alembic_version 表不存在 → 执行完整初始迁移
    2. 存量数据库（由旧 ensure_tables 创建）→ 自动 stamp head 并跳过
    3. 已受 Alembic 管理 → upgrade head（仅执行新迁移）
    """
    _agent_dir = Path(__file__).resolve().parent.parent
    _alembic_dir = _agent_dir / "alembic"
    _alembic_ini = _agent_dir / "alembic.ini"

    if str(_agent_dir) not in sys.path:
        sys.path.insert(0, str(_agent_dir))

    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config(str(_alembic_ini))
    alembic_cfg.set_main_option("script_location", str(_alembic_dir))

    # ---------- 注入 ORM 模型的 target_metadata ----------
    from database.models import Base
    from alembic.runtime.migration import MigrationContext
    from alembic.autogenerate import produce_migrations, render_python_code

    with engine.connect() as conn:
        # 检测 alembic_version 表是否存在
        has_alembic = conn.execute(text(
            "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 'alembic_version'"
        ), {"db": MYSQL_DATABASE}).fetchone()

        if not has_alembic:
            has_users = conn.execute(text(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = 'users'"
            ), {"db": MYSQL_DATABASE}).fetchone()

            if has_users:
                print("[DB] 检测到存量数据库，标记初始迁移为已执行...")
                command.stamp(alembic_cfg, "head")
                print("[DB] Stamp 完成，后续将通过 Alembic 管理迁移")
            else:
                print("[DB] 全新数据库，执行迁移...")
                command.upgrade(alembic_cfg, "head")
                print("[DB] 迁移完成")
        else:
            current = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            print(f"[DB] 当前迁移版本: {current[0]}")
            command.upgrade(alembic_cfg, "head")
            print("[DB] 迁移完成（已是最新）")


# ---------------------------------------------------------------------------
# 数据库会话
# ---------------------------------------------------------------------------
@contextmanager
def get_session() -> Session:
    """获取数据库会话（上下文管理器，异常回滚，成功提交）"""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    else:
        session.commit()
    finally:
        session.close()
