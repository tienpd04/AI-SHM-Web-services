'''
All environment settings can be configured.
'''

import os as _os
from typing import Literal as _Literal
from typing import Type as _Type
from typing import cast as _cast


class _EnvironmentSettingError(EnvironmentError):
    pass


def _getenv(key: str, default=None, strip=True, required=False, cast: _Type = None) -> str | int | None:
    v = _os.getenv(key, default)
    if strip and isinstance(v, str):
        v = v.strip()

    if required and (v is None or v == ''):
        raise _EnvironmentSettingError(
            f"Environment \"{key}\" is required") from None

    if cast is not None:
        if cast == bool and isinstance(v, str):
            return v.lower() in ('1', 'true', 'yes') # otherwise is False, no validate
        try:
            v = cast(v)
        except Exception:
            raise _EnvironmentSettingError(
                f"Environment \"{key}\" must be a {cast.__name__}: '{v}'") from None
    return v

LOGS_DIR: str = _getenv("LOGS_DIR", "logs")

HOST: str = _getenv("HOST", "0.0.0.0")

PORT: int = _getenv("PORT", 8000, cast=int)

NUM_WORKERS: int = _getenv("NUM_WORKERS", 4, cast=int)

WORKER_CONNECTIONS: int = _getenv(
    "WORKER_CONNECTIONS", 64, cast=int)

ERROR_LOG_FILE: str = _getenv(
    "ERROR_LOG_FILE", _os.path.join(LOGS_DIR, "gunicorn-error.log"))

ACCESS_LOG_FILE: str | None = _getenv("ACCESS_LOG_FILE")

LOG_LEVEL: _Literal['error', 'warning', 'info', 'debug'] = {k: k for k in ('error', 'warning', 'info', 'debug')}.get(
    _cast(str, _getenv("LOG_LEVEL", "info")).lower(), 'info')




STORAGE_DIR: str = _getenv("STORAGE_DIR", "/tmp/storage")


ENGINE_UNIX_SOCKET_PATH: str = _getenv("ENGINE_UNIX_SOCKET_PATH", default="/tmp/ai-engine.sock", required=True)

RESOURCE_SHM_INPUT_SIZE_MB: int = _getenv("RESOURCE_SHM_INPUT_SIZE_MB", 32, cast=int)

RESOURCE_SHM_OUTPUT_SIZE_MB: int = _getenv("RESOURCE_SHM_OUTPUT_SIZE_MB", 32, cast=int)

RESOURCES_UNIX_SOCKET_PATH: str = _getenv("RESOURCES_UNIX_SOCKET_PATH", default="/tmp/ai-resources.sock", required=True)


ARC_FACE_MODEL_PATH: str = _getenv('ARC_FACE_MODEL_PATH', "weights/face_extraction.bin")

ARC_FACE_USING_RGB: bool = _getenv('ARC_FACE_USING_RGB', True, cast=bool)

COCO_YOLO11_MODEL_PATH: str = _getenv('COCO_YOLO11_MODEL_PATH', "weights/yolo11n_coco.onnx")

PPOCR_V6_MODEL_PATH: str =  _getenv('PPOCR_V6_MODEL_PATH', "weights/PP-OCRv6_medium_rec.onnx")


del _Type, _os, _getenv, _cast

__all__ = [x for x in locals() if not x.startswith("_")]
