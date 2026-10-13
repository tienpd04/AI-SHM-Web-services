import os
import signal
import socket
import sys

from src.config.constants import ENGINE_LOGGER_NAME
from src.config.engine_server import (ENGINE_SOCKET_ADDRESS,
                                      ENGINE_SOCKET_FAMILY, ENGINE_SOCKET_KIND)
from src.config.settings import DEATHLOCKS_CHECKING, LOGS_DIR, NUM_LOG_BACKUP

# This is master module, just create server and worker
# Do not import the worker module (or any objects from the worker module) as global variables.


def _check_following_import():
    import warnings

    from src import shared
    if not shared._isinitialized:
        warnings.warn(
            f"Main process use child process module '{__name__}' before create the shared module", category=RuntimeWarning)
    elif not shared._manager is None:
        warnings.warn("Engine doesn't need to use resources manager", category=RuntimeWarning)

    del warnings
    del shared


_check_following_import()
del _check_following_import


def _setup_logging():
    import logging
    from logging.handlers import TimedRotatingFileHandler
    log_level = logging.INFO
    logger = logging.getLogger(ENGINE_LOGGER_NAME)
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(process)d] [%(levelname)s] %(message)s')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(log_level)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    file_handler = TimedRotatingFileHandler(os.path.join(
        LOGS_DIR, f"{ENGINE_LOGGER_NAME}.log"), when='MIDNIGHT', backupCount=NUM_LOG_BACKUP)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = None


if DEATHLOCKS_CHECKING:
    import time
    from typing import TYPE_CHECKING, Mapping

    from src.config.settings import DEATHLOCK_CHECKING_TIME
    if TYPE_CHECKING:
        from multiprocessing.synchronize import Lock as LockT

        from src.shared import _SharedFlag

    def _deathlocks_checking(shm_locks: Mapping[str, 'LockT'], flag: '_SharedFlag'):

        # Set the flag to notify web application workers and engine workers not to use shared memory (swith to 'file' mode).
        #   This means they will not use any locks in 'shm_locks'.
        flag.set()
        logger.info(
            "Deathlocks checking start after a engine worker was crashed.")
        for shm_name, lock in shm_locks.items():
            got_lock = lock.acquire(True, timeout=DEATHLOCK_CHECKING_TIME)
            try:
                lock.release()
            except ValueError:
                pass
            else:
                if not got_lock:
                    logger.warning(
                        "A deadlock was detected for SHM '%s'. It was automatically released after the %.2f seconds timeout expired.", shm_name, DEATHLOCK_CHECKING_TIME)

        # Seep a time for other processes check the flag if they acquire a lock failed while deathlocks checking is running
        time.sleep(0.1)
        flag.clear() # Now, the shared memory ('shm' mode) can use again.

        logger.info("Deathlocks checking complete")


def engine_target(ready_event=None):
    global logger
    logger = _setup_logging()
    logger.info("Starting Engine Service")
    server_socket = socket.socket(ENGINE_SOCKET_FAMILY, ENGINE_SOCKET_KIND)
    address = ENGINE_SOCKET_ADDRESS

    if isinstance(address, str) and os.path.exists(address):
        os.remove(address)

    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(address)
    server_socket.listen(128)
    logger.info("Listening at: %s", str(address))

    if DEATHLOCKS_CHECKING:
        thr = None

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

                    if DEATHLOCKS_CHECKING:
                        from src import shared
                        if not shared.is_in_deathlocks_checking():
                            import threading

                            thr = threading.Thread(target=_deathlocks_checking, args=(shared.get_all_shm_locks(), shared.get_deathlock_checking_flag()))
                            thr.start()
                            del threading
                            # Need to sleep a time before create new process after create a thread.
                            time.sleep(1)

                        del shared

                    # Going to create new worker
                    continue

                else:
                    # May be never in this case, but it is ok to handle
                    break
            except (KeyboardInterrupt, SystemExit):
                break
            except Exception:
                # May be never in this case, but it is ok to handle
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

    if DEATHLOCKS_CHECKING and thr is not None:
        thr.join()


if __name__ == "__main__":
    engine_target()
