"""Turns away requests meant for another site: DNS rebinding, cross-site posts and oversized bodies."""

from __future__ import annotations

import ipaddress
import json
import socket
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit

MAX_BODY_BYTES = 256 * 1024
DESKTOP_ORIGINS = ("tauri://localhost", "http://tauri.localhost", "https://tauri.localhost")
_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


def known_hosts(extra: tuple[str, ...] = ()) -> set[str]:
    name = socket.gethostname().lower()
    return {"localhost", name, f"{name}.local", *(h.lower() for h in extra)}


def _hostname(host: str) -> str:
    if host.startswith("["):
        return host[1:host.find("]")]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def host_allowed(host: str, names: set[str]) -> bool:
    name = _hostname(host).lower()
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return name in names


def origin_allowed(origin: str, host: str) -> bool:
    return origin in DESKTOP_ORIGINS or urlsplit(origin).netloc.lower() == host.lower()


class Guard:
    def __init__(self, app: Callable, hosts: set[str]) -> None:
        self.app = app
        self.hosts = hosts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        host = headers.get("host", "")
        if not host_allowed(host, self.hosts):
            await _refuse(scope, send, 421, "This page isn't served under that name.")
            return
        origin = headers.get("origin")
        changes_something = scope["type"] == "websocket" or scope["method"] not in _SAFE_METHODS
        if origin and changes_something and not origin_allowed(origin, host):
            await _refuse(scope, send, 403, "Requests from other sites aren't allowed.")
            return
        if scope["type"] == "http":
            if int(headers.get("content-length") or 0) > MAX_BODY_BYTES:
                await _refuse(scope, send, 413, "Request too large.")
                return
            receive = _limited(receive)
        await self.app(scope, receive, send)


def _limited(receive: Receive) -> Receive:
    seen = 0

    async def wrapped() -> dict[str, Any]:
        nonlocal seen
        message = await receive()
        seen += len(message.get("body", b""))
        if seen > MAX_BODY_BYTES:
            return {"type": "http.disconnect"}
        return message

    return wrapped


async def _refuse(scope: Scope, send: Send, status: int, detail: str) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 4000 + status})
        return
    body = json.dumps({"detail": detail}).encode()
    await send({"type": "http.response.start", "status": status, "headers": [
        (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
    ]})
    await send({"type": "http.response.body", "body": body})
