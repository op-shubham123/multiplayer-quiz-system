"""JSON-lines transport shared by the TCP server and the Tkinter client."""
from __future__ import annotations

import json
import socket
import threading
from typing import Any

MAX_MESSAGE_BYTES = 8192


def encode_message(message: dict[str, Any]) -> bytes:
    data = (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > MAX_MESSAGE_BYTES:
        raise ValueError("Message is too large")
    return data


class JsonConnection:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.send_lock = threading.Lock()
        self._buffer = bytearray()

    def send(self, message: dict[str, Any]) -> None:
        payload = encode_message(message)
        with self.send_lock:
            self.sock.sendall(payload)

    def receive(self) -> dict[str, Any] | None:
        while b"\n" not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                return None
            self._buffer.extend(chunk)
            if len(self._buffer) > MAX_MESSAGE_BYTES:
                raise ValueError("Incoming message too large")
        line, _, remaining = self._buffer.partition(b"\n")
        self._buffer = bytearray(remaining)
        try:
            data = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid JSON message") from exc
        if not isinstance(data, dict):
            raise ValueError("Message must be a JSON object")
        return data

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
