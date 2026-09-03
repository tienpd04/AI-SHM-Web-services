
import os
import time
from collections import deque
from datetime import datetime as Datetime

import psutil

from .logger import logger


class ResourcesException(Exception):
    pass


class InvalidApiKey(ResourcesException):
    pass


class InvalidWorkerPID(ResourcesException):
    pass


_rs_api_key = 0


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


def is_pid_running(pid):
    return psutil.pid_exists(pid)


class ResourcesManager:
    """Manage fixed resources created by the main process.

        - Allocate resources to web workers.
        - Check for and reclaim resources from terminated web workers to reallocate them to new web workers.
    """
    _resources: tuple[tuple[str, str]]
    _taken_at: dict[int, Datetime]

    _in_use: dict[int, tuple[str, str]]

    _num_workers: int

    _replaced_pids: deque[tuple[int, float]]

    def __init__(self, resources: list[tuple[str, str]], num_workers: int, replaced_pids_maxlen: int = 256):

        if not isinstance(resources, (list, tuple)):
            raise ValueError("'resources' must be a list or tuple")

        if not isinstance(num_workers, int) or num_workers < 1:
            raise ValueError("'num_workers' must be possitive integer")

        assert len(
            resources) >= num_workers, f"Number of resouces must be >= num_workers: number of resources {len(resources)}, num_workers {num_workers}"

        all_names = []
        for rs_set in resources:
            if not isinstance(rs_set, (tuple, list)):
                raise ValueError("'resources' element must be tuple or list")
            if len(rs_set) != 2:
                raise ValueError(
                    "'resources' element must have length = 2 (input and output)")
            for rs in rs_set:
                if not isinstance(rs, str):
                    raise ValueError(f"'resources' name must be a str: '{rs}'")
                all_names.append(rs)

        if len(set(all_names)) != len(all_names):
            raise ValueError(f"'resources' name must be uniquie")

        # Make the constant
        self._resources = tuple([tuple(x) for x in resources])
        self._taken_at = {}
        self._in_use = {}

        self._num_workers = num_workers

        self._replaced_pids = deque(maxlen=replaced_pids_maxlen)

        logger.info("Resoucer Manager created with resources: %s, num_workers: %d", sorted(
            resources), num_workers)

    def take_forever(self, api_key: str, worker_pid: int) -> tuple[str, str] | None:
        RESOURCES_API_KEY = _get_rs_api_key()
        if RESOURCES_API_KEY and api_key != RESOURCES_API_KEY:
            raise InvalidApiKey()

        if not isinstance(worker_pid, int):
            raise TypeError("'worker_pid' must be integer")

        if not is_pid_running(worker_pid):
            raise InvalidWorkerPID(
                f"Worker with pid {worker_pid} is not runing")

        if worker_pid in self._in_use:
            logger.warning("Worker PID %d take resources too many time")
            self._taken_at[worker_pid] = Datetime.now()
            return self._in_use[worker_pid]

        all_in_use: set[tuple[str, str]] = set(self._in_use.values())

        available = set(self._resources) - all_in_use

        if available:
            ret = available.pop()
            self._in_use[worker_pid] = ret
            self._taken_at[worker_pid] = Datetime.now()
            return ret

        else:
            # Check for and reclaim resources from terminated web workers to reallocate them
            replace_pid = None
            for pid in self._in_use:
                if not is_pid_running(pid):
                    replace_pid = pid
                    break
            if replace_pid is not None:
                ret = self._in_use.pop(replace_pid)
                logger.warning(
                    "Taked resouces for worker PID %d from died worker PID %d, resources: %s", worker_pid, replace_pid, ret)
                self._in_use[worker_pid] = ret
                self._taken_at[worker_pid] = Datetime.now()
                self._replaced_pids.append((replace_pid, time.time()))

                return ret
            logger.warning(
                "No resources available for worker PID: %d", worker_pid)
            return None

    def get_last_replaced_pids(self):
        return list(self._replaced_pids)
