"""
结构化日志模块：统一配置，供后端所有模块使用。
输出到控制台和 logs/evolvelab.log，支持自动轮转（10MB/文件，保留 5 个备份）。
"""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志轮转：单文件最大 10MB，保留 5 个历史备份
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

_FORMAT = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    """获取统一配置的 logger（控制台 + 自动轮转文件）。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(LOG_LEVEL)
        # 控制台
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(_FORMAT)
        logger.addHandler(sh)
        # 文件（自动轮转：10MB/文件，保留 5 个备份）
        fh = RotatingFileHandler(
            LOG_DIR / "evolvelab.log",
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        fh.setFormatter(_FORMAT)
        logger.addHandler(fh)
        logger.propagate = False
    return logger
