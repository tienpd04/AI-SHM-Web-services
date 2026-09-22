from __future__ import annotations

from multiprocessing import Lock

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from multiprocessing.synchronize import Lock as LockT

_inited = False

_shm_locks: dict[str, LockT] = {}

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


__all__ = [
    "initialize",
    'get_shm_lock'
]



