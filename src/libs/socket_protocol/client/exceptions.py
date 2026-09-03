class RequestException(OSError):
    pass

class RequestConnectionError(RequestException, ConnectionError):
    pass

class RequestTimeoutError(RequestException, TimeoutError):
    pass

class ProtocolError(RequestException):
    pass

class ContentEncodingError(RequestException, ValueError):
    pass

class ContentDecodingError(RequestException):
    pass

class StatusCodeError(RequestException):
    def __init__(self, status_code: int, *args):
        super().__init__(*args)
        self.status_code = status_code