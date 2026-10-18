import os
import time


class _TempUUID(object):
    __slots__ = ('_int',)

    _int: int

    def __init__(self, int_):
        object.__setattr__(self, '_int', int_)

    def __setattr__(self, name, value):
        raise AttributeError(
            f"type object '{self.__class__.__name__}' has no attribute '{name}'")


    @property
    def bytes(self):
        return self._int.to_bytes(16)  # big endian

    def __str__(self):
        return '%032x' % self._int

    def __int__(self):
        return self._int

    def __repr__(self):
        return f"_TempUUID(_int=0x{self.__str__()})"


def tempuuid():
    """Generate a temporary UUID based on a random value and a monotonically increasing nanosecond counter.
    For use exclusively within the local host (localhost) environment.
    Do not use for external components (such as databases, external APIs, API responses, etc.).

    Returns:
        _TempUUID: temporary UUID class instance
    """
    int_ = (int.from_bytes(os.urandom(8)) << 64) | (
        time.monotonic_ns() & 0xffffffffffffffff)
    return _TempUUID(int_)


__all__ = [
    'tempuuid',
]
