import os
import signal
import socket
import sys

from src.config.engine import (ENGINE_SOCKET_ADDRESS, ENGINE_SOCKET_FAMILY,
                               ENGINE_SOCKET_KIND)
from src.config.settings import DEATHLOCKS_CHECKING, LOGS_DIR, NUM_LOG_BACKUP

if DEATHLOCKS_CHECKING:
    from threading import Event, Thread

    # done = Event()


    def _deathlocks_checking(stop_event: Event, check_event: Event, cancel_event: Event, task_done: Event):
        import time

        from src.config.settings import DEATHLOCK_CHECKING_TIME
        from src.shared import deathlocks_checking_event, get_all_shm_locks
        shm_locks = get_all_shm_locks()
        while 1:
            while not check_event.is_set():
                check_event.wait()

            if stop_event.is_set():
                break
            logger.info("Deathlocks checking start")
            deathlocks_checking_event.set()
            for shm_name, lock in shm_locks.items():
                got_lock = lock.acquire(True, timeout=DEATHLOCK_CHECKING_TIME)
                try:
                    lock.release()
                except ValueError:
                    # Other service ('web application worker') also checking the death lock. It's may be released before.
                    pass
                else:
                    if not got_lock:
                        logger.warning(
                            "A deadlock was detected for SHM '%s'. It was automatically released after the %.2f seconds timeout expired.", shm_name, DEATHLOCK_CHECKING_TIME)
            if not cancel_event.is_set():
                deathlocks_checking_event.clear()
            logger.info("Deathlocks checking done")
            check_event.clear()
            task_done.set()




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


logger = _setup_logging()



def engine_target(ready_event=None):
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
        from src.shared import deathlocks_checking_event
        check_event = Event()
        cancel_event = Event()
        task_done = Event()
        stop_event = Event()
        thr = Thread(target=_deathlocks_checking, args=(stop_event, check_event, cancel_event, task_done))
        thr.start()
        import time
        time.sleep(0.1)

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
                        deathlocks_checking_event.set()
                        if not check_event.is_set():
                            check_event.set()
                        else:
                            cancel_event.set()
                            task_done.wait()
                            cancel_event.clear()
                            task_done.clear()
                            check_event.set()
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

    if DEATHLOCKS_CHECKING:
        logger.info("Closing deathlocks checking...")
        if check_event.is_set():
            task_done.wait()
        stop_event.set()
        check_event.set()
        thr.join()
        logger.info("Deathlocks checking closed.")


if __name__ == "__main__":
    engine_target()
