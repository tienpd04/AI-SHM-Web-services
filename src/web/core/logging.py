import logging
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

INFO = logging.INFO
DEBUG = logging.DEBUG
WARNING = logging.WARNING
ERROR = logging.ERROR

def setup_logging():
    log_level = INFO
    logger = logging.getLogger("fastapi")
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(process)d] [%(levelname)s] - %(message)s')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    from logging.handlers import TimedRotatingFileHandler

    from src.config.settings import LOGS_DIR, NUM_LOG_BACKUP
    file_handler = TimedRotatingFileHandler(
        os.path.join(LOGS_DIR, "fastapi.log"), when="MIDNIGHT", backupCount=NUM_LOG_BACKUP)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()

del logging
del sys
del os
del setup_logging


def rq_log(request: 'Request', msg: str, level: int = INFO):
    """
    Enhanced logging with request context
    """
    if level < logger.level:
        return

    request_id = getattr(request.state, 'request_id', 'UNKNOWN')

    # Get client info
    client_ip = request.headers.get('X-Forwarded-For') or request.headers.get('X-Real-IP') or request.client.host if request.client else "unknown"
    user_agent = request.headers.get('User-Agent', 'unknown')
    if len(user_agent) > 20:
        user_agent = user_agent[:17] + '...'

    # Build enhanced log message
    log_msg = f"[{request_id}] [{client_ip} {user_agent}] [{request.method} {request.url.path}] - {msg}"

    logger.log(level, log_msg)


def rq_log_info(request: 'Request', msg: str):
    rq_log(request, msg, INFO)


def rq_log_error(request: 'Request', msg: str):
    rq_log(request, msg, ERROR)


def rq_log_warning(request: 'Request', msg: str):
    rq_log(request, msg, WARNING)

def rq_log_debug(request: 'Request', msg: str):
    rq_log(request, msg, DEBUG)


__all__ = [
    "logger",
    "rq_log",
    "rq_log_info",
    "rq_log_error",
    "rq_log_warning",
    "rq_log_debug",
]
