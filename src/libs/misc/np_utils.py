

import numpy as np
from numpy.typing import NDArray
from hashlib import sha256
import time


def ndarray_sum_hash(a: NDArray):
    if not a.size:
        return sha256()

    buff = memoryview(a.tobytes())
    uint32_shape = (len(buff) // 4,)
    view = np.ndarray(uint32_shape, dtype=np.uint32, buffer=buff)
    remain = buff[len(buff) - (len(buff) % 4):]
    return sha256(int(np.sum(view[::2])).to_bytes(8) + int(np.sum(view[1::2])).to_bytes(8) + remain)


def list_ndarray_sum_hash(list_array: list[NDArray]):
    # t1 = time.perf_counter()
    if not list_array:
        return sha256()

    h = ndarray_sum_hash(list_array[0])
    for i in range(1, len(list_array)):
        h.update(ndarray_sum_hash(list_array[i]).digest())
    # t2 = time.perf_counter()
    return h
