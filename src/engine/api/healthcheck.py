

from src.libs.socket_protocol.server import Request, Response


def health_check(req: Request) -> Response:
    '''
    Health Check API

    Return:
    Response with status code 200
    '''

    return Response()

__all__ = [
    "health_check",
]