"""
MySQL 数据库连接与表结构管理
"""
from contextlib import contextmanager
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker, Session
from config import MYSQL_URL, MYSQL_DATABASE

# 创建引擎（不含数据库名，用于建库）
_base_url = MYSQL_URL.rsplit("/", 1)[0]
_base_engine = create_engine(_base_url, pool_pre_ping=True, pool_recycle=3600)

# 数据库引擎（含数据库名）
engine = create_engine(
    MYSQL_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def ensure_database():
    """确保数据库存在，不存在则创建"""
    with _base_engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        result = conn.execute(
            text(f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = :db"),
            {"db": MYSQL_DATABASE}
        )
        if not result.fetchone():
            conn.execute(text(f"CREATE DATABASE `{MYSQL_DATABASE}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            print(f"[DB] Created database: {MYSQL_DATABASE}")
    _base_engine.dispose()


@contextmanager
def get_session() -> Session:
    """获取数据库会话（上下文管理器）"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_tables():
    """确保所有表存在，不存在则创建"""
    with get_session() as sess:
        # 检查是否需要建表
        insp = inspect(engine)
        existing = insp.get_table_names()

        needed = ["users", "sessions", "tasks", "qa_logs", "materials", "material_chunks", "reports"]
        missing = [t for t in needed if t not in existing]

        if not missing:
            return

        # 逐个创建缺失的表
        if "users" in missing:
            sess.execute(text("""
                CREATE TABLE users (
                    id VARCHAR(64) PRIMARY KEY,
                    username VARCHAR(128) NOT NULL,
                    password_hash VARCHAR(256) NOT NULL,
                    avatar VARCHAR(512) DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_username (username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))

        if "sessions" in missing:
            sess.execute(text("""
                CREATE TABLE sessions (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    goal_text TEXT,
                    date DATE NOT NULL,
                    total_minutes INT DEFAULT 0,
                    status ENUM('active','completed','cancelled') DEFAULT 'active',
                    planner_json LONGTEXT COMMENT 'Planner输出的完整关卡JSON',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_user_date (user_id, date),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))

        if "tasks" in missing:
            sess.execute(text("""
                CREATE TABLE tasks (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    session_id VARCHAR(64),
                    parent_id VARCHAR(64) DEFAULT NULL,
                    subject VARCHAR(128) NOT NULL,
                    title VARCHAR(256) NOT NULL,
                    description TEXT,
                    task_type ENUM('understand','practice','memorize','correct','review','break') DEFAULT 'understand',
                    estimated_minutes INT DEFAULT 30,
                    actual_minutes INT DEFAULT 0,
                    status ENUM('pending','in_progress','completed','cancelled') DEFAULT 'pending',
                    priority INT DEFAULT 1,
                    sort_order INT DEFAULT 0,
                    material_ids JSON,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME DEFAULT NULL,
                    INDEX idx_user (user_id),
                    INDEX idx_session (session_id),
                    INDEX idx_status (user_id, status),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))

        if "qa_logs" in missing:
            sess.execute(text("""
                CREATE TABLE qa_logs (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    task_id VARCHAR(64) DEFAULT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    answer_mode ENUM('hint','explain','review') DEFAULT 'explain',
                    source_docs JSON COMMENT '引用的资料来源列表',
                    confidence VARCHAR(16) DEFAULT 'medium',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user (user_id),
                    INDEX idx_task (task_id),
                    INDEX idx_created (created_at),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))

        if "materials" in missing:
            sess.execute(text("""
                CREATE TABLE materials (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    filename VARCHAR(512) NOT NULL,
                    file_type VARCHAR(32) NOT NULL,
                    file_path VARCHAR(1024) NOT NULL,
                    subject VARCHAR(128) DEFAULT '',
                    chapter VARCHAR(256) DEFAULT '',
                    knowledge_point VARCHAR(256) DEFAULT '',
                    ocr_text LONGTEXT,
                    chunk_count INT DEFAULT 0,
                    qdrant_indexed TINYINT(1) DEFAULT 0,
                    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user (user_id),
                    INDEX idx_subject (user_id, subject),
                    INDEX idx_knowledge (user_id, knowledge_point),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))

        if "material_chunks" in missing:
            sess.execute(text("""
                CREATE TABLE material_chunks (
                    id VARCHAR(64) PRIMARY KEY,
                    material_id VARCHAR(64) NOT NULL,
                    chunk_index INT NOT NULL,
                    content TEXT NOT NULL,
                    qdrant_point_id VARCHAR(128) DEFAULT '',
                    embedding_model VARCHAR(64) DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_material (material_id),
                    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))

        if "reports" in missing:
            sess.execute(text("""
                CREATE TABLE reports (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    session_id VARCHAR(64),
                    task_id VARCHAR(64),
                    completion JSON COMMENT '完成情况',
                    weak_points JSON COMMENT '薄弱点列表',
                    recommended_material_ids JSON,
                    next_tasks_suggestion TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user (user_id),
                    INDEX idx_session (session_id),
                    INDEX idx_task (task_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))

        sess.commit()
        print(f"[DB] Created tables: {missing}")
