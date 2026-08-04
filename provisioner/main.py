"""ChronosDesk desktop provisioner and integration tests."""

from __future__ import annotations

import argparse
import os
import time
import webbrowser
from pathlib import Path

from callback_server import CallbackError, LoopbackCallbackServer
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
    from serial_transport import available_ports

    if explicit_port:
        return explicit_port
    ports = available_ports()
    if ports:
        print("Portas encontradas:", ", ".join(ports))
    return input("Informe a porta COM do ESP32 (ex.: COM5): ").strip()


def run_provisioning(port: str, callback_port: int, timeout: int) -> None:
    from serial_transport import SerialTransport

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


def run_google_calendar_test(timeout_seconds: int) -> None:
    from google_calendar.auth import GoogleOAuthClient
    from google_calendar.config import load_google_calendar_config
    from google_calendar.presenter import CalendarConsolePresenter
    from google_calendar.use_case import GoogleCalendarValidationUseCase

    config = load_google_calendar_config(environment={})
    GoogleCalendarValidationUseCase(
        GoogleOAuthClient(),
        CalendarConsolePresenter(),
    ).execute(config, timeout_seconds)


def run_google_calendar_provision(
    port: str, timeout_seconds: int
) -> None:
    from google_calendar.auth import GoogleOAuthClient
    from google_calendar.config import load_google_calendar_config
    from google_calendar.provisioning import GoogleCalendarProvisioningUseCase
    from serial_transport import SerialTransport

    config = load_google_calendar_config(environment={})
    GoogleCalendarProvisioningUseCase(
        GoogleOAuthClient(),
        SerialTransport,
    ).execute(config, port, timeout_seconds)


def run_google_calendar_erase(port: str) -> None:
    from google_calendar.provisioning import GoogleCalendarEraseUseCase
    from serial_transport import SerialTransport

    GoogleCalendarEraseUseCase(SerialTransport).execute(port)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="Porta serial, por exemplo COM5")
    parser.add_argument("--callback-port", type=int, default=DEFAULT_CALLBACK_PORT)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--erase",
        action="store_true",
        help="Apaga as credenciais Spotify da NVS sem iniciar OAuth.",
    )
    subparsers = parser.add_subparsers(dest="command")
    google_parser = subparsers.add_parser(
        "google-calendar-test",
        help="Valida OAuth e lista os compromissos de hoje somente no computador.",
        description=(
            "Autoriza o Google Agenda e consulta os compromissos de hoje. "
            "Não usa porta serial nem o ESP32."
        ),
    )
    google_parser.add_argument(
        "--timeout",
        dest="google_timeout",
        type=int,
        default=180,
        help="Tempo máximo, em segundos, para concluir o callback OAuth.",
    )
    provision_parser = subparsers.add_parser(
        "google-calendar-provision",
        help="Autoriza no Google e provisiona o ESP32 pela serial.",
        description=(
            "Conclui o OAuth Google antes de abrir a porta serial e envia "
            "somente o material persistente da Fase 5."
        ),
    )
    provision_parser.add_argument(
        "--port",
        dest="google_port",
        required=True,
        help="Porta serial do ESP32, por exemplo COM5.",
    )
    provision_parser.add_argument(
        "--timeout",
        dest="google_provision_timeout",
        type=int,
        default=180,
        help="Tempo máximo, em segundos, para concluir o callback OAuth.",
    )
    erase_parser = subparsers.add_parser(
        "google-calendar-erase",
        help="Apaga somente as credenciais Google armazenadas no ESP32.",
        description=(
            "Apaga localmente as credenciais Google do ESP32 sem iniciar OAuth "
            "e sem revogar o acesso remoto."
        ),
    )
    erase_parser.add_argument(
        "--port",
        dest="google_erase_port",
        required=True,
        help="Porta serial do ESP32, por exemplo COM5.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "google-calendar-test":
        from google_calendar.errors import GoogleCalendarError

        try:
            run_google_calendar_test(arguments.google_timeout)
            return 0
        except KeyboardInterrupt:
            print("\n[GCAL] Operação cancelada.")
            return 130
        except GoogleCalendarError as error:
            print(f"[GCAL] Erro: {error}")
            return 1

    if arguments.command in {
        "google-calendar-provision",
        "google-calendar-erase",
    }:
        from google_calendar.errors import GoogleCalendarError
        from serial_transport import SerialProvisioningError

        try:
            if arguments.command == "google-calendar-provision":
                run_google_calendar_provision(
                    arguments.google_port,
                    arguments.google_provision_timeout,
                )
            else:
                run_google_calendar_erase(arguments.google_erase_port)
            return 0
        except KeyboardInterrupt:
            print("\n[GCAL] Operação cancelada.")
            return 130
        except (GoogleCalendarError, SerialProvisioningError) as error:
            print(f"[GCAL] Erro: {error}")
            return 1

    load_local_environment()
    serial_port = choose_serial_port(arguments.port)
    if not serial_port:
        print("Nenhuma porta serial informada.")
        return 2

    try:
        from serial_transport import SerialProvisioningError, SerialTransport

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
