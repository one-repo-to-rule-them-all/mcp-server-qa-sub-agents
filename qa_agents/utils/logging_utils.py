"""Central logging configuration using Loguru JSON sinks."""

from __future__ import annotations

import logging
import sys

from loguru import logger


def configure_json_logging(level: str = "INFO") -> None:
    """Route stdlib logging and Loguru through JSON-formatted stderr sink."""
    logger.remove()
    logger.add(sys.stderr, level=level.upper(), serialize=True, enqueue=False, backtrace=False, diagnose=False)

    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            logger.bind(logger_name=record.name).log(record.levelname, record.getMessage())

    logging.basicConfig(handlers=[InterceptHandler()], level=getattr(logging, level.upper(), logging.INFO), force=True)

