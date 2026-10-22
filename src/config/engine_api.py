'''
All constants, schemas, common functools for both engine worker(s) and web application worker(s).
'''


import os
import base64
from dataclasses import dataclass as _dataclass
from enum import IntEnum as _IntEnum
from enum import StrEnum as _StrEnum

from .constants import SHM_HEADER_SIZE as SHM_HEADER_SIZE
from .settings import STORAGE_DIR as STORAGE_DIR
from .settings import USING_SHM_LOCK


class EngineSocketAPI(_IntEnum):
    HEALTH_CHECK = 1
    INFERENCE = 2


OVERWRITE_STT_CODE = 499

SHM_CANCELLED_STT_CODE = 488


class ModelName(_StrEnum):
    # use ASCII only, do not use unicode
    ARC_FACE = 'ARC_FACE'
    COCO_YOLO11 = 'COCO_YOLO11'
    PPOCR_V6 = 'PPOCR_V6'


@_dataclass(frozen=True, kw_only=True)
class ShmTensorSchema:
    shape: tuple[int, ...] | list[int]
    dtype: str
    shm_name: str
    buf_from: int = SHM_HEADER_SIZE

    def original_dict(self):
        '''
        Ensure that the returned dictionary (dict) is not modified.
        '''
        return self.__dict__


del _dataclass, _IntEnum, _StrEnum

if USING_SHM_LOCK and SHM_HEADER_SIZE >= 16:
    import time

    def generate_shm_nonce():
        """This function is called within a lock block.
            The execution time of the code segment inside the lock block is almost always greater than 1 nanosecond.
            This means that the subsequent `monotonic_ns` value will always increase.
        """
        return (
            os.urandom(SHM_HEADER_SIZE - 6)  # >= 80 bits random
            +
            (time.monotonic_ns() & 0xffff_ffff_ffff).to_bytes(
                6, 'little')  # 48 bits timestamp (> 3 days > engine request timeout)
        )

else:
    def generate_shm_nonce():
        """like uuid4
            """
        return os.urandom(SHM_HEADER_SIZE)


def generate_filestem():
    """like uuid4
    """
    tok = os.urandom(16)
    return base64.urlsafe_b64encode(tok).rstrip(b'=').decode('ascii')


__all__ = [
    x for x in locals() if not x.startswith('_')
]
