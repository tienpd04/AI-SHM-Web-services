from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy.typing import NDArray

class InferenceModelMeta(ABC):
    @abstractmethod
    def inference(self, *args, **kwargs) -> list['NDArray']:
        raise NotImplementedError()