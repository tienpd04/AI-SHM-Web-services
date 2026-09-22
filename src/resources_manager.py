from __future__ import annotations
import struct
import time
from multiprocessing import Lock
from multiprocessing.shared_memory import SharedMemory
from types import MappingProxyType
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from multiprocessing.synchronize import Lock as LockT


class _OneSizeResourcesManager:
    _idx_names: tuple[str]
    _set_names: frozenset[str]
    _size: int
    _timeout: float | int

    _fmt: str
    _shm: SharedMemory

    def __init__(self, names: set[str], size: int, timeout: float):
        self._set_names = frozenset(names)
        self._idx_names = tuple(names)
        self._size = size
        self._timeout = timeout

        self._fmt = 'd' * len(names)
        shm_size = struct.calcsize(self._fmt)
        self._shm = SharedMemory(create=True, size=shm_size)
        self._shm.buf[:] = struct.pack(self._fmt, *([0.0] * len(names)))

    @property
    def names(self):
        return self._set_names

    @property
    def size(self):
        return self._size

    @property
    def timeout(self):
        return self._timeout

    def _load_last_use_times(self) -> dict[str, float]:
        use_times = struct.unpack(self._fmt, self._shm.buf)
        ret = {}
        for idx, name in enumerate(self._idx_names):
            last_use_time = use_times[idx]
            if last_use_time > 0:
                ret[name] = last_use_time

        return ret

    def _store_last_use_times(self, last_use_times: dict[str, float]):
        use_times = [last_use_times.get(name, 0.0) for name in self._idx_names]
        self._shm.buf[:] = struct.pack(self._fmt, *use_times)

    def acquire(self, sizes: list[int]) -> list[tuple[str, int]] | None:

        last_use_times = self._load_last_use_times()
        # print(f"Before: {sorted(last_use_times, key=last_use_times.get)}")

        mono = time.monotonic()
        available = self._set_names - set(last_use_times)
        if len(available) >= len(sizes):
            ret_names = list(available)[:len(sizes)]

        else:
            ret_names = list(available)
            for name, last_time in last_use_times.items():
                if mono - last_time > self._timeout:
                    ret_names.append(name)
                    if len(ret_names) == len(sizes):
                        break

        if len(ret_names) == len(sizes):
            ret = []
            for name in ret_names:
                ret.append((name, self._size))
                last_use_times[name] = mono
            self._store_last_use_times(last_use_times)
            # print(f"After: {sorted(last_use_times, key=last_use_times.get)}")
            return ret

        return None

    def release(self, names: set[str]) -> bool:
        ret = True
        last_use_times = self._load_last_use_times()
        for name in names:
            ret = ret and (last_use_times.pop(name, None) is not None)

        self._store_last_use_times(last_use_times)
        return ret

    def cleanup(self):
        self._shm.close()
        self._shm.unlink()


_lock = Lock()

_manager = None

_initial_key = None

_shm_locks: dict[str, LockT] = {}

def initialize(names: set[str], size: int, reuse_after_timeout_enough: float | int, initial_key: str):
    """For use only by the main process
    """
    global _manager, _initial_key

    assert _manager is None, f"{__name__}.initialize called too many time"

    if not isinstance(names, (set, frozenset)):
        raise TypeError(
            f"'names' must be a set or frozenset, not {type(names)}")
    for name in names:
        if not isinstance(name, str):
            raise ValueError("'names' must be a set of str")
    if not isinstance(size, int):
        TypeError(f"'size' must be a int, not {type(size)}")
    if not size > 0:
        raise ValueError("'size' must be a positive integer")

    if not isinstance(reuse_after_timeout_enough, (int, float)):
        raise TypeError(
            f"'reuse_after_timeout_enough' must be float or integer, not {type(reuse_after_timeout_enough)}")
    if not reuse_after_timeout_enough > 0:
        raise ValueError("'reuse_after_timeout_enough' must be a positive number")

    _manager = _OneSizeResourcesManager(names, size, reuse_after_timeout_enough)
    for name in names:
        _shm_locks[name] = Lock()
    _initial_key = initial_key


def acquire(sizes: list[int]):
    """For use only by the web application workers
    """
    if not sizes:
        return None

    if len(sizes) > len(_manager.names):
        return None

    if max(sizes) > _manager.size:
        return None

    with _lock:
        return _manager.acquire(sizes)

def release(names: set[str]):
    """For use only by the web application workers
    """
    if not isinstance(names, set | frozenset):
        names = set(names)
    with _lock:
        return _manager.release(names)

def cleanup(initial_key: str):
    """For use only by the main process
    """
    if initial_key != _initial_key:
        raise ValueError("Invalid 'initial_key'")

    with _lock:
        _manager.cleanup()

def get_shm_lock(name: str) -> LockT:
    return _shm_locks[name]


__all__ = [
    'initialize',
    'acquire',
    'release',
    'cleanup',
    'get_shm_lock'
]