import time
from typing import cast

from src.libs.socket_protocol.server import (ASCIIJsonResponse,
                                             ASCIIPlainTextResponse,
                                             PlainTextResponse, Request,
                                             Response, SocketApplicaltion)

from .logger import logger
from .manager import InvalidApiKey, InvalidWorkerPID, ResourcesManager


class _LogInterval:
    __slots__ = ('lasttime',)
    lasttime: float

    def __init__(self):
        self.lasttime = 0


_replaced_log_interval = _LogInterval()


def health_check(req: Request):
    '''
    return Response with status code 200
    '''
    manager = cast(ResourcesManager, getattr(
        cast(SocketApplicaltion, req.app).state, 'manager'))
    now = time.time()
    if now > _replaced_log_interval.lasttime + 3600:
        replace_pids = manager.get_last_replaced_pids()
        log_replaces = [
            k for k, v in replace_pids if v + 7 * 24 * 60 * 60 < now]
        logger.info(
            "The health check last week reused resources from dead worker processes: %s", log_replaces)
        _replaced_log_interval.lasttime = now
    return Response()


def take_resources(req: Request) -> ASCIIJsonResponse:
    '''
    Request Json:
    {
        'api_key': string or None,
        'worker_pid': integer
    }

    Return:
    case success:
        type: ASCIIJsonResponse
        content: list[str]:  ['Shm_01', 'Shm_02', ...]

    case failure:
        type: ASCIIPlainTextResponse
        content: the error message
    '''

    try:
        data = req.json()
        assert isinstance(data, dict), ''

    except Exception:
        return ASCIIPlainTextResponse("Required content as a dict", 422)

    api_key = data.get('api_key')
    if not isinstance(api_key, (str, type(None))):
        return ASCIIPlainTextResponse("'api_key' must be a string or None", 422)

    worker_pid = data.get("worker_pid")

    if not isinstance(worker_pid, int):
        return ASCIIPlainTextResponse("'worker_pid' must be an integer", 422)

    manager = cast(ResourcesManager, getattr(
        cast(SocketApplicaltion, req.app).state, 'manager'))

    try:
        resources = manager.take_forever(api_key, worker_pid)

    except InvalidApiKey:
        return ASCIIPlainTextResponse(f"Permission denied", 403)

    except InvalidWorkerPID:
        return ASCIIPlainTextResponse(f"'worker_pid' {worker_pid} is not running", 403)

    except Exception as e:
        logger.error("Error while during take resources: %s", str(e))
        return PlainTextResponse(f"Intenal Server Error: {e}", 500)

    if resources is None:
        return ASCIIPlainTextResponse("No available resouces", 400)

    resources = list(resources)
    return ASCIIJsonResponse(resources)
