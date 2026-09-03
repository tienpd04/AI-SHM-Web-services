import cv2
import numpy as np
from numpy.typing import NDArray

from src.config.engine import ModelName

from .engine import inference
from .improc import letterbox


class _CocoYolo11:

    def run(self, image: NDArray):
        img, padding = self.preprocess(image)
        pred = inference(ModelName.COCO_YOLO11, img)[0]
        pred = self.postprocess(pred, padding)
        return pred

    def preprocess(self, img):
        img, padding = letterbox(img, new_shape=(640, 640))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32)
        img /= 255.0
        img = np.expand_dims(img, axis=0)
        img = np.transpose(img, (0, 3, 1, 2))

        return img, padding

    def postprocess(self, pred: NDArray, padding):
        # TODO
        return pred

_coco_detector = _CocoYolo11()

def coco_detect(img: NDArray) -> NDArray:
    return _coco_detector.run(img)