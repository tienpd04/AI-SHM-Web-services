from __future__ import annotations

import os
import pickle
import secrets
from typing import TYPE_CHECKING, TypeAlias, cast

if TYPE_CHECKING:
    from multiprocessing.shared_memory import SharedMemory
    from numpy.typing import NDArray

import numpy as np

from src.config.engine import STORAGE_DIR, ShmTensorSchema
from src.libs.socket_protocol.server import (ASCIIJsonResponse, JSONResponse,
                                             PlainTextResponse, Request,
                                             Response, SocketApplicaltion)
from src.libs.misc.np_utils import ndarray_sum_hash, list_ndarray_sum_hash

from ..core.engine import Engine, InvalidModelName
from ..core.shm import get_shm
from ..utils.logging import logger

# import time

if STORAGE_DIR.isascii():
    FileModeResponse: TypeAlias = JSONResponse
else:
    FileModeResponse: TypeAlias = ASCIIJsonResponse


def _load_shm_input_tensor(tensor_info: dict) -> tuple[NDArray, SharedMemory]:

    tensor_schema = ShmTensorSchema(**tensor_info)
    shm = get_shm(tensor_schema.shm)
    buffer = shm.buf if tensor_schema.buf_from == 0 else shm.buf[tensor_schema.buf_from:]
    # Using shm buffer, no need to copy
    # tensor = np.ndarray(shape=tensor_schema.shape,
    #                     dtype=tensor_schema.dtype, buffer=buffer)
    tensor = np.ndarray(shape=tensor_schema.shape,
                            dtype=tensor_schema.dtype, buffer=buffer).copy()
    return tensor, shm


def _bind_ouputs(outputs: list[NDArray], shm: SharedMemory) -> list[ShmTensorSchema]:

    shm_buff: memoryview = shm.buf
    buf_from = 0
    tensor_schemas: list[ShmTensorSchema] = []
    for tensor in outputs:
        buf = shm_buff if buf_from == 0 else shm_buff[buf_from:]
        array = np.ndarray(shape=tensor.shape, dtype=tensor.dtype, buffer=buf)
        array[:] = tensor[:]

        schema = ShmTensorSchema(
            shape=tensor.shape, dtype=tensor.dtype.name, shm=shm.name, buf_from=buf_from)
        buf_from += array.nbytes
        tensor_schemas.append(schema)

    return tensor_schemas


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
            tensor_info = data.get('input_tensor')
            input_tensor, _ = _load_shm_input_tensor(tensor_info)

        else:
            filepath = data.get('filepath')
            input_tensor = np.load(filepath)
    except Exception as e:
        return PlainTextResponse(f"Could not load input tensor: {str(e)}", 422)

    if mode == 'shm':
        input_hash = data.get('input_hash')
        if ndarray_sum_hash(input_tensor).hexdigest() != input_hash:
            return PlainTextResponse(f"Invalid input hash. The SHM may be overwritten.")
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
            total_size = sum(o.nbytes for o in outputs)
            if total_size > output_shm.size:
                logger.warning(
                    "Output SHM not enough size to write the output, expected: %d, shm size: %d. Try to write output with 'file' mode", total_size, output_shm.size)
                output_mode = 'file'

    if output_mode == 'shm':
        outputs_hash = list_ndarray_sum_hash(outputs)
        try:
            output_schemas = _bind_ouputs(outputs=outputs, shm=output_shm)
        except Exception as e:
            logger.error("Could not bind output to shm: shm name '%s', shm size %d. Exception: %s",
                         output_shm.name, output_shm.size, str(e))
            return PlainTextResponse("Could not bind output to shm: shm name '{}', shm size {}. Exception: {}".format(output_shm.name, output_shm.size, str(e)), 500)

        content = {'mode': output_mode, 'outputs': [
            s.original_dict() for s in output_schemas], 'outputs_hash': outputs_hash.hexdigest()}
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
