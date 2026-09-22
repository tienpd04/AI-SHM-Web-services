
import logging
import socket
import struct
import time
import traceback
from enum import IntFlag
from socket import SocketType
from typing import Any, Callable, Dict, NoReturn, TypeAlias

from .. import sp_status_code
from ..protocol import (API_MAX, API_MIN, REQUEST_HEADER_SIZE,
                        InvalidProtocolHeaderKey, NotEnoughHeaderSize,
                        unpack_request_header)
from .request import Request
from .response import (ASCIIPlainTextResponse, JSONResponse, PlainTextResponse,
                       Response)

RequestHandler: TypeAlias = Callable[[Request], Response | Any]

ExceptionHandler: TypeAlias = Callable[[Request, Exception], Response]


def _document_api(req: Request) -> Response:
    '''
    Returns a PlainTextResponse containing the documentation for all APIs.
    '''
    app: SocketApplicaltion = req.app
    return PlainTextResponse(app.api_documents())


def _recv_enough(sock: SocketType, size: int) -> bytes:
    chunks = []
    while size > 0:
        chunk = sock.recv(size)
        if not chunk:
            break
        chunks.append(chunk)
        size -= len(chunk)

    return b''.join(chunks)


def _get_client_info(conn: SocketType) -> str:
    try:
        client_id = conn.fileno()
    except Exception:
        return ""

    try:
        creds = conn.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
        pid, uid, _ = struct.unpack('3i', creds)
        client_label = f"PID:{pid} (Socket FD:{client_id})"
    except Exception:
        client_label = f"Socket FD:{client_id}"
    return client_label


class _AppState:
    pass


DOCUMENT_API = API_MAX  # API for document of all registered APIs, current value is 65535
REGISTER_API_MIN = API_MIN
REGISTER_API_MAX = DOCUMENT_API - 1


class SocketApplicaltion:
    _state: _AppState
    _api_handlers: Dict[int, RequestHandler]
    _api_documents: Dict[int, tuple[str, str, str]]

    _default_response_class: type[Response]
    _timeout: int | float | None

    _exception_handlers: list[tuple[type[Exception], ExceptionHandler]]

    _logger: logging.Logger | None = None

    _first_rcv_size: int

    def __init__(
        self,
        *,
        timeout: float | int | None = 300,
        first_rcv_size: int = 4096,
        logger: logging.Logger | str = None,
        default_response_class: type[Response] = JSONResponse
    ):

        if not isinstance(timeout, float | int | None):
            raise TypeError(
                f"'timeout' must be int, float or None, not {type(timeout)}")

        if not isinstance(first_rcv_size, int):
            raise TypeError(
                f"'first_rcv_timeout' must be int, float or None, not {type(timeout)}")

        if not isinstance(default_response_class, type) or not issubclass(default_response_class, Response):
            raise TypeError(
                f"'default_response_class' must be a subclass of {Response.__name__}")

        if not isinstance(logger, logging.Logger | str | None):
            raise TypeError("'logger' must be Logger, str or None")

        if timeout is not None and timeout <= 0:
            timeout = None

        first_rcv_size = max(first_rcv_size, REQUEST_HEADER_SIZE)

        self._timeout = timeout
        self._first_rcv_size = first_rcv_size
        self._default_response_class = default_response_class
        self._api_handlers = {}
        self._exception_handlers = []
        self._api_documents = {}
        self._state = _AppState()

        if isinstance(logger, logging.Logger):
            self._logger = logger
        elif isinstance(logger, str):
            self._logger = logging.getLogger(logger)

        self._register(DOCUMENT_API, _document_api,
                       'Desctiption for all of APIs')

    @property
    def state(self) -> _AppState:
        return self._state

    def register(self, api: int, handler: RequestHandler, description: str = None):
        if not isinstance(api, int) or not REGISTER_API_MIN <= api <= REGISTER_API_MAX:
            raise ValueError(
                f"'api' must be an integer from {REGISTER_API_MIN} to {REGISTER_API_MAX}") from None
        return self._register(api, handler, description)

    def add_exception_handler(self, exp_class: type[Exception], handler: ExceptionHandler):
        if not isinstance(exp_class, type):
            raise ValueError("'exp_class' must be a class type")

        if not issubclass(exp_class, Exception):
            raise ValueError("'exp_class' must be a subclass of Exception")

        insert_index = len(self._exception_handlers)
        for i, (added_exp_class, _) in enumerate(self._exception_handlers):
            if exp_class is added_exp_class:
                raise ValueError(
                    f"Duplicated exception handler. The handler for the exception class '{exp_class.__name__}' already added.")
            if issubclass(exp_class, added_exp_class):
                insert_index = i
                break
        self._exception_handlers.insert(insert_index, (exp_class, handler))

    def api_documents(self) -> str:
        document_list: list[str] = []
        for api in sorted(self._api_documents):
            descript, endpoint, handler_doc = self._api_documents[api]
            doc_str = f"=========\nAPI ID: {api}\nDESCRIPTION: {descript}\nENDPOINT: {endpoint}\nDOCUMENT STRING:\n{handler_doc}"
            document_list.append(doc_str)
        return "\n\n".join(document_list)

    def run(
        self,
        # NOTE: server_socket must be binded and listesning before run the application
        server_socket: socket.socket,
        log_traceback=True,
        stop_after_consecutive_accept_error=100,
    ) -> NoReturn:

        logger = self._logger
        handle = self._handle
        accept_error = 0
        while True:
            try:
                try:
                    conn, address = server_socket.accept()
                except Exception:
                    # Never in this case if the server_socket is binded and listesning
                    if logger is not None:
                        if log_traceback:
                            logger.error(
                                "Failed to accept connection from server_socket:\n%s", traceback.format_exc())
                        else:
                            logger.error(
                                "Failed to accept connection from server_socket: %s", str(e))
                    accept_error += 1
                    if accept_error >= stop_after_consecutive_accept_error:
                        import sys
                        sys.exit(1)
                    else:
                        time.sleep(1)
                        continue
                else:
                    accept_error = 0

                try:
                    handle(conn, address)
                except socket.timeout:
                    if logger is not None:
                        logger.warning(
                            "Connection timeout from address: '%s'", str(address) or _get_client_info(conn))
                except ConnectionError:
                    if logger is not None:
                        logger.warning(
                            "Disconnected from address: '%s'", str(address) or _get_client_info(conn))
                finally:
                    conn.close()

            except Exception as e:
                if logger is not None:
                    if log_traceback:
                        logger.error(
                            "Exception from Socket Application:\n%s", traceback.format_exc())
                    else:
                        logger.error(
                            "Exception from Socket Application: %s", str(e))

    def _prepare_request(self, conn: SocketType, address) -> Request | None:
        """Parser the header and validate
        """
        data = conn.recv(self._first_rcv_size)
        if 0 < len(data) < REQUEST_HEADER_SIZE:
            data += _recv_enough(conn, REQUEST_HEADER_SIZE - len(data))

        try:
            api, content_type, content_len = unpack_request_header(data)
        except NotEnoughHeaderSize:
            if self._logger is not None:
                self._logger.warning("Not enough header size from address: '%s'", str(
                    address) or _get_client_info(conn))
            res = ASCIIPlainTextResponse(
                f"Request header required at least {REQUEST_HEADER_SIZE} bytes", status_code=sp_status_code.SP_420_INVALID_HEADER)
            conn.sendall(res.data)
            return None
        except InvalidProtocolHeaderKey:
            if self._logger is not None:
                self._logger.warning("Invalid protocol header key from address: '%s'", str(
                    address) or _get_client_info(conn))
            res = ASCIIPlainTextResponse(
                f"Invalid protocol header key", status_code=sp_status_code.SP_420_INVALID_HEADER)
            conn.sendall(res.data)
            return None

        if api not in self._api_handlers:
            if self._logger is not None:
                self._logger.warning("Request not found from address: '%s', api: %d", str(
                    address) or _get_client_info(conn), api)
            res = ASCIIPlainTextResponse(
                f"Request not found with api: {api}", status_code=sp_status_code.SP_404_NOT_FOUND)
            conn.sendall(res.data)
            return None

        remaining_len = content_len - (len(data) - REQUEST_HEADER_SIZE)
        if remaining_len > 0:
            remaining_content = _recv_enough(
                conn, remaining_len)
            content = data[REQUEST_HEADER_SIZE:] + remaining_content
        else:
            content = data[REQUEST_HEADER_SIZE:]

        if len(content) != content_len:
            res = ASCIIPlainTextResponse(
                f"Request content length error, expected {content_len}, got {len(content)}", status_code=sp_status_code.SP_421_CONTENT_LENGTH_ERROR)
            conn.sendall(res.data)
            return None

        return Request(scope={'app': self, 'conn': conn, 'api': api,
                              'content_type': content_type, 'client': address}, content=content)

    def _handle(self, conn: SocketType, address):
        """Hanle the connection
        """
        conn.settimeout(self._timeout)
        req = self._prepare_request(conn, address)
        if req is None:
            return
        try:
            response = self._api_handlers[req.api](req)
            if not isinstance(response, Response):
                response = self._default_response_class(response)
        except Exception as e:
            found = False
            for exp_cls, exp_handler in self._exception_handlers:
                if isinstance(e, exp_cls):
                    response = exp_handler(req, e)
                    if not isinstance(response, Response):
                        raise TypeError(
                            f"Exception handler must return a Response object, not {type(response)}. Check your exception handler at {exp_handler.__code__.co_filename}:{exp_handler.__code__.co_firstlineno}") from None
                    found = True
                    break
            if not found:
                raise e

        conn.sendall(response.data)

    def _register(self, api: int, handler: RequestHandler, description: str = None):
        api = int(api)
        self._api_handlers[api] = handler
        self._api_documents[api] = (
            description or "", handler.__module__ + "." + handler.__name__, handler.__doc__ or "")


RetAddress: TypeAlias = Any
PermissionChecker: TypeAlias = Callable[[SocketType, RetAddress], bool]


class PermissionFlag(IntFlag):
    DO_NOTHING = 0
    WARNING = 1
    RESPONSE = 2


DEFAULT_PERMISSION_FLAGS = PermissionFlag.WARNING | PermissionFlag.RESPONSE


def no_check_permissions(conn: SocketType, addr: RetAddress) -> bool:
    return True


class PermissionSocketApplication(SocketApplicaltion):
    def __init__(
        self,
        *,
        timeout: float | int | None = 300,
        first_rcv_size: int = 4096,
        logger: logging.Logger | str | None = None,
        default_response_class=JSONResponse,
        permission_checker: PermissionChecker = no_check_permissions,
        permission_flags=DEFAULT_PERMISSION_FLAGS
    ):
        super().__init__(timeout=timeout, first_rcv_size=first_rcv_size,
                         logger=logger, default_response_class=default_response_class)
        self._check_permission = permission_checker
        self._perm_flags = int(permission_flags or 0)

    def _handle(self, conn, address):
        if not self._check_permission(conn, address):
            if self._logger is not None and self._perm_flags & PermissionFlag.WARNING:
                self._logger.warning("Premission denied from address: %s", str(
                    address) or _get_client_info(conn))
            if self._perm_flags & PermissionFlag.RESPONSE:
                res = ASCIIPlainTextResponse(
                    "Permission Denied", sp_status_code.SP_403_FORBIDDEN)
                conn.sendall(res.data)
            return
        return super()._handle(conn, address)
