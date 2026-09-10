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
    return resources_manager.release(set([shm.name for shm in shms]))

__all__ = [
    'get_shm',
    'acquire',
    'release'
    ]