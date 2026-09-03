import json
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from socket import SocketType


class _RequestState:
    pass


class Request:
    _state: _RequestState
    scope: dict[str, Any]
    content: bytes

    def __init__(self, scope: dict[str, Any], content: bytes):
        self.scope = scope
        self.content = content
        self._state = _RequestState()

    @property
    def content_type(self) -> int:
        return cast(int, self.scope["content_type"])

    @property
    def api(self) -> int:
        return cast(int, self.scope['api'])

    @property
    def app(self) -> Any:
        return self.scope['app']

    @property
    def state(self) -> _RequestState:
        return self._state

    @property
    def conn(self) -> 'SocketType':
        return self.scope['conn']

    def json(self) -> Any:
        return json.loads(self.content)

    def text(self) -> str:
        return self.content.decode()
