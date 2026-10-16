"""Logging configuration for AI Evaluation Platform."""

import logging
import sys
from typing import Optional


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure standardized application-wide logging format."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    logger = logging.getLogger("ai_evaluation_platform")
    logger.setLevel(level)
    return logger


logger = setup_logging()
