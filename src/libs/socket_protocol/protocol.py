
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


# REQUEST_HEADER_SIZE: Final[int] = 8
# RESPONSE_HEADER_SIZE: Final[int] = 8

class SocketProtocolError(OSError):
    pass
class NotEnoughHeaderSize(SocketProtocolError):
    pass
class InvalidProtocolHeaderKey(SocketProtocolError):
    pass

import os

_using_header_key = os.getenv("SOCKET_PROTOCOL_USING_HEADER_KEY", 'on').lower() not in ('off', 'false')

del os

if _using_header_key:
    # To ensure that both the client and the server use this protocol. The default is ON.
    # Setup 'SOCKET_PROTOCOL_HEADER_KEY' environment is make more secure.

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
        return _client_key + api.to_bytes(2,'little') + \
                content_type.to_bytes(2,'little') + \
                    len(content).to_bytes(4,'little')

    def unpack_request_header(buff: bytes) -> Tuple[int, int, int]:
        if len(buff) < 24:
            raise NotEnoughHeaderSize("'buff' required at least 24 number of bytes") from None

        if buff[:16] != _client_key:
            raise InvalidProtocolHeaderKey() from None

        api = int.from_bytes(buff[16:18],'little')
        content_type = int.from_bytes(buff[18:20],'little')
        content_len = int.from_bytes(buff[20:24],'little')
        return api, content_type, content_len


    def pack_response_header(status_code: int, content_type: int, content: bytes) -> bytes:
        return _server_key + status_code.to_bytes(2,'little') + \
                content_type.to_bytes(2,'little') + \
                    len(content).to_bytes(4,'little')

    def unpack_response_header(buff: bytes) -> Tuple[int, int, int]:
        if len(buff) < 24:
            raise NotEnoughHeaderSize("'buff' required at least 24 number of bytes") from None

        if buff[:16] != _server_key:
            raise InvalidProtocolHeaderKey() from None

        status_code = int.from_bytes(buff[16:18],'little')
        content_type = int.from_bytes(buff[18:20],'little')
        content_len = int.from_bytes(buff[20:24],'little')
        return status_code, content_type, content_len

else:
    REQUEST_HEADER_SIZE: Final[int] = 8
    RESPONSE_HEADER_SIZE: Final[int] = 8

    def pack_request_header(api: int, content_type: int, content: bytes | memoryview) -> bytes:
        return api.to_bytes(2,'little') + \
                content_type.to_bytes(2,'little') + \
                    len(content).to_bytes(4,'little')

    def unpack_request_header(buff: bytes) -> Tuple[int, int, int]:
        if len(buff) < 8:
            raise NotEnoughHeaderSize(f"\'buff\' required at least 8 number of bytes")

        api = int.from_bytes(buff[:2],'little')
        content_type = int.from_bytes(buff[2:4],'little')
        content_len = int.from_bytes(buff[4:8],'little')
        return api, content_type, content_len


    def pack_response_header(status_code: int, content_type: int, content: bytes) -> bytes:
        return status_code.to_bytes(2,'little') + \
                content_type.to_bytes(2,'little') + \
                    len(content).to_bytes(4,'little')

    def unpack_response_header(buff: bytes) -> Tuple[int, int, int]:
        if len(buff) < 8:
            raise NotEnoughHeaderSize(f"\'buff\' required at least 8 number of bytes")

        status_code = int.from_bytes(buff[:2],'little')
        content_type = int.from_bytes(buff[2:4],'little')
        content_len = int.from_bytes(buff[4:8],'little')
        return status_code, content_type, content_len
