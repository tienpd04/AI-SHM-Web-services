import socket as _socket
from enum import IntEnum as _IntEnum
from typing import Final as _Final

from .settings import RESOURCES_UNIX_SOCKET_PATH as _RESOURCES_UNIX_SOCKET_PATH

RESOURCES_SOCKET_ADDRESS: _Final[str] = _RESOURCES_UNIX_SOCKET_PATH
RESOURCES_SOCKET_FAMILY: _Final[int] = _socket.AF_UNIX

RESOURCES_SOCKET_KIND: _Final[int] = _socket.SOCK_STREAM


class ResourcesSocketAPI(_IntEnum):
    HEALTH_CHECK = 1
    TAKE_RESOURCES = 2


del _socket, _IntEnum, _Final, _RESOURCES_UNIX_SOCKET_PATH
