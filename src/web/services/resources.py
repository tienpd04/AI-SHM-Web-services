
import os
from multiprocessing.shared_memory import SharedMemory

from src.shared import current_using_shms, worker_get_shm_name_set
from src.web.core.logging import logger

_shms: tuple[SharedMemory, ...] = ()

_skip_first_time = False


def _get_rs_api_key():
    """Runtime get resources api key. Warning only once.
    """
    global _rs_api_key
    if isinstance(_rs_api_key, int):
        # type change to str or None
        _rs_api_key = os.getenv("RESOURCES_API_KEY")
        if not _rs_api_key:
            logger.warning("Enviroment 'RESOURCES_API_KEY' is not set up.")
    return _rs_api_key


def _take_resources() -> bool:
    global _shms
    if _shms:
        # taken
        return True
    try:
        ret = worker_get_shm_name_set()
        if ret is None:
            current_using = current_using_shms()
            logger.error("Failed to take resources, current using resources: %s", current_using)

            return False
        names, is_new = ret
        shms = [SharedMemory(name) for name in names]
        _shms = tuple(shms)
        if not is_new:
            global _skip_first_time
            _skip_first_time = True

    except Exception as e:
        logger.error("Failed to take resources: %s", str(e))
        return False

    logger.info("Taken resources for worker PID %d: %s",
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
        return ()

    return _shms




__all__ = [
    "get_shms"
]
