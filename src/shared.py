from __future__ import annotations

from multiprocessing import Event, Lock, Semaphore
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiprocessing.synchronize import Lock as LockT


class _OverwrittenCounter(object):
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


_inited = False

_shm_locks: dict[str, LockT] = {}

overwrite_counter = _OverwrittenCounter()


def initialize(shm_names: set[str]):
    """For use only by the main process
    """
    global _inited
    assert _inited is False, f"{__name__}.initialize called too many times"
    if not isinstance(shm_names, (set, frozenset)):
        raise ValueError("'shm_names' must be a set")

    for name in shm_names:
        if not isinstance(name, str):
            raise ValueError("Each element of 'shm_names' must be a str")

    try:
        for name in shm_names:
            _shm_locks[name] = Lock()
    except Exception:
        _shm_locks.clear()
        raise

    _inited = True


def get_shm_lock(name: str) -> LockT:
    return _shm_locks[name]


def get_all_shm_locks():
    """For use only by checking deathlocks when a engine worker crashed.
    """
    return _shm_locks.copy()


__all__ = [
    "initialize",
    'get_shm_lock',
    'get_all_shm_locks',
    'overwrite_counter',
]
