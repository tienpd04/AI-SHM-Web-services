import os
import struct
from enum import IntEnum
from typing import Final, Tuple

__all__ = [
    "RequestContentType",
    "ResponseContentType",
    "API_MIN",
    "API_MAX",
    "REQUEST_HEADER_SIZE",
    "RESPONSE_HEADER_SIZE",
    "STATUS_CODE_MIN",
    "STATUS_CODE_MAX",
    "pack_request_header",
    "unpack_request_header",
    "pack_response_header",
    "unpack_response_header",
    'NotEnoughHeaderSize'
]

STATUS_CODE_MIN: Final[int] = 0
STATUS_CODE_MAX: Final[int] = 65535

CONTENT_TYPE_MIN: Final[int] = 0
CONTENT_TYPE_MAX: Final[int] = 65535

API_MIN: Final[int] = 0
API_MAX: Final[int] = 65535


class RequestContentType(IntEnum):
    BYTES = 1
    TEXT = 2
    JSON = 3


class ResponseContentType(IntEnum):
    BYTES = 1
    TEXT = 2
    JSON = 3


class SocketProtocolError(OSError):
    pass


class NotEnoughHeaderSize(SocketProtocolError):
    pass


class InvalidProtocolHeaderKey(SocketProtocolError):
    pass


_using_header_key = os.getenv(
    "SOCKET_PROTOCOL_USING_HEADER_KEY", 'on').lower() not in ('off', 'false')

del os

if _using_header_key:
    # To ensure that both the client and the server use this protocol. The default is ON.
    # Setup 'SOCKET_PROTOCOL_HEADER_KEY' environment (on both the client and server sides) is make more secure.

    # NOTE:
    #   - The server using content length and running in loop to receive enough.
    #   It can be halt or timeout from a request that not using this protocol.

    # If you have noted the points above and do not wish to use this feature,
    #   set the `SOCKET_PROTOCOL_USING_HEADER_KEY` environment variable to `OFF`
    #   on both the client and server sides.

    from ._internal._private_key import _client_key, _server_key

    REQUEST_HEADER_SIZE: Final[int] = 24
    RESPONSE_HEADER_SIZE: Final[int] = 24

    def pack_request_header(api: int, content_type: int, content: bytes | memoryview) -> bytes:
        return _client_key + struct.pack('HHI', api, content_type, len(content))

    def unpack_request_header(buff: bytes) -> Tuple[int, int, int]:
        if len(buff) < 24:
            raise NotEnoughHeaderSize() from None

        if buff[:16] != _client_key:
            raise InvalidProtocolHeaderKey() from None

        return struct.unpack('HHI', buff[16:24])

    def pack_response_header(status_code: int, content_type: int, content: bytes) -> bytes:
        return _server_key + struct.pack('HHI', status_code, content_type, len(content))

    def unpack_response_header(buff: bytes) -> Tuple[int, int, int]:
        if len(buff) < 24:
            raise NotEnoughHeaderSize() from None

        if buff[:16] != _server_key:
            raise InvalidProtocolHeaderKey() from None

        return struct.unpack('HHI', buff[16:24])

else:
    REQUEST_HEADER_SIZE: Final[int] = 8
    RESPONSE_HEADER_SIZE: Final[int] = 8

    def pack_request_header(api: int, content_type: int, content: bytes | memoryview) -> bytes:
        return struct.pack('HHI', api, content_type, len(content))

    def unpack_request_header(buff: bytes) -> Tuple[int, int, int]:
        if len(buff) < 8:
            raise NotEnoughHeaderSize() from None
        return struct.unpack('HHI', buff[:8])

    def pack_response_header(status_code: int, content_type: int, content: bytes) -> bytes:
        return struct.pack('HHI', status_code, content_type, len(content))

    def unpack_response_header(buff: bytes) -> Tuple[int, int, int]:
        if len(buff) < 8:
            raise NotEnoughHeaderSize() from None
        return struct.unpack('HHI', buff[:8])
