from __future__ import annotations

import os
import pickle
import secrets
from typing import TYPE_CHECKING, TypeAlias, cast

if TYPE_CHECKING:
    from multiprocessing.shared_memory import SharedMemory
    from numpy.typing import NDArray

import numpy as np

from src.config.engine import STORAGE_DIR, SHM_HEADER_SIZE, ShmTensorSchema
from src.libs.socket_protocol.server import (ASCIIJsonResponse, JSONResponse,
                                             PlainTextResponse, Request,
                                             Response, SocketApplicaltion)
from src.globals_signals import get_shm_lock

from ..core.engine import Engine, InvalidModelName
from ..core.shm import get_shm
from ..utils.logging import logger

# import time

if STORAGE_DIR.isascii():
    FileModeResponse: TypeAlias = JSONResponse
else:
    FileModeResponse: TypeAlias = ASCIIJsonResponse


def _load_shm_input_tensor(tensor_info: dict, shm_nonce: str) -> tuple[NDArray, SharedMemory]:

    tensor_schema = ShmTensorSchema(**tensor_info)
    shm = get_shm(tensor_schema.shm)

    tensor = np.ndarray(shape=tensor_schema.shape,
                        dtype=tensor_schema.dtype)
    lock = get_shm_lock(shm.name)
    if lock.acquire(block=False):
        try:
            buf = shm.buf
            if buf[:SHM_HEADER_SIZE].hex() != shm_nonce:
                raise ValueError(
                    "Invalid SHM header. The SHM may be overwritten.")
            shm_tensor = np.ndarray(shape=tensor_schema.shape,
                                    dtype=tensor_schema.dtype, buffer=buf[tensor_schema.buf_from:])
            tensor[:] = shm_tensor[:]
        finally:
            lock.release()
    else:
        raise RuntimeError(
            "Too many processes or threads accessing SHM simultaneously.")
    return tensor, shm


def _bind_shm_outputs(outputs: list[NDArray], shm: SharedMemory) -> tuple[list[ShmTensorSchema], bytes]:
    shm_nonce = secrets.token_bytes(SHM_HEADER_SIZE)
    shm_buff = shm.buf
    lock = get_shm_lock(shm.name)
    if lock.acquire(block=False):
        try:
            shm_buff[:SHM_HEADER_SIZE] = shm_nonce
            buf_from = SHM_HEADER_SIZE
            tensor_schemas: list[ShmTensorSchema] = []
            for tensor in outputs:
                array = np.ndarray(shape=tensor.shape,
                                dtype=tensor.dtype, buffer=shm_buff[buf_from:])
                array[:] = tensor[:]

                schema = ShmTensorSchema(
                    shape=tensor.shape, dtype=tensor.dtype.name, shm=shm.name, buf_from=buf_from)
                buf_from += array.nbytes
                tensor_schemas.append(schema)
        finally:
            lock.release()
    else:
        raise RuntimeError(
            "Too many processes or threads accessing SHM simultaneously.")
    return tensor_schemas, shm_nonce


def inference(req: Request) -> Response:
    '''
    Inference API

    Return:
    JsonResponse if success
    PlainTextResponse with message if have error
    '''
    try:
        data = req.json()
        assert isinstance(data, dict), ""
    except Exception:
        return PlainTextResponse("Required content as a dict type", 422)

    model_name = data.get('model_name')
    mode = data.get('mode')
    if mode not in ['shm', 'file']:
        return PlainTextResponse(f"Invalid mode: '{mode}'", 422)

    # t1 = time.time()
    try:
        if mode == 'shm':
            shm_nonce = data.get('shm_nonce')
            tensor_info = data.get('input_tensor')
            input_tensor, _ = _load_shm_input_tensor(tensor_info, shm_nonce)

        else:
            filepath = data.get('filepath')
            input_tensor = np.load(filepath)
    except Exception as e:
        return PlainTextResponse(f"Could not load input tensor: {str(e)}", 422)

    if mode == 'shm':
        output_shm_name = data.get('output_shm')
        if output_shm_name is not None:
            try:
                output_shm = get_shm(output_shm_name)
            except Exception:
                return PlainTextResponse(f"Invalid output shm name: '{output_shm}'", 422)
        else:
            logger.warning(
                "Inference with input mode 'shm' without output shm")
            output_shm = None

    engine = cast(Engine, getattr(
        cast(SocketApplicaltion, req.app).state, "engine"))
    try:
        outputs = engine.inference(
            model_name=model_name, input_tensor=input_tensor)
    except InvalidModelName:
        logger.warning("Invalid model name: %s", model_name)
        return PlainTextResponse(f"Invalid model name: {model_name}", 422)
    except Exception as e:
        logger.error("Error during inference: %s", str(e))
        return PlainTextResponse(f"Error while during inference: {e}", 500)

    output_mode = mode
    if output_mode == 'shm':
        if output_shm is None:
            output_mode = 'file'
        else:
            total_size = sum(o.nbytes for o in outputs) + \
                SHM_HEADER_SIZE
            if total_size > output_shm.size:
                logger.warning(
                    "Output SHM not enough size to write the output, expected: %d, shm size: %d. Try to write output with 'file' mode", total_size, output_shm.size)
                output_mode = 'file'

    if output_mode == 'shm':
        try:
            output_schemas, shm_nonce = _bind_shm_outputs(
                outputs=outputs, shm=output_shm)
        except Exception as e:
            logger.error("Could not bind output to shm: shm name '%s', shm size %d. Exception: %s",
                         output_shm.name, output_shm.size, str(e))
            return PlainTextResponse("Could not bind output to shm: shm name '{}', shm size {}. Exception: {}".format(output_shm.name, output_shm.size, str(e)), 500)

        content = {'mode': output_mode, 'outputs': [
            s.original_dict() for s in output_schemas], 'shm_nonce': shm_nonce.hex()}
        return ASCIIJsonResponse(content)
    else:
        filepath = os.path.join(STORAGE_DIR, secrets.token_hex(16) + '.pkl')
        with open(filepath, 'wb') as f:
            pickle.dump(outputs, f)
        content = {'mode': output_mode, 'outputs': {'filepath': filepath}}
        return FileModeResponse(content)


__all__ = [
    "inference",
]
