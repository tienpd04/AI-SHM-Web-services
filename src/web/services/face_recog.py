import cv2
import numpy as np
from numpy.typing import NDArray

from src.config.engine import ModelName
from src.config.settings import ARC_FACE_USING_RGB

from .engine import inference
from .improc import letterbox


class _ArcFace:
    def __init__(self, rgb):
        self.rgb = rgb

    def run(self, face: NDArray, keep_dim: bool = True):
        img = self.preprocess(face)
        embedding = inference(ModelName.ARC_FACE, img)[0]
        if keep_dim:
            return embedding.flatten()
        return embedding.flatten()[None]

    def preprocess(self, img):
        img, _ = letterbox(img, new_shape=(112, 112))
        if self.rgb:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32)
        img = (img / 255.0 - 0.5) * 2.0
        img = np.expand_dims(img, axis=0)
        img = np.transpose(img, (0, 3, 1, 2))
        return img


_arc_face = _ArcFace(ARC_FACE_USING_RGB)


def face_recog(img: NDArray, keep_dim: bool = True) -> NDArray:
    return _arc_face.run(img, keep_dim)
