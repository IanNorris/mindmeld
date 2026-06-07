"""Minimal, dependency-free WebSocket (RFC 6455) helpers for the stdlib server.

Only what Mind Meld needs: the opening handshake plus unmasked server->client
frames and masked client->server frame decoding. Frames are small JSON text
messages, so we read them whole rather than streaming.
"""

from __future__ import annotations

import base64
import hashlib
import struct

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA


def accept_key(sec_websocket_key: str) -> str:
    """Compute the Sec-WebSocket-Accept response value."""
    digest = hashlib.sha1((sec_websocket_key + _GUID).encode()).digest()
    return base64.b64encode(digest).decode()


def handshake_response(sec_websocket_key: str) -> bytes:
    return (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept_key(sec_websocket_key)}\r\n\r\n"
    ).encode()


def _recv_n(sock, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except OSError:
            return None
        if not chunk:
            return None
        buf += chunk
    return buf


def send(sock, data, opcode: int = OP_TEXT) -> None:
    """Send a single unmasked WebSocket frame (server -> client)."""
    if isinstance(data, str):
        data = data.encode()
    header = bytearray([0x80 | opcode])
    n = len(data)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += struct.pack("!H", n)
    else:
        header.append(127)
        header += struct.pack("!Q", n)
    sock.sendall(bytes(header) + data)


def recv(sock) -> tuple[int, bytes] | None:
    """Read one client frame. Returns (opcode, payload) or None on close/error."""
    head = _recv_n(sock, 2)
    if not head:
        return None
    b0, b1 = head[0], head[1]
    opcode = b0 & 0x0F
    masked = b1 & 0x80
    length = b1 & 0x7F
    if length == 126:
        ext = _recv_n(sock, 2)
        if ext is None:
            return None
        length = struct.unpack("!H", ext)[0]
    elif length == 127:
        ext = _recv_n(sock, 8)
        if ext is None:
            return None
        length = struct.unpack("!Q", ext)[0]
    mask = _recv_n(sock, 4) if masked else b""
    if masked and mask is None:
        return None
    payload = _recv_n(sock, length) if length else b""
    if payload is None:
        return None
    if masked:
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    return opcode, payload
