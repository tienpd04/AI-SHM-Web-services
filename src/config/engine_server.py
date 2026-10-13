"""For engine master and web application worker(s)"""


import socket as _socket
from typing import Final as _Final

from .settings import ENGINE_UNIX_SOCKET_PATH as _ENGINE_UNIX_SOCKET_PATH

ENGINE_SOCKET_ADDRESS: _Final[str] = _ENGINE_UNIX_SOCKET_PATH
ENGINE_SOCKET_FAMILY: _Final[int] = _socket.AF_UNIX

ENGINE_SOCKET_KIND: _Final[int] = _socket.SOCK_STREAM

del _socket, _Final, _ENGINE_UNIX_SOCKET_PATH

__all__ = [x for x in locals() if not x.startswith('_')]
