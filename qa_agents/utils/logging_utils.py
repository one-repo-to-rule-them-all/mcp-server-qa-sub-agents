"""Central logging configuration using Loguru JSON sinks."""

from __future__ import annotations

import logging
import sys


def configure_json_logging(level: str = "INFO") -> None:
    """Route stdlib logging and (if available) Loguru through JSON-ish stderr sink."""
    try:
        from loguru import logger as loguru_logger  # imported lazily for optional dependency fallback

        loguru_logger.remove()
        loguru_logger.add(
            sys.stderr,
            level=level.upper(),
            serialize=True,
            enqueue=False,
            backtrace=False,
            diagnose=False,
        )

        class InterceptHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                loguru_logger.bind(logger_name=record.name).log(record.levelname, record.getMessage())

        logging.basicConfig(
            handlers=[InterceptHandler()],
            level=getattr(logging, level.upper(), logging.INFO),
            force=True,
        )
        return
    except ModuleNotFoundError:
        pass

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='{"time":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
        stream=sys.stderr,
        force=True,
    )
