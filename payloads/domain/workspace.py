"""Serve a job-scoped lab workspace over the runtime Web UI proxy."""

import asyncio
import json
import secrets
import time
from concurrent.futures import Future
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import urlsplit

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

from .equipment import CommandError, command_from_message


ASSETS = Path(__file__).resolve().parents[1] / "web_assets"
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
CAMERAS = {"overview": "/World/Cameras/Overview", "deck": "/World/Cameras/Deck"}
STALE_SECONDS = 5


class LiveFrames:
    """Exchange one pending command and the latest observed frame between threads."""

    def __init__(self, joints):
        self.joints = joints
        self.lock = Lock()
        self.latest = None
        self.pending = None
        self.last_frame_at = 0.0

    def publish(self, state, images):
        with self.lock:
            self.latest = state, images
            self.last_frame_at = time.monotonic()
            if self.pending and self.pending[0] == state["revision"]:
                self.pending = None

    def read(self):
        with self.lock:
            return self.latest

    def command(self):
        with self.lock:
            return self.pending

    def submit(self, message):
        command = command_from_message(message.get("command"), self.joints)
        revision = message.get("revision")
        with self.lock:
            if self.latest is None or time.monotonic() - self.last_frame_at >= STALE_SECONDS:
                raise CommandError("Waiting for a current Isaac Sim frame.")
            if self.pending or type(revision) is not int or revision != self.latest[0]["revision"]:
                raise CommandError("The controls changed. Check the current state and try again.")
            self.pending = revision + 1, command
            return self.pending[0]


class Workspace:
    def __init__(self, host, port, frames):
        self.frames = frames
        self.key = secrets.token_urlsafe(32)
        self.assets = {path: (mime, (ASSETS / file).read_bytes()) for path, (file, mime) in FILES.items()}
        self.clients = set()
        self.bound_port = Future()
        self.thread = Thread(target=self._run, args=(host, port), name="web-lab-workspace", daemon=True)
        self.thread.start()
        self.port = self.bound_port.result(timeout=10)

    def _run(self, host, port):
        try:
            asyncio.run(self._serve(host, port))
        except Exception as error:
            if not self.bound_port.done():
                self.bound_port.set_exception(error)

    async def _serve(self, host, port):
        self.loop = asyncio.get_running_loop()
        self.stop = asyncio.Event()
        async with serve(self._viewer, host, port, process_request=self._http,
                         max_size=1024, max_queue=4, compression=None, close_timeout=1) as server:
            self.bound_port.set_result(server.sockets[0].getsockname()[1])
            await self.stop.wait()

    def _http(self, _connection, request):
        path = urlsplit(request.path).path
        if request.headers.get("Upgrade", "").lower() == "websocket":
            if path == "/control":
                return None
            return Response(404, "Not found", Headers(), b"")
        if path == "/session.json":
            mime, body = "application/json", json.dumps({"key": self.key}).encode()
        elif path in self.assets:
            mime, body = self.assets[path]
        else:
            return Response(404, "Not found", Headers(), b"")
        headers = Headers({
            "Content-Type": mime,
            "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cross-Origin-Resource-Policy": "same-origin",
        })
        return Response(200, "OK", headers, body)

    async def _viewer(self, connection):
        if len(self.clients) >= 8:
            await connection.close(1013, "Too many viewers")
            return
        self.clients.add(connection)
        try:
            message = self._decode(await asyncio.wait_for(connection.recv(), timeout=5))
            key = message.get("key") if message else None
            if not isinstance(key, str) or not key.isascii() or not secrets.compare_digest(key, self.key):
                await connection.close(1008, "Open the workspace to connect")
                return
            await self._stream(connection)
        except (ConnectionClosed, TimeoutError):
            pass
        finally:
            self.clients.discard(connection)

    @staticmethod
    def _decode(raw):
        if not isinstance(raw, str):
            return None
        try:
            decoded = json.loads(raw)
        except (ValueError, RecursionError):
            return None
        return decoded if isinstance(decoded, dict) else None

    async def _stream(self, connection):
        camera, last = "overview", None
        while not self.stop.is_set():
            latest = self.frames.read()
            if latest:
                state, images = latest
                identity = state["frame"], camera
                if identity != last:
                    metadata = {"type": "frame", "camera": camera, "state": state}
                    await asyncio.wait_for(connection.send(json.dumps(metadata, allow_nan=False)), timeout=2)
                    await asyncio.wait_for(connection.send(images[camera]), timeout=2)
                    last = identity
            try:
                raw = await asyncio.wait_for(connection.recv(), timeout=.12)
            except TimeoutError:
                continue
            message = self._decode(raw)
            if message is not None and message.keys() == {"camera"} and message["camera"] in tuple(CAMERAS):
                camera = message["camera"]
                continue
            try:
                if message is None or message.keys() != {"revision", "command"}:
                    raise CommandError("Choose a workcell control.")
                response = {"type": "accepted", "id": self.frames.submit(message)}
            except CommandError as error:
                response = {"type": "rejected", "message": str(error)}
            await asyncio.wait_for(connection.send(json.dumps(response)), timeout=2)

    def check(self):
        if not self.thread.is_alive():
            raise RuntimeError("The Web Lab workspace listener stopped.")

    def close(self):
        if self.thread.is_alive():
            self.loop.call_soon_threadsafe(self.stop.set)
            self.thread.join(5)
