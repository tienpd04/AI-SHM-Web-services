from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy.typing import NDArray

from libs.models.onnxinference import (SingleInputOnnxInference,
                                       SingleInputOutputOnnxInference)
from src.config.engine import ModelName
from src.config.settings import (ARC_FACE_MODEL_PATH, COCO_YOLO11_MODEL_PATH,
                                 PPOCR_V6_MODEL_PATH)


class InvalidModelName(ValueError):
    pass

class Engine:

    def __init__(self):
        CPU_COUNT = os.cpu_count()
        # arc_face =
        self.face_recog_model = SingleInputOutputOnnxInference(
            ARC_FACE_MODEL_PATH, intra_op_num_threads=CPU_COUNT, inter_op_num_threads=1)
        self.coo_detect_model = SingleInputOnnxInference(
            COCO_YOLO11_MODEL_PATH, intra_op_num_threads=CPU_COUNT, inter_op_num_threads=1)
        self.ocr_model = SingleInputOnnxInference(
            PPOCR_V6_MODEL_PATH, intra_op_num_threads=CPU_COUNT, inter_op_num_threads=1)

    def cleanup(self):
        pass

    def inference(self, model_name: str, input_tensor: 'NDArray') -> list['NDArray']:
        match model_name:
            case ModelName.ARC_FACE:
                return self.face_recog_model.inference(input_tensor=input_tensor)

            case ModelName.COCO_YOLO11:
                return self.coo_detect_model.inference(input_tensor=input_tensor)

            case ModelName.PPOCR_V6:
                return self.ocr_model.inference(input_tensor=input_tensor)

            case _:
                raise InvalidModelName(f"Model name not found: '{model_name}")
