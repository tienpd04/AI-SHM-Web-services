from __future__ import annotations

import os
from multiprocessing import Lock, Semaphore
from multiprocessing.shared_memory import SharedMemory
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from multiprocessing.synchronize import Lock as LockT


class _ShmManager(object):
    __slots__ = ('_shm', '_lock', '_name_tuples')

    def __init__(self, shm_name_tuples: list[tuple[str, ...]]):
        # Make constants
        self._name_tuples = tuple([tuple(x) for x in shm_name_tuples])
        self._lock = Lock()
        size = 4 * len(shm_name_tuples)
        self._shm = SharedMemory(create=True, size=size)
        self._shm.buf[:] = b'\xff' * size

    def get_shm_set(self) -> tuple[tuple[str, ...], bool] | None:

        pid = os.getpid()
        with self._lock:
            for i, names in enumerate(self._name_tuples):
                # Avaiable
                if self._shm.buf[i * 4: (i+1)*4] == b'\xff\xff\xff\xff':
                    self._shm.buf[i * 4: (i+1)*4] = pid.to_bytes(4, 'little')
                    return names, True

            for i, names in enumerate(self._name_tuples):
                # Reuse from termiated processs
                check_pid = int.from_bytes(self._shm.buf[i * 4: (i+1)*4], 'little')
                if not psutil.pid_exists(check_pid):
                    self._shm.buf[i * 4: (i+1)*4] = pid.to_bytes(4, 'little')
                    return names, False

        return None

    def status(self) -> dict[int, tuple[str, ...]]:

        ret = {}
        with self._lock:
            for i, names in enumerate(self._name_tuples):
                if self._shm.buf[i * 4: (i+1)*4] != b'\xff\xff\xff\xff':
                    pid = int.from_bytes(self._shm.buf[i * 4: (i+1)*4], 'little')
                    ret[pid] = names

        return ret

    def terminate(self):
        self._shm.close()
        self._shm.unlink()


class _OverwriteCounter(object):
    __slots__ = ('_cnt',)

    def __init__(self):
        self._cnt = Semaphore(0)

    def increase(self):
        try:
            self._cnt.release()
        except ValueError:
            pass

    def clear(self):
        while self._cnt.acquire(False):
            continue

    def get_value(self):
        return self._cnt.get_value()


_isinitialized = False

_manager = None

_shm_locks: dict[str, LockT] = {}

overwrite_counter = _OverwriteCounter()


def initialize(name_tuples: list[tuple[str, ...]]):
    """For use only by the main process
    """
    global _isinitialized, _manager
    assert _isinitialized is False, f"{__name__}.initialize called too many times"

    shm_names = []
    for tup in name_tuples:
        shm_names.extend(tup)

    assert all([isinstance(x, str) for x in shm_names]), 'SHM name must be str'

    assert len(set(shm_names)) == len(shm_names), 'SHM name must be uniquie'

    for name in shm_names:
        if not isinstance(name, str):
            raise ValueError("Each element of 'shm_names' must be a str")

    for name in shm_names:
        _shm_locks[name] = Lock()

    _manager = _ShmManager(name_tuples)

    _isinitialized = True

def terminate():
    """For use only by the main process
        """
    _manager.terminate()


def worker_get_shm_name_set() -> tuple[tuple[str, ...], bool] | None:
    return _manager.get_shm_set()

def current_using_shms():
    return _manager.status()

def get_shm_lock(name: str) -> LockT:
    return _shm_locks[name]


__all__ = [
    "initialize",
    "terminate",
    'get_shm_lock',
    'overwrite_counter',
    'worker_get_shm_name_set',
    'current_using_shms'
]
