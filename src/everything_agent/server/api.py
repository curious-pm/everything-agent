"""The HTTP and WebSocket API, and the built web UI."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field as PydanticField
from starlette.requests import HTTPConnection

from .. import __version__, devices, envfile, logs, mute, paths
from ..conversation.history import History
from ..runtime import Runtime
from ..settings import FIELDS, FIELDS_BY_KEY, Settings
from ..voice import voices
from . import checks, guard
from .auth import MIN_PIN_LENGTH, SESSION_TTL_S, Auth, LockedOut

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
COOKIE = "everything_agent_session"
_TICK_S = 0.1
_MAX_TEXT = 2000
_SHUTDOWN_GRACE_S = 3
_STATE_KEYS = ("session", "phase", "asleep", "listening", "in_turn", "mic_muted", "speaker_muted", "missing", "problem")


class _Pin(BaseModel):
    pin: str = PydanticField(max_length=128)
    current: str = PydanticField("", max_length=128)


class _Text(BaseModel):
    text: str


class _Mute(BaseModel):
    mic: bool | None = None
    speaker: bool | None = None


class _Values(BaseModel):
    values: dict[str, str]


class _Voice(BaseModel):
    id: str = PydanticField(pattern=r"^[A-Za-z0-9-]{8,64}$")
    language: str = ""


class _Devices(BaseModel):
    input: str = ""
    output: str = ""


def _mask(value: str) -> str:
    if not value:
        return ""
    return "•" * len(value) if len(value) <= 8 else "•" * 8 + value[-4:]


def _is_local(host: str) -> bool:
    return host in ("127.0.0.1", "localhost")


def lan_address(port: int) -> str:
    """This machine's address on the local network; connecting a UDP socket sends nothing."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        host = sock.getsockname()[0]
    except OSError:
        host = "127.0.0.1"
    finally:
        sock.close()
    return f"http://{host}:{port}/"


def _robot_model_file(name: str) -> Path | None:
    """Reachy's URDF or one of its meshes, straight from the installed SDK."""
    parts = Path(name).parts
    if not parts or len(parts) > 2 or any(p in ("..", "") or ":" in p for p in parts):
        return None
    try:
        import reachy_mini
    except ImportError:
        return None
    urdf_dir = Path(reachy_mini.__file__).resolve().parent / "descriptions" / "reachy_mini" / "urdf"
    if parts == ("robot.urdf",):
        path = urdf_dir / "robot_no_collision.urdf"
    elif len(parts) == 2 and parts[0] == "assets":
        path = urdf_dir / "assets" / parts[1]
    else:
        return None
    return path if path.is_file() else None


def _keeps_saved_secret(key: str, value: str) -> bool:
    return not value and FIELDS_BY_KEY[key].kind == "secret"


def build_app(runtime: Runtime) -> FastAPI:
    settings = runtime.settings
    auth = Auth(settings.web_pin_hash, settings.web_pin, settings.desktop_token, settings.env_path)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    if settings.desktop:
        app.add_middleware(
            CORSMiddleware, allow_origins=list(guard.DESKTOP_ORIGINS), allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type"],
        )
    app.add_middleware(guard.Guard, hosts=guard.known_hosts(settings.web_allowed_hosts))

    def is_signed_in(connection: HTTPConnection) -> bool:
        return auth.bearer_ok(connection.headers.get("authorization")) or auth.session_ok(connection.cookies.get(COOKIE))

    def signed_in(request: Request) -> None:
        if not is_signed_in(request):
            raise HTTPException(status_code=401, detail="not signed in")

    def start_session(response: Response, session: str) -> None:
        response.set_cookie(COOKIE, session, httponly=True, samesite="strict", max_age=SESSION_TTL_S)

    def conversation():
        if runtime.conversation is None or runtime.state != "running":
            raise HTTPException(status_code=503, detail="Reachy isn't ready yet")
        return runtime.conversation

    def env_path() -> Path:
        if runtime.settings.env_path is None:
            raise HTTPException(status_code=500, detail="no settings file to save to")
        return runtime.settings.env_path

    @app.get("/api/auth")
    async def get_auth(request: Request) -> dict[str, Any]:
        return {"signed_in": is_signed_in(request), "pin_set": auth.pin_set}

    @app.post("/api/auth/login")
    async def login(body: _Pin, request: Request, response: Response) -> dict[str, Any]:
        client = request.client.host if request.client else "unknown"
        try:
            session = await asyncio.to_thread(auth.login, body.pin, client)
        except LockedOut as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        if session is None:
            raise HTTPException(status_code=401, detail="That PIN isn't right.")
        start_session(response, session)
        return {"signed_in": True}

    @app.post("/api/auth/pin")
    async def set_pin(body: _Pin, request: Request, response: Response) -> dict[str, Any]:
        had_pin = auth.pin_set
        from_desktop = auth.bearer_ok(request.headers.get("authorization"))
        if had_pin:
            signed_in(request)
            if not from_desktop:
                await check_current_pin(body.current, request)
        elif runtime.settings.desktop and not from_desktop:
            raise HTTPException(status_code=403, detail="Set the first PIN from the Everything Agent window.")
        pin = body.pin.strip()
        if len(pin) < MIN_PIN_LENGTH:
            raise HTTPException(status_code=400, detail=f"Use at least {MIN_PIN_LENGTH} characters.")
        start_session(response, auth.set_pin(pin))
        logger.info("The web page's PIN was %s", "changed" if had_pin else "set")
        return {"signed_in": True}

    async def check_current_pin(current: str, request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        try:
            ok = await asyncio.to_thread(auth.login, current, client) is not None
        except LockedOut as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        if not ok:
            raise HTTPException(status_code=403, detail="The current PIN isn't right.")

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response) -> dict[str, Any]:
        auth.logout(request.cookies.get(COOKIE))
        response.delete_cookie(COOKIE)
        return {"signed_in": False}

    api = Depends(signed_in)

    @app.get("/api/info", dependencies=[api])
    async def info() -> dict[str, Any]:
        return {
            "version": __version__,
            "desktop": runtime.settings.desktop,
            "address": lan_address(runtime.settings.web_port),
            "lan": not _is_local(runtime.settings.web_host),
            "pin_set": auth.pin_set,
        }

    @app.get("/api/status", dependencies=[api])
    async def status() -> dict[str, Any]:
        return runtime.status()

    @app.post("/api/say", dependencies=[api])
    async def say(body: _Text) -> dict[str, Any]:
        text = body.text.strip()
        if not text or len(text) > _MAX_TEXT:
            raise HTTPException(status_code=400, detail=f"Type between 1 and {_MAX_TEXT} characters.")
        await conversation().say(text)
        return {"queued": True}

    @app.post("/api/mute", dependencies=[api])
    async def set_mute(body: _Mute) -> dict[str, bool]:
        state = mute.set_mute(mic=body.mic, speaker=body.speaker)
        return {"mic": state.mic, "speaker": state.speaker}

    @app.post("/api/sleep", dependencies=[api])
    async def sleep() -> dict[str, Any]:
        await conversation().sleep()
        return {"asleep": True}

    @app.post("/api/wake", dependencies=[api])
    async def wake() -> dict[str, Any]:
        await conversation().wake()
        return {"asleep": False}

    @app.get("/api/conversation", dependencies=[api])
    async def get_conversation(limit: int = 60) -> dict[str, Any]:
        history = runtime.conversation.history if runtime.conversation is not None else History("")
        return {"messages": history.lines(max(1, min(limit, 200)))}

    @app.delete("/api/conversation", dependencies=[api])
    async def clear_conversation() -> dict[str, Any]:
        if runtime.conversation is not None:
            runtime.conversation.clear_history()
        else:
            History("").clear()
        runtime.events.publish("cleared")
        return {"cleared": True}

    @app.get("/api/settings", dependencies=[api])
    async def get_settings() -> dict[str, Any]:
        saved = envfile.read_values(runtime.settings.env_path)
        fields = []
        for f in FIELDS:
            raw = (saved.get(f.key) or os.environ.get(f.key) or "").strip()
            fields.append({
                "key": f.key, "label": f.label, "kind": f.kind, "hint": f.hint, "required": f.required,
                "is_set": bool(raw), "value": _mask(raw) if f.kind == "secret" else (raw or f.default),
                "default": f.default,
            })
        return {"fields": fields, "missing": runtime.settings.missing()}

    @app.post("/api/settings", dependencies=[api])
    async def save_settings(body: _Values) -> dict[str, Any]:
        unknown = sorted(set(body.values) - set(FIELDS_BY_KEY))
        if unknown:
            raise HTTPException(status_code=400, detail=f"Can't change {', '.join(unknown)} here.")
        values = {k: v.strip() for k, v in body.values.items()}
        values = {k: v for k, v in values.items() if not _keeps_saved_secret(k, v)}
        envfile.set_values(env_path(), values)
        logger.info("Settings saved: %s", ", ".join(sorted(values)) or "nothing")
        runtime.reload()
        return {"saved": sorted(values)}

    @app.get("/api/voices", dependencies=[api])
    async def list_voices() -> dict[str, Any]:
        key = runtime.settings.cartesia_api_key
        if not key:
            raise HTTPException(status_code=400, detail="Add the Cartesia key in Advanced settings first.")
        current_id = runtime.settings.voice_id
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                library = await voices.library(client, key)
                current = next((v for v in library if v["id"] == current_id), None)
                if current is None and current_id:
                    current = await voices.voice(client, key, current_id)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Couldn't reach Cartesia ({type(exc).__name__}).") from exc
        return {"current": current or {"id": current_id, "name": "", "language": "", "gender": ""}, "voices": library}

    @app.post("/api/voices/sample", dependencies=[api])
    async def voice_sample(body: _Voice) -> Response:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                audio = await voices.sample(
                    client, runtime.settings.cartesia_api_key, runtime.settings.tts_model, body.id, body.language,
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Couldn't get a sample ({type(exc).__name__}).") from exc
        return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})

    @app.post("/api/voices/use", dependencies=[api])
    async def use_voice(body: _Voice) -> dict[str, Any]:
        envfile.set_value(env_path(), "CARTESIA_VOICE_ID", body.id)
        runtime.settings = Settings.load(runtime.settings.env_path)
        if runtime.conversation is not None:
            runtime.conversation.set_voice(body.id)
        return {"saved": True}

    @app.get("/api/checks", dependencies=[api])
    async def get_checks() -> dict[str, Any]:
        return {"checks": await checks.run_checks(runtime.settings, runtime.status())}

    @app.get("/api/logs", dependencies=[api])
    async def get_logs(name: str = "app", lines: int = 300) -> dict[str, Any]:
        if name not in logs.LOG_FILES:
            raise HTTPException(status_code=404, detail="no such log")
        text = await asyncio.to_thread(logs.tail, name, max(10, min(lines, 2000)))
        return {"name": name, "text": text}

    @app.post("/api/logs/open", dependencies=[api])
    async def open_logs() -> dict[str, Any]:
        if not runtime.settings.desktop:
            raise HTTPException(status_code=404, detail="Only in the desktop app.")
        folder = paths.log_dir()
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
        return {"opened": True}

    @app.get("/api/devices", dependencies=[api])
    async def get_devices() -> dict[str, Any]:
        saved = envfile.read_values(runtime.settings.env_path)
        error = ""
        try:
            found = await asyncio.to_thread(devices.list_devices_safely)
        except Exception as exc:
            logger.exception("Listing devices failed")
            found, error = {"inputs": [], "outputs": []}, f"{type(exc).__name__}: {exc}"
        return {
            **found,
            "error": error,
            "selected": {"input": saved.get(devices.INPUT_SETTING, ""), "output": saved.get(devices.OUTPUT_SETTING, "")},
            "can_choose": runtime.restart_process is not None,
        }

    @app.post("/api/devices", dependencies=[api])
    async def set_devices(body: _Devices) -> dict[str, Any]:
        if runtime.restart_process is None:
            raise HTTPException(status_code=400, detail="Reachy uses the robot's own microphone and speaker here.")
        envfile.set_values(env_path(), {devices.INPUT_SETTING: body.input.strip(), devices.OUTPUT_SETTING: body.output.strip()})
        logger.info("New microphone or speaker chosen; restarting")
        asyncio.get_running_loop().call_later(0.5, runtime.restart_process)
        return {"restarting": True}

    async def token_sent_first(websocket: WebSocket) -> bool:
        try:
            first = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            return auth.token_ok(str(json.loads(first).get("token") or ""))
        except (asyncio.TimeoutError, ValueError, AttributeError, WebSocketDisconnect, RuntimeError):
            return False

    @app.websocket("/api/events")
    async def events(websocket: WebSocket) -> None:
        await websocket.accept()
        if not (is_signed_in(websocket) or await token_sent_first(websocket)):
            await websocket.close(code=4401)
            return
        seq = runtime.events.latest
        last_state: dict[str, Any] | None = None
        last_levels: tuple[float, float] | None = None
        try:
            while True:
                live = runtime.status()
                state = {key: live.get(key) for key in _STATE_KEYS}
                if state != last_state:
                    await websocket.send_json({"type": "state", **state})
                    last_state = state
                levels = (round(float(live.get("mic_level") or 0.0), 3), round(float(live.get("speaker_level") or 0.0), 3))
                if levels != last_levels:
                    await websocket.send_json({"type": "levels", "mic": levels[0], "speaker": levels[1]})
                    last_levels = levels
                seq, fresh = runtime.events.since(seq)
                for event in fresh:
                    await websocket.send_json({"type": "event", **event})
                await asyncio.sleep(_TICK_S)
        except (WebSocketDisconnect, RuntimeError):
            return
        except Exception:
            logger.debug("Live feed ended", exc_info=True)

    @app.get("/robot/{name:path}")
    async def robot_model(name: str) -> FileResponse:
        path = _robot_model_file(name)
        if path is None:
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(path, headers={"Cache-Control": "max-age=86400"})

    if (WEB_DIR / "index.html").is_file():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    else:
        @app.get("/")
        async def no_ui() -> Response:
            return Response(
                "The web UI isn't built. Run `npm run build` in ui/ (see README).", media_type="text/plain",
            )

    return app


class _Server(uvicorn.Server):
    """Leaves Ctrl+C to the app, which stops the robot cleanly."""

    @contextlib.contextmanager
    def capture_signals(self):  # type: ignore[override]
        yield


async def serve(runtime: Runtime, stop: asyncio.Event) -> None:
    settings = runtime.settings
    config = uvicorn.Config(
        build_app(runtime), host=settings.web_host, port=settings.web_port, log_level="warning",
        timeout_graceful_shutdown=_SHUTDOWN_GRACE_S, proxy_headers=False,
    )
    server = _Server(config)
    address = f"http://127.0.0.1:{settings.web_port}/" if _is_local(settings.web_host) else lan_address(settings.web_port)
    logger.info("Web page: %s", address)

    async def run_server() -> None:
        try:
            await server.serve()
        except SystemExit:
            logger.error("The web page couldn't start on port %d; is something else using it?", settings.web_port)

    task = asyncio.create_task(run_server())
    stopper = asyncio.create_task(stop.wait())
    try:
        await asyncio.wait([task, stopper], return_when=asyncio.FIRST_COMPLETED)
    finally:
        stopper.cancel()
        server.should_exit = True
        with contextlib.suppress(Exception):
            await task
