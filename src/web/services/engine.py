import os
import pickle
import secrets
from multiprocessing.shared_memory import SharedMemory
from typing import cast

import numpy as np
from numpy.typing import NDArray

from src.config.engine import ENGINE_SOCKET_ADDRESS as ADDRESS
from src.config.engine import ENGINE_SOCKET_FAMILY as SOCKET_FAMILY
from src.config.engine import ENGINE_SOCKET_KIND as SOCKET_KIND
from src.config.engine import STORAGE_DIR
from src.config.engine import EngineSocketAPI as SocketAPI
from src.config.engine import ShmTensorSchema
from src.libs.socket_protocol.client.exceptions import (RequestException,
                                                        StatusCodeError)
from src.libs.socket_protocol.client.requests import request
from src.web.core.logging import logger

from .resources import get_input_shm, get_output_shm


class _EnigneTaskCounter:
    __slots__ = ('_shm', '_file')
    _shm: int
    _file: int

    def __init__(self):
        self._shm = 0
        self._file = 0

    def increase_shm(self):
        self._shm += 1

    def increase_file(self):
        self._file += 1

    @property
    def shm(self) -> int:
        return self._shm

    @property
    def file(self) -> int:
        return self._file

    @property
    def total(self):
        return self._shm + self._file


# For each web application worker, not for all
_task_counter = _EnigneTaskCounter()


def engine_health_check(raise_exp=True, timeout=10) -> bool:
    try:
        res = request(ADDRESS, SocketAPI.HEALTH_CHECK,
                      address_family=SOCKET_FAMILY, socket_kind=SOCKET_KIND, timeout=timeout)
        res.raise_for_status()
    except Exception:
        if raise_exp:
            raise
        return False

    return True


def _load_ouputs_from_file(filepath):
    try:
        with open(filepath, 'rb') as f:
            output_tensors = pickle.load(f)
        return output_tensors

    finally:
        try:
            os.remove(filepath)
        except Exception:
            pass


def _load_outputs(response_dict: dict, output_shm: SharedMemory) -> list[NDArray]:

    mode = response_dict.get("mode")
    outputs: list | dict = response_dict.get("outputs")

    if mode == "shm":
        list_outputs: list[NDArray] = []
        for tensor_info in outputs:
            tensor_schema = ShmTensorSchema(**tensor_info)
            if tensor_schema.shm != output_shm.name:
                raise RequestException(
                    f"Invalid output SHM name, expected: '{output_shm.name}', actual: '{tensor_schema.shm}'")
            buf = output_shm.buf if tensor_schema.buf_from == 0 else output_shm.buf[
                tensor_schema.buf_from:]
            output_tensor = np.ndarray(
                # May be does not need to copy
                shape=tensor_schema.shape, dtype=tensor_schema.dtype, buffer=buf).copy()
            list_outputs.append(output_tensor)

        return list_outputs

    elif mode == "file":
        filepath = outputs.get('filepath')
        return _load_ouputs_from_file(filepath)


def _inference_from_file(model_name: str, tensor_file_path: str, timeout: float = None) -> list[NDArray]:
    content = {'model_name': model_name,
               "mode": "file", "filepath": tensor_file_path}
    try:
        res = request(ADDRESS, SocketAPI.INFERENCE, data=content,
                      address_family=SOCKET_FAMILY, socket_kind=SOCKET_KIND, ensure_ascii=True, timeout=timeout)
        res.raise_for_status()
        response_dict = res.json()
        assert isinstance(response_dict, dict), "Content return must be a dict"

    except StatusCodeError as e:
        try:
            msg = res.text
        except Exception:
            msg = ''
        raise RequestException(
            f"Request failed with status code {res.status_code}: {msg}") from e
    except Exception as e:
        logger.error(
            "Failed to request inference from engine with exception: %s", str(e))
        # logger.error(traceback.format_exc())
        raise

    # Inferece from file always return 'file' mode
    filepath = cast(dict, response_dict.get('outputs')).get("filepath")
    outputs = _load_ouputs_from_file(filepath)

    return outputs


def _log_engine_tasks_interval():
    total = _task_counter.total
    if total and total % 100 == 0:
        logger.info("[Interval Log] Engine tasks for web application worker: total %d, shm %d, file %d",
                    total, _task_counter.shm, _task_counter.file)


def inference(model_name: str, input_tensor: NDArray, timeout: float = None) -> list[NDArray]:
    """Request inferece to engine via shared memory or file
    """

    using_shm = False
    input_shm = get_input_shm()
    output_shm = get_output_shm()

    if input_shm is None or input_shm.size < input_tensor.nbytes:
        logger.warning(
            "Failed to acquire shared memory with size %d, try request to engine with 'file' mode", input_tensor.nbytes)
    else:
        using_shm = True

    if not using_shm:
        _task_counter.increase_file()
        _log_engine_tasks_interval()
        file_path = os.path.join(STORAGE_DIR, secrets.token_hex(16) + ".npy")
        np.save(file_path, input_tensor)
        try:
            ret = _inference_from_file(model_name, file_path, timeout=timeout)
        finally:
            try:
                os.remove(file_path)
            except Exception:
                pass
        return ret

    else:
        _task_counter.increase_shm()
        _log_engine_tasks_interval()
        try:
            array = np.ndarray(shape=input_tensor.shape,
                               dtype=input_tensor.dtype, buffer=input_shm.buf)
            array[:] = input_tensor[:]
            tensor_content = ShmTensorSchema(
                shape=input_tensor.shape, dtype=input_tensor.dtype.name, shm=input_shm.name).original_dict()
            content = {'model_name': model_name,
                       'input_tensor': tensor_content, 'mode': 'shm'}
            if output_shm is not None:
                content['output_shm'] = output_shm.name

            res = request(ADDRESS, SocketAPI.INFERENCE, data=content,
                          address_family=SOCKET_FAMILY, socket_kind=SOCKET_KIND, ensure_ascii=True, timeout=timeout)
            res.raise_for_status()
            response_dict = res.json()
            assert isinstance(
                response_dict, dict), "Content return must be a dict"
            outputs = _load_outputs(response_dict, output_shm)
            return outputs
        except StatusCodeError as e:
            try:
                msg = res.text
            except Exception:
                msg = ''
            raise RequestException(
                f"Request failed with status code {res.status_code}: {msg}") from e
