"""
Centralised logging bootstrap so that every module shares structured logs.
"""

from __future__ import annotations

import logging
import sys


def init_logger(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("study_companion")
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = init_logger()
