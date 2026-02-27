"""
utils/logger.py — Centralized logging setup.
Writes to console and a rotating log file so free-tier hosts
don't run out of disk space.
"""

import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(name: str) -> logging.Logger:
    from config import Config  # imported here to avoid circular imports

    logger = logging.getLogger(name)

    if logger.handlers:          # already configured (e.g. re-imported module)
        return logger

    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console handler ───────────────────────────────────────────
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # ── Rotating file handler (5 MB × 3 backups) ─────────────────
    try:
        fh = RotatingFileHandler(
            Config.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass  # read-only filesystem on some free hosts — skip file logging

    return logger
