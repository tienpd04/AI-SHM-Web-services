'''
All environment settings can be configured.
'''

import os as _os
from typing import Literal as _Literal
from typing import Type as _Type
from typing import cast as _cast

from .constants import *


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
            return v.lower() in ('1', 'true', 'yes', 'on')  # otherwise is False, no validate
        try:
            v = cast(v)
        except Exception:
            raise _EnvironmentSettingError(
                f"Environment \"{key}\" must be a {cast.__name__}: '{v}'") from None
    return v


LOGS_DIR: str = _getenv("LOGS_DIR", "logs")

NUM_LOG_BACKUP: int = _getenv("NUM_LOG_BACKUP", 10, cast=int)

HOST: str = _getenv("HOST", "0.0.0.0")

PORT: int = _getenv("PORT", 8000, cast=int)

GUNICORN_NUM_WORKERS: int = _getenv("GUNICORN_NUM_WORKERS", 4, cast=int)
if GUNICORN_NUM_WORKERS < 2:
    raise _EnvironmentSettingError(
        "'GUNICORN_NUM_WORKERS' must be greater than 1 for using the engine.")

GUNICORN_WORKER_CONNECTIONS: int = _getenv(
    "GUNICORN_WORKER_CONNECTIONS", 64, cast=int)

GUNICORN_ERROR_LOG_FILE: str = _getenv(
    "GUNICORN_ERROR_LOG_FILE", _os.path.join(LOGS_DIR, "gunicorn-error.log"))

GUNICORN_ACCESS_LOG_FILE: str | None = _getenv("GUNICORN_ACCESS_LOG_FILE")

GUNICORN_LOG_LEVEL: _Literal['error', 'warning', 'info', 'debug'] = {k: k for k in ('error', 'warning', 'info', 'debug')}.get(
    _cast(str, _getenv("GUNICORN_LOG_LEVEL", "info")).lower(), 'info')

GUNICORN_TIMEOUT: int = _getenv("GUNICORN_TIMEOUT", default=300, cast=int)

if GUNICORN_TIMEOUT <= 0:
    raise _EnvironmentSettingError(
        "'GUNICORN_TIMEOUT' must be a positive number")


STORAGE_DIR: str = _getenv("STORAGE_DIR", "/tmp/storage")


ENGINE_UNIX_SOCKET_PATH: str = _getenv(
    "ENGINE_UNIX_SOCKET_PATH", default="/run/appuser/engine.sock", required=True)

# Calculate the maximum value among the INPUT data sizes (in Megabytes) of all engine tasks, then set this value.
RESOURCE_SHM_INPUT_SIZE_MB: int = _getenv(
    "RESOURCE_SHM_INPUT_SIZE_MB", 32, cast=int)

# Calculate the maximum value among the OUTPUT data sizes (in Megabytes) of all engine tasks, then set this value.
RESOURCE_SHM_OUTPUT_SIZE_MB: int = _getenv(
    "RESOURCE_SHM_OUTPUT_SIZE_MB", 32, cast=int)

RESOURCES_MANAGER_LOG_INTERVAL: int = _getenv(
    "RESOURCES_MANAGER_LOG_INTERVAL", 3600, cast=int)

USING_SHM_LOCK: bool = _getenv("USING_SHM_LOCK", True, cast=bool)

# Always False if 'USING_SHM_LOCK' is False
# Use only after a worker process has failed (crashed).
# Restarting the server is necessary if the failed process held a global lock (unlikely).
#    - (The server continues running, but the error occurs repeatedly).
# Set this option to True if you want to automatically detect and release residual locks (locks left by a crash or "death locks").
#   - The server will recover correctly if the 'DEATHLOCK_CHECKING_TIME' parameter (specified below) is configured appropriately.
#   - However, if the configured time is insufficient,
#       and—unfortunately—if the web application's worker processes use the same shared memory (SHM) (*) or if there is uncontrolled code,
#       the shared memory (SHM) could be overwritten.
#       (*) This occurs if the external 'psutil' module is not functioning correctly (used in src/shared.py).
DEATHLOCKS_CHECKING: bool = USING_SHM_LOCK and _getenv("DEATHLOCKS_CHECKING", False, cast=bool)

# Recommendation: Setup this greater than or equal to the config timeout of gunicorn
DEATHLOCK_CHECKING_TIME: float = _getenv(
    "DEATHLOCK_CHECKING_TIME", GUNICORN_TIMEOUT, cast=float)

if DEATHLOCK_CHECKING_TIME <= 0:
    raise _EnvironmentSettingError(
        "'DEATHLOCK_CHECKING_TIME' must be a positive number")

ARC_FACE_MODEL_PATH: str = _getenv(
    'ARC_FACE_MODEL_PATH', "weights/face_extraction.bin")

ARC_FACE_USING_RGB: bool = _getenv('ARC_FACE_USING_RGB', True, cast=bool)

COCO_YOLO11_MODEL_PATH: str = _getenv(
    'COCO_YOLO11_MODEL_PATH', "weights/yolo11n_coco.onnx")

PPOCR_V6_MODEL_PATH: str = _getenv(
    'PPOCR_V6_MODEL_PATH', "weights/PP-OCRv6_medium_rec.onnx")


del _Type, _os, _getenv, _cast, _EnvironmentSettingError

__all__ = [x for x in locals() if not x.startswith("_")]
