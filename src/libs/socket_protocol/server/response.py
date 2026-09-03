import json
from typing import Any

from ..protocol import (STATUS_CODE_MAX, STATUS_CODE_MIN, ResponseContentType,
                        pack_response_header)


class Response:
    content_type = ResponseContentType.BYTES
    charset = "utf-8"

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
    ) -> None:
        if not isinstance(status_code, int) or status_code < STATUS_CODE_MIN or status_code > STATUS_CODE_MAX:
            raise ValueError(f"\'status_code\' must be an integer between {STATUS_CODE_MIN} and {STATUS_CODE_MAX}")
        self.status_code = status_code
        self.content = content
        body = self.render(content)
        header = pack_response_header(self.status_code, self.content_type, body)
        self.data = header + body

    def render(self, content: Any) -> bytes | memoryview:
        if content is None:
            return b""
        if isinstance(content, bytes | memoryview):
            return content
        return content.encode(self.charset)  # type: ignore


class PlainTextResponse(Response):
    content_type = ResponseContentType.TEXT


class JSONResponse(Response):
    content_type = ResponseContentType.JSON
    ensure_ascii = False

    def __init__(
        self,
        content: Any,
        status_code: int = 200
    ) -> None:
        super().__init__(content, status_code)

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=self.ensure_ascii,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode(self.charset)

class ASCIIPlainTextResponse(PlainTextResponse):
    charset = 'ascii'

class ASCIIJsonResponse(JSONResponse):
    charset = 'ascii'
    ensure_ascii = True