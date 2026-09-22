from multiprocessing.shared_memory import SharedMemory

from src import resources_manager

_shm_cache: dict[str, SharedMemory] = {}

def get_shm(name: str):
    shm = _shm_cache.get(name)
    if shm is None:
        shm = SharedMemory(name)
        _shm_cache[name] = shm
    return shm

def acquire(sizes: list[int]) -> list[SharedMemory] | None:
    ret = resources_manager.acquire(sizes)
    if ret is None:
        return ret

    return [get_shm(x) for x, _ in ret]

def release(shms: list[SharedMemory]):
    return resources_manager.release({shm.name for shm in shms})

def get_shm_lock(shm: SharedMemory):
    return resources_manager.get_shm_lock(shm.name)

__all__ = [
    'get_shm',
    'acquire',
    'release',
    'get_shm_lock'
    ]