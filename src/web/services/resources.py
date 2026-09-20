
import os
from multiprocessing.shared_memory import SharedMemory

from src.config.resources import (RESOURCES_SOCKET_ADDRESS,
                                  RESOURCES_SOCKET_FAMILY,
                                  RESOURCES_SOCKET_KIND, ResourcesSocketAPI)
from src.libs.socket_protocol.client import StatusCodeError, request
from src.web.core.logging import logger

_rs_api_key = 0
_input_output_shms: tuple[SharedMemory, SharedMemory] = ()


def _module_get_rs_api_key():
    """First get api key for this module and warning if miss.
    """
    global _rs_api_key
    api_key = os.getenv("RESOURCES_API_KEY")
    if api_key:
        # type change to str or None
        _rs_api_key = api_key
    else:
        logger.warning(
            f"Enviroment 'RESOURCES_API_KEY' is not set up or set up it after import module {__name__}.")


_module_get_rs_api_key()

del _module_get_rs_api_key


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
    global _input_output_shms
    if _input_output_shms:
        # taken
        return True
    pid = os.getpid()
    data = {'api_key': _get_rs_api_key(), 'worker_pid': pid}
    try:
        res = request(RESOURCES_SOCKET_ADDRESS, ResourcesSocketAPI.TAKE_RESOURCES, data=data,
                      address_family=RESOURCES_SOCKET_FAMILY, socket_kind=RESOURCES_SOCKET_KIND, timeout=30)
        res.raise_for_status()
        names = res.json()
        assert isinstance(
            names, list), f"Required response as a list, not {type(names)}"
        assert all([isinstance(x, str) for x in names]
                   ), f"Required each element in list is str: {names}"
        assert len(
            names) == 2, f"Required exact 2 resources, actual return: {names}"
        assert len(
            set(names)) == 2, f"Resources name must be unique, actual return: {names}"
        input_shm = SharedMemory(names[0])
        output_shm = SharedMemory(names[1])
        _input_output_shms = (input_shm, output_shm)

    except StatusCodeError:
        try:
            msg = res.text
        except Exception:
            msg = ''
        logger.error("Failed to take resources status code = %d: %s",
                     res.status_code, msg)
        return False
    except Exception as e:
        logger.error("Failed to take resources: %s", str(e))
        return False

    logger.info("Taken resources for worker PID %d: %s",
                pid, _input_output_shms)
    return True


def get_input_output_shms() -> tuple[SharedMemory, SharedMemory] | tuple[None, None]:
    """For use only by the engine service
    Do not use this for other service. The Shared Memory can be overwritten.
    Do not use this in multi-threading. The Shared Memory can be overwritten.
    """
    if not _input_output_shms:
        _take_resources()
    return _input_output_shms or (None, None)


def rs_health_check(timeout=10, raise_exp=True):
    try:
        res = request(RESOURCES_SOCKET_ADDRESS, ResourcesSocketAPI.HEALTH_CHECK,
                      address_family=RESOURCES_SOCKET_FAMILY, socket_kind=RESOURCES_SOCKET_KIND, timeout=timeout)
        res.raise_for_status()
    except Exception:
        if raise_exp:
            raise
        return False

    return True


__all__ = [
    "rs_health_check",
    "get_input_output_shms"
]
