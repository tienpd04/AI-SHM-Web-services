import os

_protocol_key = os.getenv("SOCKET_PROTOCOL_HEADER_KEY", "").encode()

del os

from hashlib import md5


def _bit_rotate(x: int, mid):
    hi = (x >> mid)
    low = x & ((1 << mid) -1)
    return (low << (128 - mid)) ^ hi

def _make_client_key():
    k1 = 0x378a1a1c5c7f731e7d41492230fb4c6a
    k2 = 0xa53f0ca2f87d72cf17c846787a5e5296
    k3 = 0xd6464703adead4bf8c0d215833eaae82
    k4 = 0x7a7e8ab5346d37b287febecffe65548a

    k = 0
    k ^= _bit_rotate(k1, 79)
    k ^= _bit_rotate(k2, 31)
    k ^= _bit_rotate(k3, 43)
    k ^= _bit_rotate(k4, 97)


    return md5(_protocol_key + k.to_bytes(16)).digest()

def _make_server_key():
    k1 = 0x2966095d8c68e5b9188006987e9acb0f
    k2 = 0x7e02cd28d0822ba0bbecf4cb4eaeccba
    k3 = 0xd6464703adead4bf8c0d215833eaae82
    k4 = 0x694e5ac4048324dc5992aa23d1b648c5

    k = 0
    k ^= _bit_rotate(k1, 83)
    k ^= _bit_rotate(k2, 37)
    k ^= _bit_rotate(k3, 53)
    k ^= _bit_rotate(k4, 71)


    return md5(_protocol_key + k.to_bytes(16)).digest()

_client_key = _make_client_key()

_server_key = _make_server_key()

del md5, _bit_rotate, _make_client_key, _make_server_key

__all__ = ['_client_key', '_server_key']

