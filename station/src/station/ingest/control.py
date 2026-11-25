"""Internal HTTP interface to the ingest service: definitions and commands.

It has no authentication. It must only be reachable by the web API and the test runner.
"""

from dataclasses import asdict

import psycopg
from aiohttp import web

from station import protocol

from .service import Ingest


def _definitions() -> dict:
    definitions = protocol.DEFINITIONS
    return {
        "parameters": [asdict(p) for p in definitions.parameters],
        "enums": definitions.enums,
        "functions": [asdict(f) for f in definitions.functions],
    }


def _message(body) -> protocol.Command | protocol.Ping:
    if not isinstance(body, dict) or not isinstance(body.get("name"), str):
        raise protocol.PayloadError('expected {"name": ..., "args": {...}}')
    args = body.get("args", {})
    if not isinstance(args, dict):
        raise protocol.PayloadError("args must be an object")
    if body["name"] == "ping" and not args:
        return protocol.Ping()
    return protocol.Command(body["name"], args)


def build_app(ingest: Ingest) -> web.Application:
    async def definitions(request: web.Request) -> web.Response:
        return web.json_response(_definitions())

    async def send(request: web.Request) -> web.Response:
        try:
            command_id = await ingest.send_command(_message(await request.json()))
        # TypeError: a value of a kind that cannot even be looked up, such as a list
        except (protocol.PayloadError, TypeError, ValueError) as error:
            return web.json_response({"error": str(error)}, status=400)
        except psycopg.OperationalError:
            return web.json_response({"error": "database unavailable"}, status=503)
        return web.json_response({"id": command_id}, status=202)

    app = web.Application(client_max_size=4096)
    app.add_routes([web.get("/definitions", definitions), web.post("/commands", send)])
    return app


async def serve_control(ingest: Ingest, host: str, port: int) -> web.AppRunner:
    runner = web.AppRunner(build_app(ingest), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    return runner
