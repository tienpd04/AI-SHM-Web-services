
import os
from multiprocessing.shared_memory import SharedMemory

from src.config.settings import DEATHLOCKS_CHECKING
from src.shared import current_using_shms, worker_get_shm_names_set
from src.web.core.logging import logger

_shms: tuple[SharedMemory, ...] = ()

_skip_first_time = False

_dl_checking_event = None

if DEATHLOCKS_CHECKING:
    from src.config.settings import DEATHLOCK_CHECKING_TIME
    from src.shared import get_shm_lock

    # _dl_chk_thread = None

    def _deathlocks_checking(shm_names: list[str]):
        logger.info("Deathlocks checking start after reuse shared memory from a teminated worker process")
        _dl_checking_event.set()

        for shm_name in shm_names:
            lock = get_shm_lock(shm_name)
            got_lock = lock.acquire(True, timeout=DEATHLOCK_CHECKING_TIME)
            try:
                lock.release()
            except ValueError:
                pass
            else:
                if not got_lock:
                    logger.warning(
                        "A deadlock was detected for SHM '%s'. It was automatically released after the %.2f seconds timeout expired.", shm_name, DEATHLOCK_CHECKING_TIME)

        _dl_checking_event.clear()
        logger.info("Deathlocks checking complete")

    def _background_deathlocks_checking(shm_names: list[str]):
        from threading import Event, Thread
        global _dl_checking_event
        if _dl_checking_event is None:
            _dl_checking_event = Event()

        _dl_checking_event.set()
        t = Thread(target=_deathlocks_checking, args=(shm_names,))
        t.start()


def _take_resources() -> bool:
    global _shms
    if _shms:
        # taken
        return True
    try:
        ret = worker_get_shm_names_set()
        if ret is None:
            current_using = current_using_shms()
            logger.error(
                "Failed to take resources for worker PID [%d], current using resources: %s", os.getpid(), current_using)
            return False
        names, is_new = ret
        assert len(names) > 0, "Required atleast one SHM"
        shms = [SharedMemory(name) for name in names]
        _shms = tuple(shms)
        if not is_new:
            global _skip_first_time
            _skip_first_time = True
            if DEATHLOCKS_CHECKING:
                # Called only once time
                _background_deathlocks_checking(names)

    except Exception as e:
        logger.error("Failed to take resources: %s", str(e))
        return False

    logger.info("Taken resources for worker PID [%d]: %s",
                os.getpid(), _shms)
    return True


def get_shms() -> tuple[SharedMemory, ...]:
    """For use only by the engine service
    Do not use this for other service. The Shared Memory can be overwritten.
    Do not use this in multi-threading. The Shared Memory can be overwritten.
    """
    global _skip_first_time
    if not _shms:
        _take_resources()

    if _skip_first_time:
        _skip_first_time = False
        # Notify the engine using 'file' mode at this time because the set of SHMs is taken from a terminated worker process
        return ()

    if _dl_checking_event is not None and _dl_checking_event.is_set():
        # Notify the engine using 'file' mode while deatlocks checking is still running, it means the engine does not using any lock.
        return ()

    return _shms


__all__ = [
    "get_shms"
]
