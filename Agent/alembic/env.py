"""
Alembic 迁移环境配置（SQLAlchemy ORM）
从 Agent/config 读取数据库连接，基于 ORM 模型元数据自动生成/执行迁移
"""
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# 1. 把 Agent/ 目录加入 sys.path，以便导入 config + models
# ---------------------------------------------------------------------------
_agent_dir = Path(__file__).resolve().parent.parent
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

from config import MYSQL_URL
from database.models import Base

# ---------------------------------------------------------------------------
# 2. Alembic Config 对象（读取 alembic.ini）
# ---------------------------------------------------------------------------
config = context.config
config.set_main_option("sqlalchemy.url", MYSQL_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# 3. 使用 ORM 模型元数据 —— 支持 --autogenerate
# ---------------------------------------------------------------------------
target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# 4. 离线模式（生成 SQL 脚本）
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# 5. 在线模式（连接数据库执行 DDL）
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# 6. 入口
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
