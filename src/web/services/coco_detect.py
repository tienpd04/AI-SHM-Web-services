from typing import cast

import cv2
import numpy as np
from numpy.typing import NDArray

from src.config.engine import ModelName

from .engine import inference
from .improc import letterbox


class _CocoYolo11:
    def __init__(self, conf_thresh = 0.5, iou_thresh = 0.45):
        self.conf_thresh = conf_thresh
        self.iou_thresh = iou_thresh

    def run(self, image: NDArray):
        img, padding = self.preprocess(image)
        output = inference(ModelName.COCO_YOLO11, img)[0]
        output = self.postprocess(output, image, padding)
        return output

    def preprocess(self, img):
        img, padding = letterbox(img, new_shape=(640, 640))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB, dst=img)
        img = img.astype(np.float32)
        img /= 255.0
        img = np.expand_dims(img, axis=0)
        img = np.transpose(img, (0, 3, 1, 2))

        return img, padding

    def postprocess(self, output: NDArray, image: NDArray, padding: tuple[int, int]):
        output = cast(NDArray, output[0]).transpose()
        boxes = output[:, :4]
        scores = output[:, 4:]
        class_score = np.max(scores, axis=1)
        class_id = np.argmax(scores, axis=1)
        keep = class_score >= self.conf_thresh
        class_id = class_id[keep].copy() # The indexes is not a range, copy is better
        class_score = class_score[keep].copy()
        boxes = boxes[keep].copy()
        boxes[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
        boxes[:, 1] = boxes[:, 1] - boxes[:, 3] / 2

        idxs = cv2.dnn.NMSBoxes(boxes, class_score, self.conf_thresh, self.iou_thresh)
        boxes = boxes[idxs].copy() # The indexes is not a range, copy is better
        class_id: NDArray = class_id[idxs].copy()
        class_score = class_score[idxs].copy()

        boxes[:, 0] -= padding[1]
        boxes[:, 1] -= padding[0]
        boxes *= (max(image.shape[:2])) / 640

        ret = np.hstack((boxes, class_score.reshape((-1, 1)), class_id.reshape(-1, 1).astype(np.float32)))
        return ret


_coco_detector = _CocoYolo11()

def coco_detect(img: NDArray) -> NDArray:
    return _coco_detector.run(img)