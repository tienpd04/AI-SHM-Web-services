import os
import signal
import socket
import sys

from src.config.engine import (ENGINE_SOCKET_ADDRESS, ENGINE_SOCKET_FAMILY,
                               ENGINE_SOCKET_KIND)
from src.config.settings import DEATHLOCKS_CHECKING, LOGS_DIR, NUM_LOG_BACKUP

# This is master module, just create server and worker
# Do not import the worker module (or any objects from the worker module) as global variables.



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

    file_handler = TimedRotatingFileHandler(os.path.join(
        LOGS_DIR, "engine.log"), when='MIDNIGHT', backupCount=NUM_LOG_BACKUP)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = None


if DEATHLOCKS_CHECKING:
    import time
    from typing import TYPE_CHECKING, cast

    from src.config.settings import DEATHLOCK_CHECKING_TIME
    if TYPE_CHECKING:
        from multiprocessing.synchronize import Lock as LockT
        from threading import Event

        from src.shared import _SharedFlag



    def _deathlocks_checking(cancel_event: 'Event', shm_locks: dict[str, 'LockT'], flag: '_SharedFlag'):

        flag.set()
        logger.info("Deathlocks checking start")

        for shm_name, lock in shm_locks.items():

            remaining_time = DEATHLOCK_CHECKING_TIME
            while remaining_time > 0:
                # Doesn't need to be perfectly precise;
                if lock.acquire(True, timeout=1):
                    try:
                        lock.release()
                    except ValueError:
                        pass
                    break

                if cancel_event.is_set():
                    break

                remaining_time -= 1

            if remaining_time <= 0:
                # timeout
                try:
                    lock.release()
                except ValueError:
                    pass
                else:
                    logger.warning(
                            "A deadlock was detected for SHM '%s'. It was automatically released after the %.2f seconds timeout expired.", shm_name, DEATHLOCK_CHECKING_TIME)

            if cancel_event.is_set():
                break


        # Sleep enough time for execute 'src.shared.is_in_deathlocks_checking' function that called by web application worker or engine worker after they aquired a lock failed
        time.sleep(0.1)
        if not cancel_event.is_set():
            flag.clear()
            logger.info("Deathlocks checking done")
        else:
            logger.info("Deathlocks checking cancelled")


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
        cancel_event: Event = None
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
                        import threading

                        from src import shared
                        if thr is not None:
                            cast(threading.Event, cancel_event).set()
                            cast(threading.Thread, thr).join()
                            cast(threading.Event, cancel_event).clear()

                        else:
                            cancel_event = threading.Event()

                        thr = threading.Thread(target=_deathlocks_checking, args=(cancel_event, shared.get_all_shm_locks(), shared.get_deathlock_checking_flag()))
                        thr.start()
                        del threading, shared
                        # Need to sleep a time before create new process after create a thread.
                        time.sleep(1)


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
        cancel_event.set()
        thr.join()


if __name__ == "__main__":
    engine_target()
