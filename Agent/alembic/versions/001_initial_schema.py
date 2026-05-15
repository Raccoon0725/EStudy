"""初始迁移 —— 创建 StudyQuest 全部 7 张表

Revision ID: 001_initial
Revises:
Create Date: 2026-05-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 所有表使用 IF NOT EXISTS，兼容存量数据库
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(64) PRIMARY KEY,
            username VARCHAR(128) NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            avatar VARCHAR(512) DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
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
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
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
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS qa_logs (
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
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS materials (
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
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS material_chunks (
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
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS reports (
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
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reports")
    op.execute("DROP TABLE IF EXISTS material_chunks")
    op.execute("DROP TABLE IF EXISTS materials")
    op.execute("DROP TABLE IF EXISTS qa_logs")
    op.execute("DROP TABLE IF EXISTS tasks")
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS users")
