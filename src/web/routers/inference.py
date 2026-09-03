import time
# from src.web.services.engine import inference
import traceback
from typing import Annotated, Literal

import cv2
import numpy as np
from fastapi import APIRouter, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from src.web.core.logging import rq_log_error, rq_log_info
from src.web.services.coco_detect import coco_detect
from src.web.services.face_recog import face_recog
from src.web.services.ppocr import ocr

router = APIRouter()


@router.get("/api/v1/inference")
async def inference_api(request: Request, model: Annotated[Literal['arc', 'ocr', 'coco'], Query()] = None):

    t1 = time.perf_counter()
    try:
        if model == 'arc':
            input_tensor = cv2.imread('images/face/face.png')
            face_recog(input_tensor)
        elif model == 'ocr':
            input_tensor = cv2.imread('images/text/short_text.png')
            ocr(input_tensor)
        else:
            input_tensor = cv2.imread('images/person/person.jpg')
            coco_detect(input_tensor)
    except Exception as e:
        traceback.print_exc()
        rq_log_error(request, f'inference failed: {e}')
        return JSONResponse(status_code=500, content={'success': False, 'message': f'Inference failed: {e}'})
    t2 = time.perf_counter()

    rq_log_info(
        request, f'Inference successfully. Time = {(t2 - t1):.06f} seconds')
    return JSONResponse({'success': True, 'message': 'inference successfully'})


@router.post('/api/v1/inference')
async def inference_from_upload(request: Request, file: UploadFile, model: Annotated[Literal['arc', 'ocr', 'coco'], Query()] = None):
    buffer = await file.read()
    input_tensor = cv2.imdecode(np.frombuffer(
        buffer=buffer, dtype=np.uint8), cv2.IMREAD_COLOR)

    t1 = time.perf_counter()
    try:
        if model == 'arc':
            face_recog(input_tensor)
        elif model == 'ocr':
            ocr(input_tensor)
        else:
            coco_detect(input_tensor)
    except Exception as e:
        traceback.print_exc()
        rq_log_error(request, f'inference failed: {e}')
        return JSONResponse(status_code=500, content={'success': False, 'message': f'Inference failed: {e}'})
    t2 = time.perf_counter()

    rq_log_info(
        request, f'Inference successfully. Time = {(t2 - t1):.06f} seconds')
    return JSONResponse({'success': True, 'message': 'inference successfully'})
