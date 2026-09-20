import cv2
import numpy as np
from numpy.typing import NDArray

from src.config.engine import ModelName

from .engine import inference


class _PPOCR_V6:

    def run(self, image: NDArray):
        img = self.preprocess(image)
        preds = inference(ModelName.PPOCR_V6, img)
        return self.postprocess(preds)

    def preprocess(self, image: NDArray):
        height, width = image.shape[:2]
        new_height = 48
        new_width = int((width * new_height) / height)
        img = cv2.resize(image, dsize=(new_width, new_height))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB, dst=img)
        img = img.astype(np.float32)
        img /= 255.0
        img -= 0.5
        img *= 2.0
        img = np.expand_dims(img, axis=0)
        img = np.transpose(img, (0, 3, 1, 2))

        return img

    def postprocess(self, preds):
        # TODO
        return preds

_ppocr = _PPOCR_V6()

def ocr(img: NDArray) -> NDArray:
    return _ppocr.run(img)