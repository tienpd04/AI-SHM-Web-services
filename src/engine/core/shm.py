from multiprocessing.shared_memory import SharedMemory

_shm_cache: dict[str, SharedMemory] = {}

def get_shm(name: str):
    shm = _shm_cache.get(name)
    if shm is None:
        shm = SharedMemory(name)
        _shm_cache[name] = shm

    return shm

__all__ = [
    'get_shm',
    ]