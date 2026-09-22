



def _setup_logging():
    import logging
    import os
    import sys
    from logging.handlers import TimedRotatingFileHandler
    log_level = logging.INFO
    logger = logging.getLogger("resources")
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(process)d] [%(levelname)s] %(message)s')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    from src.config.settings import LOGS_DIR, NUM_LOG_BACKUP
    file_handler = TimedRotatingFileHandler(os.path.join(LOGS_DIR, "resources.log"), when='MIDNIGHT', backupCount=NUM_LOG_BACKUP)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


logger = _setup_logging()

del _setup_logging

__all__ = [
    "logger",
]