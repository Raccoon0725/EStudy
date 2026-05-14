"""
日志配置
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = "StudyQuest", log_dir: str = None) -> logging.Logger:
    """设置结构化日志"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # 控制台 handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))
    logger.addHandler(console)

    # 文件 handler（如果指定了目录）
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            log_path / f"studyquest_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","message":"%(message)s"}',
            datefmt='%Y-%m-%dT%H:%M:%S',
        ))
        logger.addHandler(file_handler)

    return logger


logger = setup_logger()
