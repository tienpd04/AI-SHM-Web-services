"""This is a sub module of main.
Create and manager the shared object using between processes.
"""


from __future__ import annotations

import os
from multiprocessing import BoundedSemaphore, Lock, Semaphore
from multiprocessing.shared_memory import SharedMemory
from types import MappingProxyType
from typing import TYPE_CHECKING

# NOTE:
#   Do not import any object from worker module.
#   Do not import any big module in here
#       (The master process doesn't not using that.)

if TYPE_CHECKING:
    from multiprocessing.synchronize import Lock as LockT
    from multiprocessing.synchronize import Semaphore as SemT


class _ShmManager(object):
    __slots__ = ('_shm', '_lock', '_name_tuples')

    _shm: SharedMemory
    _lock: LockT
    _name_tuples: tuple[tuple[str, ...]]

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

    def get_shm_names_set(self) -> tuple[tuple[str, ...], bool] | None:
        # Master process does not using this module. Import here for the web application worker only.
        import psutil

        pid = os.getpid()

        pid_bytes = pid.to_bytes(4, 'little')
        with self._lock:
            for i, names in enumerate(self._name_tuples):
                # Available
                if self._shm.buf[i * 4: (i+1)*4] in [b'\xff\xff\xff\xff', pid_bytes]:
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

    _cnt: SemT

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

    _flg: SemT

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


_isinitialized = False

_manager = None

_shm_locks: MappingProxyType[str, LockT] = None

_overwrite_counter = None

# For ensure the import is correct path, it's will raise error if using this.
_dl_chk_flg = _NotAFlag()



def initialize(shm_name_tuples: list[tuple[str, ...]]) :
    """For use only by the main process
    """
    global _isinitialized, _manager, _overwrite_counter, _dl_chk_flg, _shm_locks
    assert _isinitialized is False, f"{__name__}.initialize called too many times"

    assert all([isinstance(x, (list, tuple)) for x in shm_name_tuples])

    shm_names = []
    for tup in shm_name_tuples:
        shm_names.extend(tup)

    assert all([isinstance(x, str) for x in shm_names]), 'SHM name must be str'

    assert len(set(shm_names)) == len(shm_names), 'SHM name must be uniquie'

    _manager = _ShmManager(shm_name_tuples)

    locks = {}

    for name in shm_names:
        locks[name] = Lock()

    _shm_locks = MappingProxyType(locks)

    _overwrite_counter = _OverwriteCounter()

    from src.config.settings import DEATHLOCKS_CHECKING
    _dl_chk_flg = _SharedFlag() if DEATHLOCKS_CHECKING else False

    _isinitialized = True


def cleanup():
    """For use only by the main process
        """
    _manager.cleanup()


def worker_get_shm_names_set() -> tuple[tuple[str, ...], bool] | None:
    """For use only by the web aplication workers
    Get only once and using entire lifecycle
    """
    return _manager.get_shm_names_set()


def current_using_shms():
    return _manager.status()


def get_shm_lock(name: str) -> LockT:
    return _shm_locks[name]


def get_all_shm_locks():
    """For use only by the engine master process
    """
    return _shm_locks


def get_overwrite_counter():
    return _overwrite_counter


def get_deathlock_checking_flag():
    """For use only by the engine master process
    """
    return _dl_chk_flg


def is_in_deathlocks_checking():
    return bool(_dl_chk_flg)


__all__ = [
    "initialize",
    "cleanup",
    'get_shm_lock',
    'worker_get_shm_names_set',
    'current_using_shms',
    'get_all_shm_locks',
    'get_deathlock_checking_flag',
    'is_in_deathlocks_checking',
    'get_overwrite_counter'

]

if 0:
    class ShmTaskCancelledByDLChecking(Exception):
        pass

    class SHMAccessError(RuntimeError):
        pass

    import contextlib
    @contextlib.contextmanager
    def shmreadwritecontext(shm_name: str):
        lock = _shm_locks[shm_name]
        got_lock = lock.acquire(False)
        if not got_lock:
            if is_in_deathlocks_checking():
                # catch this exception and switch to 'file' mode
                raise ShmTaskCancelledByDLChecking()
            else:
                raise SHMAccessError("Too many processes or threads access shared memory simultaneously or a worker process was crashed while holding a lock")

        try:
            yield
        finally:
            lock.release()

    __all__.extend(['ShmTaskCancelledByDLChecking', 'SHMAccessError', 'shmreadwritecontext'])
