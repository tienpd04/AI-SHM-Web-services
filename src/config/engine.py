'''
All for both engine worker and web application worker use.
'''


import socket as _socket
from copy import deepcopy as _deepcopy
from dataclasses import dataclass as _dataclass
from enum import IntEnum as _IntEnum
from enum import StrEnum as _StrEnum
from typing import Final as _Final

from .settings import ENGINE_UNIX_SOCKET_PATH as _ENGINE_UNIX_SOCKET_PATH
from .settings import STORAGE_DIR as STORAGE_DIR
from .settings import SHM_HEADER_SIZE as SHM_HEADER_SIZE

ENGINE_SOCKET_ADDRESS: _Final[str] = _ENGINE_UNIX_SOCKET_PATH
ENGINE_SOCKET_FAMILY: _Final[int] = _socket.AF_UNIX

ENGINE_SOCKET_KIND: _Final[int] = _socket.SOCK_STREAM


class EngineSocketAPI(_IntEnum):
    HEALTH_CHECK = 1
    INFERENCE = 2


class ModelName(_StrEnum):
    ARC_FACE = 'ARC_FACE'
    COCO_YOLO11 = 'COCO_YOLO11'
    PPOCR_V6 = 'PPOCR_V6'


@_dataclass(frozen=True, kw_only=True)
class ShmTensorSchema:
    shape: tuple[int, ...] | list[int]
    dtype: str
    shm: str
    buf_from: int = SHM_HEADER_SIZE

    def to_dict(self):
        return _deepcopy(self.__dict__)

    def original_dict(self):
        '''
        Ensure that the returned dictionary (dict) is not modified. If unsure, use 'to_dict' instead.
        '''
        return self.__dict__


del _socket, _Final, _dataclass, _IntEnum, _StrEnum, _ENGINE_UNIX_SOCKET_PATH

__all__ = [
    x for x in locals() if not x.startswith('_')
]
