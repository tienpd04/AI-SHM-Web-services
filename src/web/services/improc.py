import cv2
import numpy as np

_EPSILON = 0.1

def letterbox(img: np.ndarray, new_shape: tuple[int, int] = (640, 640)) -> tuple[np.ndarray, tuple[int, int]]:
    """Resize and reshape images while maintaining aspect ratio by adding padding.

    Args:
        img (np.ndarray): Input image to be resized.
        new_shape (tuple[int, int]): Target shape (height, width) for the image.

    Returns:
        img (np.ndarray): Resized and padded image.
        pad (tuple[int, int]): Padding values (top, left) applied to the image.
    """
    shape = img.shape[:2]  # current shape [height, width]

    # Scale ratio (new / old)
    r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

    # Compute padding
    new_unpad = round(shape[1] * r), round(shape[0] * r)
    dw, dh = (new_shape[1] - new_unpad[0]) / 2, (new_shape[0] - new_unpad[1]) / 2  # wh padding

    if shape[::-1] != new_unpad:  # resize
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = round(dh - _EPSILON), round(dh + _EPSILON)
    left, right = round(dw - _EPSILON), round(dw + _EPSILON)
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114))

    return img, (top, left)
