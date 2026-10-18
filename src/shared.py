"""This is a sub module of main.
Create and manager shared objects using between processes.
"""

import os
from multiprocessing import BoundedSemaphore, Lock, Semaphore
from multiprocessing.shared_memory import SharedMemory
from types import MappingProxyType
from typing import TYPE_CHECKING

from src.config.settings import DEATHLOCKS_CHECKING, USING_SHM_LOCK

# NOTE:
#   Do not import any object from worker module.
#   Do not import any big module in here
#       (The master process doesn't not using that.)


if TYPE_CHECKING:
    from multiprocessing.synchronize import Lock as LockT
    from multiprocessing.synchronize import Semaphore as SemT

# After fork, the objects in 'multiprocessing' module like Lock, Semaphore, SharedMemory can be shared.
# All other objects, like int, str, dict, list, func, class, ... are copied (they are not shared objects)

def _retake_warning(pid: int):
    try:
        import logging

        from src.config.constants import MAIN_LOGGER_NAME
        logger = logging.getLogger(MAIN_LOGGER_NAME)
        logger.warning("Worker PID [%d] taking resources to many times", pid)
    except Exception:
        import warnings
        warnings.warn(f"Worker PID [{pid}] taking resources to many times", category=RuntimeWarning)

class _ResourcesManager(object):
    __slots__ = ('_shm', '_lock', '_name_tuples')

    _shm: SharedMemory
    _lock: 'LockT'
    _name_tuples: tuple[tuple[str, ...], ...]

    def __init__(self, shm_name_tuples: list[tuple[str, ...]]):
        # Make constants
        name_tuples = tuple([tuple(x) for x in shm_name_tuples])
        lock = Lock()
        size = 4 * len(shm_name_tuples)
        shm = SharedMemory(create=True, size=size)
        shm.buf[:] = b'\xff' * size

        object.__setattr__(self, '_shm', shm)
        object.__setattr__(self, '_lock', lock)
        object.__setattr__(self, '_name_tuples', name_tuples)

    def __setattr__(self, name, value):
        raise AttributeError(
            f"type object '{self.__class__.__name__}' has no attribute '{name}'")

    def take_shm_names_set(self) -> tuple[tuple[str, ...], bool] | None:
        # Master process does not using this module. Import here for the web application worker only.
        import psutil

        pid = os.getpid()

        pid_bytes = pid.to_bytes(4, 'little')

        with self._lock:
            for i, names in enumerate(self._name_tuples):
                # Available
                # It's not a problem if it's taken again. But hope it's only taken once.
                if self._shm.buf[i * 4: (i+1)*4] in [b'\xff\xff\xff\xff', pid_bytes]:
                    if self._shm.buf[i * 4: (i+1)*4] == pid_bytes:
                        _retake_warning(pid)
                    else:
                        self._shm.buf[i * 4: (i+1)*4] = pid_bytes
                    return names, True

            for i, names in enumerate(self._name_tuples):

                check_pid = int.from_bytes(
                    self._shm.buf[i * 4: (i+1)*4], 'little')

                if not psutil.pid_exists(check_pid):

                    # Reuse from the terminated worker process
                    self._shm.buf[i * 4: (i+1)*4] = pid_bytes

                    return names, False

        return None

    def status(self) -> dict[int, tuple[str, ...]]:

        ret = {}
        with self._lock:
            for i, names in enumerate(self._name_tuples):
                if self._shm.buf[i * 4: (i+1)*4] != b'\xff\xff\xff\xff':
                    pid = int.from_bytes(
                        self._shm.buf[i * 4: (i+1)*4], 'little')
                    ret[pid] = names

        return ret

    def cleanup(self):
        self._shm.close()
        self._shm.unlink()


class _OverwriteCounter(object):
    __slots__ = ('_cnt',)

    _cnt: 'SemT'

    def __init__(self):

        object.__setattr__(self, '_cnt', Semaphore(0))

    def __setattr__(self, name, value):
        raise AttributeError(
            f"type object '{self.__class__.__name__}' has no attribute '{name}'")

    def increase(self):
        try:
            self._cnt.release()
        except ValueError:
            # It is fine to have a limit; this number is large enough to test
            pass

    def get_value(self):
        return self._cnt.get_value()


class _SharedFlag(object):
    __slots__ = ('_flg',)

    _flg: 'SemT'

    def __init__(self):
        sem = BoundedSemaphore(1)
        sem.acquire(False)
        object.__setattr__(self, '_flg', sem)

    def __setattr__(self, name, value):
        raise AttributeError(
            f"type object '{self.__class__.__name__}' has no attribute '{name}'")

    def is_set(self):
        return self._flg.get_value() > 0

    __bool__ = is_set

    def set(self):
        """For use only by the engine master process
        """
        try:
            self._flg.release()
        except ValueError:
            pass

    def clear(self):
        """For use only by the engine master process
        """
        self._flg.acquire(False)


class _NotAFlag(object):
    __slots__ = ()

    def __bool__(self):
        raise NotImplementedError()

class _DummyLock(object):
    __slots__ = ()

    def acquire(self, *args, **kwargs):
        return True

    def release(self):
        pass

    __enter__ = acquire

    def __exit__(self, exc_type, exc, tb):
        pass


_isinitialized = False

_manager = None

_shm_locks: MappingProxyType[str, 'LockT'] = None

_overwrite_counter = None

# For ensure the import is correct path, it's will raise error if using this.
_dl_chk_flg = _NotAFlag()

_shm_name_tuples = None

_dummy_lock = None

# No need for hashing. Just need to ensure the functions aren't called incorrectly.
_key = None

def initialize(shm_name_tuples: list[tuple[str, ...]], key: str):
    """For use only by the main process
    """
    global _isinitialized, _manager, _dl_chk_flg, _shm_locks, _shm_name_tuples, _key
    assert _isinitialized is False, f"{__name__}.initialize called too many times"

    assert all([isinstance(x, (list, tuple)) for x in shm_name_tuples])

    shm_names = []
    for tup in shm_name_tuples:
        shm_names.extend(tup)

    assert all([isinstance(x, str) for x in shm_names]), 'SHM name must be str'

    assert len(set(shm_names)) == len(shm_names), 'SHM name must be uniquie'


    locks = {}
    if USING_SHM_LOCK:
        for name in shm_names:
            locks[name] = Lock()
    else:
        global _dummy_lock
        _dummy_lock = _DummyLock()
    _shm_locks = MappingProxyType(locks)

    _dl_chk_flg = _SharedFlag() if DEATHLOCKS_CHECKING else False

    _shm_name_tuples = shm_name_tuples

    _key = key

    _isinitialized = True


def init_rs_manager(key):
    """For use only by the main process
    Init resources manager to distribute shared memory for web application worker(s)
    """
    assert _isinitialized, "need to initialize before"
    assert key == _key
    global _shm_name_tuples
    global _manager
    global _overwrite_counter
    assert _manager is None, f"{__name__}.init_rs_manager called too many times"
    _manager = _ResourcesManager(_shm_name_tuples)
    _overwrite_counter = _OverwriteCounter()
    del _shm_name_tuples


def cleanup(key):
    """For use only by the main process
        """
    if _manager is None:
        return
    assert key == _key
    _manager.cleanup()


def worker_take_shm_names_set() -> tuple[tuple[str, ...], bool] | None:
    """For use only by the web aplication workers
    Take only once and using entire lifecycle
    """
    assert _manager is not None
    return _manager.take_shm_names_set()


def current_using_shms():
    """Use for logging
    """
    assert _manager is not None
    return _manager.status()


if not USING_SHM_LOCK:
    def get_shm_lock(name: str) -> _DummyLock:
        # assert _isinitialized
        return _dummy_lock
else:
    def get_shm_lock(name: str) -> 'LockT':
        # assert _isinitialized
        return _shm_locks[name]


def get_all_shm_locks():
    """For use only by the engine master process.
    Never use if `DEATHLOCKS_CHECKING` settings variable is False.
    Using for deathlocks checking after a engine worker was crashed.
    """
    assert _isinitialized
    return _shm_locks


def current_overwrite_counter():
    """For use only by the web application workers process.
    It is used to detect and log shared memory overwrite
    """
    assert _overwrite_counter is not None
    return _overwrite_counter


def get_deathlock_checking_flag():
    """For use only by the engine master process.
    Never use if `DEATHLOCKS_CHECKING` settings variable is False.
    Using for deathlocks checking after a engine worker was crashed.
    """
    assert _isinitialized
    return _dl_chk_flg


def is_in_deathlocks_checking():
    """Always return `False` if the `DEATHLOCKS_CHECKING` settings variable is False.
       Otherwise, return `True` if the master engine activated the deathlock check flag following a worker engine crashed.
            After deathlocks checking is complete, it will return `False'
    """
    # assert _isinitialized
    return bool(_dl_chk_flg)


__all__ = [
    'get_shm_lock',
    'worker_take_shm_names_set',
    'current_using_shms',
    'get_all_shm_locks',
    'get_deathlock_checking_flag',
    'is_in_deathlocks_checking',
    'current_overwrite_counter'
]

