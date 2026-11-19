"""Serve the lab page and its read-only snapshots on one Job UI binding."""

import asyncio
import json
from urllib.parse import urlsplit

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

from .presentation import ASSETS, STYLE, SCRIPTS


MONITOR_PATH = '/monitor/ws'
FILES = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    f'/{STYLE}': (STYLE, 'text/css; charset=utf-8'),
    **{f'/{name}': (name, 'text/javascript; charset=utf-8') for name in SCRIPTS},
}


class LabVisualizer:
    def __init__(self, projection):
        self.projection = projection
        self.server = None
        self.monitors = set()

    async def start(self, host, port):
        self.server = await serve(self._socket_handler, host, port,
                                  process_request=self.http, max_size=8192,
                                  ping_interval=20, close_timeout=2)
        return self.server.sockets[0].getsockname()[1]

    def snapshot(self):
        return json.dumps(self.projection(), allow_nan=False)

    async def _socket_handler(self, connection):
        if len(self.monitors) >= 8:
            await connection.close(code=1013, reason='Too many viewers')
            return
        self.monitors.add(connection)
        try:
            await connection.send(self.snapshot())
            async for _ in connection:
                await connection.close(code=1008, reason='The deck stream is read-only')
                break
        except ConnectionClosed:
            pass
        finally:
            self.monitors.discard(connection)

    async def publish(self):
        content = self.snapshot()

        async def send(connection):
            try:
                await asyncio.wait_for(connection.send(content), timeout=1)
            except (ConnectionClosed, TimeoutError):
                self.monitors.discard(connection)
                await connection.close()

        await asyncio.gather(*(send(connection) for connection in tuple(self.monitors)))

    async def http(self, connection, request):
        path = urlsplit(request.path).path
        if request.headers.get('Upgrade', '').lower() == 'websocket':
            return None if path == MONITOR_PATH else Response(403, 'Forbidden', Headers(), b'')
        try:
            if path == '/state':
                content, mime = self.snapshot().encode(), 'application/json'
            else:
                source, mime = FILES[path]
                content = (ASSETS / source).read_bytes()
        except (KeyError, FileNotFoundError):
            return Response(404, 'Not found', Headers(), b'Not found')
        headers = Headers({'Content-Type': mime, 'Content-Length': str(len(content)),
                           'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                           'Referrer-Policy': 'no-referrer'})
        return Response(200, 'OK', headers, content)

    async def close(self):
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
