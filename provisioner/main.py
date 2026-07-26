"""ChronosDesk Spotify provisioner for Windows."""

from __future__ import annotations

import argparse
import os
import time
import webbrowser
from pathlib import Path

from callback_server import CallbackError, LoopbackCallbackServer
from serial_transport import (
    SerialProvisioningError,
    SerialTransport,
    available_ports,
)
from spotify_auth import (
    SpotifyAuthorizationError,
    build_authorization_url,
    exchange_authorization_code,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)

DEFAULT_CALLBACK_PORT = 8888


def load_local_environment() -> None:
    path = Path(__file__).with_name(".env")
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def choose_serial_port(explicit_port: str | None) -> str:
    if explicit_port:
        return explicit_port
    ports = available_ports()
    if ports:
        print("Portas encontradas:", ", ".join(ports))
    return input("Informe a porta COM do ESP32 (ex.: COM5): ").strip()


def run_provisioning(port: str, callback_port: int, timeout: int) -> None:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    if not client_id:
        raise RuntimeError(
            "Defina SPOTIFY_CLIENT_ID no ambiente ou em provisioner/.env."
        )

    verifier = generate_code_verifier()
    state = generate_state()
    server = LoopbackCallbackServer(callback_port, state, timeout)
    authorization_url = build_authorization_url(
        client_id,
        server.redirect_uri,
        generate_code_challenge(verifier),
        state,
    )

    print(f"Usando callback {server.redirect_uri}")
    print("Abrindo a autorização oficial do Spotify no navegador...")
    if not webbrowser.open(authorization_url):
        print("O navegador não abriu automaticamente. Abra a URL exibida abaixo:")
        print(authorization_url)
    callback = server.wait_for_callback()
    print("Autorização recebida; solicitando credenciais...")
    tokens = exchange_authorization_code(
        client_id,
        callback.authorization_code,
        server.redirect_uri,
        verifier,
    )

    callback = None
    verifier = ""
    state = ""
    try:
        print("Feche o Monitor Serial antes de continuar.")
        SerialTransport(port=port).provision(
            refresh_token=tokens.refresh_token,
            authorized_at=int(time.time()),
            scopes=tokens.scopes,
        )
        print("Credenciais armazenadas e confirmadas pelo ESP32.")
    finally:
        tokens.clear()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Porta serial, por exemplo COM5")
    parser.add_argument("--callback-port", type=int, default=DEFAULT_CALLBACK_PORT)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--erase",
        action="store_true",
        help="Apaga as credenciais Spotify da NVS sem iniciar OAuth.",
    )
    arguments = parser.parse_args()
    load_local_environment()
    serial_port = choose_serial_port(arguments.port)
    if not serial_port:
        print("Nenhuma porta serial informada.")
        return 2

    try:
        if arguments.erase:
            SerialTransport(port=serial_port).erase()
            print("Credenciais apagadas.")
        else:
            run_provisioning(
                serial_port, arguments.callback_port, arguments.timeout
            )
        return 0
    except (
        CallbackError,
        SerialProvisioningError,
        SpotifyAuthorizationError,
        RuntimeError,
    ) as error:
        print(f"Erro: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
