'''
All constants, schemas for both engine worker(s) and web application worker(s).
'''


from dataclasses import dataclass as _dataclass
from enum import IntEnum as _IntEnum
from enum import StrEnum as _StrEnum

from .constants import SHM_HEADER_SIZE as SHM_HEADER_SIZE
from .settings import STORAGE_DIR as STORAGE_DIR


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

__all__ = [
    x for x in locals() if not x.startswith('_')
]
