"""One-shot OAuth callback server bound only to IPv4 loopback."""

from __future__ import annotations

import hmac
import queue
import socket
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class CallbackError(RuntimeError):
    pass


@dataclass(frozen=True)
class CallbackResult:
    authorization_code: str


def parse_callback_target(target: str, expected_state: str) -> CallbackResult:
    parsed = urlparse(target)
    if parsed.path != "/callback":
        raise CallbackError("Caminho de callback inválido.")
    parameters = parse_qs(parsed.query)
    received_state = parameters.get("state", [""])[0]
    if not received_state or not hmac.compare_digest(received_state, expected_state):
        raise CallbackError("O state do callback não corresponde ao esperado.")
    if "error" in parameters:
        reason = parameters["error"][0]
        if reason == "access_denied":
            raise CallbackError("A autorização foi recusada.")
        raise CallbackError("O Spotify retornou um erro de autorização.")
    code = parameters.get("code", [""])[0]
    if not code:
        raise CallbackError("Callback sem authorization code.")
    return CallbackResult(authorization_code=code)


class LoopbackCallbackServer:
    def __init__(self, port: int, expected_state: str, timeout_seconds: int):
        self.redirect_uri = f"http://127.0.0.1:{port}/callback"
        self._results: queue.Queue[CallbackResult | Exception] = queue.Queue(maxsize=1)
        results = self._results

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - HTTP method name
                try:
                    result = parse_callback_target(self.path, expected_state)
                    results.put_nowait(result)
                    status = 200
                    message = "Autorização recebida. Você pode fechar esta janela."
                except CallbackError as error:
                    results.put_nowait(error)
                    status = 400
                    message = str(error)
                body = (
                    "<!doctype html><meta charset='utf-8'>"
                    f"<title>ChronosDesk</title><p>{message}</p>"
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        try:
            self._server = HTTPServer(("127.0.0.1", port), Handler)
        except OSError as error:
            raise CallbackError(
                f"Não foi possível abrir 127.0.0.1:{port}; a porta pode estar ocupada."
            ) from error
        self._server.timeout = timeout_seconds

    def wait_for_callback(self) -> CallbackResult:
        try:
            self._server.handle_request()
            if self._results.empty():
                raise CallbackError("Tempo limite aguardando autorização.")
            result = self._results.get_nowait()
            if isinstance(result, Exception):
                raise result
            return result
        finally:
            self._server.server_close()
