import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request, Response

from starlette.middleware.base import BaseHTTPMiddleware


class SetRequestIDMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: 'Request', call_next):
        request_id = secrets.token_hex(6).upper()
        setattr(request.state, "request_id", request_id)
        response: 'Response' = await call_next(request)
        response.headers['X-Request-ID'] = request_id
        return response


del BaseHTTPMiddleware
