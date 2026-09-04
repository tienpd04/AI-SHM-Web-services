import os
import signal
import socket
import sys

from src.config.engine import (ENGINE_SOCKET_ADDRESS, ENGINE_SOCKET_FAMILY,
                               ENGINE_SOCKET_KIND)
from src.config.settings import LOGS_DIR


def _setup_logging():
    import logging
    from logging.handlers import TimedRotatingFileHandler
    log_level = logging.INFO
    logger = logging.getLogger("engine")
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(process)d] [%(levelname)s] %(message)s')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    file_handler = TimedRotatingFileHandler(os.path.join(LOGS_DIR, "engine.log"), when='MIDNIGHT', backupCount=5)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = _setup_logging()


def _signal_handler(signum, frame):
    signame = f"{signum}"
    for sig in signal.Signals:
        if signum == sig:
            signame = sig.name
            break
    logger.info("Handling signal: %s", signame)
    sys.exit(0)


def engine_target(ready_event=None):
    logger.info("Starting Engine Service")
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    server_socket = socket.socket(ENGINE_SOCKET_FAMILY, ENGINE_SOCKET_KIND)
    address = ENGINE_SOCKET_ADDRESS

    if isinstance(address, str) and os.path.exists(address):
        os.remove(address)

    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(address)
    server_socket.listen(128)
    logger.info("Listening at: %s", str(address))

    # NOTE:
    # Use only one worker process for the engine.
    # Do not use multiple engine workers because:
    # - Multiple workers do not make the engine run faster; they can make it slower than a single worker.
    # - The fixed output SHM (Shared Memory) can be overwritten if the client request times out.
    worker_pid = -1

    while True:
        pid = os.fork()
        if pid == 0:
            # Child process
            from engine.worker import start_server_worker
            start_server_worker(server_socket, ready_event=ready_event)
            os._exit(0)
        else:
            # Parent process
            worker_pid = pid
            try:
                child_pid, status = os.waitpid(worker_pid, 0)
                if os.WIFEXITED(status):
                    # Normal exit
                    exit_code = os.WEXITSTATUS(status)
                    if exit_code == 0:
                        logger.info(
                            "Engine worker %d exited with code %d", child_pid, exit_code)
                    else:
                        logger.error(
                            "Engine worker %d exited with code %d", child_pid, exit_code)
                    break
                elif os.WIFSIGNALED(status):
                    # Crashed by signal
                    term_signal = os.WTERMSIG(status)
                    logger.error(
                        "Engine worker %d terminated by signal %d", child_pid, term_signal)
                    # Going to create new worker
                    continue
                else:
                    # Never in this case, but it is ok to handle
                    break
            except (KeyboardInterrupt, SystemExit):
                break
            except Exception:
                # Never in this case, but it is ok to handle
                import traceback
                logger.error(traceback.format_exc())
                break
        break

    try:
        os.kill(worker_pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        os.waitpid(worker_pid, 0)
    except ChildProcessError:
        pass

    logger.info("Shutting down: Master")
    server_socket.close()
    if isinstance(address, str) and os.path.exists(address):
        try:
            os.remove(address)
        except Exception:
            pass


if __name__ == "__main__":
    engine_target()
