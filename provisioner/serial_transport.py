"""Versioned newline-delimited JSON transport for the ESP32."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import serial
from serial.tools import list_ports

PROTOCOL_VERSION = 2
SPOTIFY_PROVIDER = "spotify"
GOOGLE_CALENDAR_PROVIDER = "google_calendar"
SUPPORTED_PROVIDERS = {SPOTIFY_PROVIDER, GOOGLE_CALENDAR_PROVIDER}
SPOTIFY_CREDENTIAL_FORMAT_VERSION = 1
MAXIMUM_RESPONSE_LINE_BYTES = 512
MAXIMUM_RESPONSE_FIELDS = 4
MAXIMUM_REQUEST_LINE_BYTES = 3072
MAXIMUM_REQUEST_FIELDS = 8
SERIAL_STARTUP_SECONDS = 1.5
DEFAULT_HANDSHAKE_TIMEOUT_SECONDS = 15.0
DEFAULT_CONFIRMATION_TIMEOUT_SECONDS = 15.0
DEFAULT_MAXIMUM_ATTEMPTS = 2

_FIRMWARE_ERRORS = {
    "invalid_json": "O ESP32 recebeu JSON inválido.",
    "invalid_message": "O ESP32 recusou uma mensagem inválida.",
    "invalid_provider": "O ESP32 recusou o provedor solicitado.",
    "provider_mismatch": "O ESP32 detectou troca de provedor na negociação.",
    "invalid_sequence": "O ESP32 recusou uma mensagem fora de sequência.",
    "invalid_credentials": "O ESP32 recusou o material de provisionamento.",
    "invalid_credential_format": "O ESP32 recusou o formato de credenciais.",
    "message_too_large": "O ESP32 recusou uma mensagem acima do limite.",
    "too_many_fields": "O ESP32 recusou um payload com campos em excesso.",
    "nvs_write_failed": "O ESP32 não conseguiu gravar as credenciais.",
    "erase_failed": "O ESP32 não conseguiu apagar as credenciais.",
    "unsupported_protocol": "Versão de protocolo incompatível.",
}


class SerialProvisioningError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


def available_ports() -> list[str]:
    return [port.device for port in list_ports.comports()]


def build_message(
    message_type: str,
    *,
    provider: str = SPOTIFY_PROVIDER,
    **fields: object,
) -> bytes:
    if provider not in SUPPORTED_PROVIDERS:
        raise SerialProvisioningError(
            "A mensagem serial possui provedor desconhecido."
        )
    if {"protocol", "type", "provider"}.intersection(fields):
        raise SerialProvisioningError(
            "A mensagem serial tentou redefinir um campo reservado."
        )
    document = {
        "protocol": PROTOCOL_VERSION,
        "type": message_type,
        "provider": provider,
        **fields,
    }
    if len(document) > MAXIMUM_REQUEST_FIELDS:
        raise SerialProvisioningError(
            "A mensagem serial possui campos em excesso."
        )
    message = (json.dumps(document, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    if len(message) - 1 > MAXIMUM_REQUEST_LINE_BYTES:
        raise SerialProvisioningError(
            "A mensagem serial ultrapassa o limite permitido."
        )
    return message


@dataclass
class SerialTransport:
    port: str
    baud_rate: int = 115200
    handshake_timeout_seconds: float = DEFAULT_HANDSHAKE_TIMEOUT_SECONDS
    confirmation_timeout_seconds: float = DEFAULT_CONFIRMATION_TIMEOUT_SECONDS
    maximum_attempts: int = DEFAULT_MAXIMUM_ATTEMPTS
    serial_factory: Callable[..., Any] = field(default=serial.Serial, repr=False)
    sleeper: Callable[[float], None] = field(default=time.sleep, repr=False)
    monotonic: Callable[[], float] = field(default=time.monotonic, repr=False)

    def provision(
        self, refresh_token: str, authorized_at: int, scopes: str
    ) -> None:
        self._provision(
            SPOTIFY_PROVIDER,
            credential_format_version=SPOTIFY_CREDENTIAL_FORMAT_VERSION,
            refresh_token=refresh_token,
            authorized_at=authorized_at,
            scopes=scopes,
        )

    def provision_google(
        self,
        *,
        google_client_id: str,
        refresh_token: str,
        authorized_at: str,
        scopes: str,
        credential_format_version: int,
    ) -> None:
        self._provision(
            GOOGLE_CALENDAR_PROVIDER,
            credential_format_version=credential_format_version,
            google_client_id=google_client_id,
            refresh_token=refresh_token,
            authorized_at=authorized_at,
            scopes=scopes,
        )

    def _provision(
        self,
        provider: str,
        **credential_fields: object,
    ) -> None:
        def transaction(connection: Any) -> None:
            connection.write(build_message("provision_begin", provider=provider))
            self._wait_for(
                connection,
                {"provision_ready"},
                provider,
                self.handshake_timeout_seconds,
            )
            message = build_message(
                "store_credentials", provider=provider, **credential_fields
            )
            try:
                connection.write(message)
                self._wait_for(
                    connection,
                    {"storage_complete"},
                    provider,
                    self.confirmation_timeout_seconds,
                )
            finally:
                message = b""

        self._execute_with_retries(transaction)

    def erase(self, provider: str = SPOTIFY_PROVIDER) -> None:
        def transaction(connection: Any) -> None:
            connection.write(build_message("provision_begin", provider=provider))
            self._wait_for(
                connection,
                {"provision_ready"},
                provider,
                self.handshake_timeout_seconds,
            )
            connection.write(build_message("erase_credentials", provider=provider))
            self._wait_for(
                connection,
                {"credentials_erased"},
                provider,
                self.confirmation_timeout_seconds,
            )

        self._execute_with_retries(transaction)

    def erase_google(self) -> None:
        self.erase(GOOGLE_CALENDAR_PROVIDER)

    def _execute_with_retries(
        self, transaction: Callable[[Any], None]
    ) -> None:
        if self.maximum_attempts < 1:
            raise SerialProvisioningError(
                "A quantidade de tentativas seriais é inválida."
            )

        last_error: SerialProvisioningError | None = None
        for attempt in range(self.maximum_attempts):
            try:
                with self.serial_factory(
                    self.port,
                    self.baud_rate,
                    timeout=0.25,
                    write_timeout=3,
                ) as connection:
                    self.sleeper(SERIAL_STARTUP_SECONDS)
                    connection.reset_input_buffer()
                    transaction(connection)
                    return
            except serial.SerialException:
                last_error = SerialProvisioningError(
                    "Falha na porta serial. Feche o Monitor Serial e confira a porta COM.",
                    retryable=True,
                )
            except SerialProvisioningError as error:
                last_error = error

            if last_error is None:
                raise AssertionError("Falha serial sem diagnóstico.")
            if not last_error.retryable:
                raise last_error
            if attempt + 1 >= self.maximum_attempts:
                raise last_error

        if last_error is not None:
            raise last_error
        raise AssertionError("Tentativas seriais sem resultado.")

    def _wait_for(
        self,
        connection: Any,
        accepted: set[str],
        provider: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        deadline = self.monotonic() + timeout_seconds
        while self.monotonic() < deadline:
            line = connection.read_until(
                expected=b"\n", size=MAXIMUM_RESPONSE_LINE_BYTES + 1
            )
            if not line:
                continue
            if (
                len(line) > MAXIMUM_RESPONSE_LINE_BYTES
                or not line.endswith(b"\n")
            ):
                raise SerialProvisioningError(
                    "O ESP32 enviou uma resposta acima do limite.",
                    retryable=False,
                )
            try:
                decoded = line.decode("utf-8").strip()
            except UnicodeDecodeError as error:
                raise SerialProvisioningError(
                    "O ESP32 enviou uma resposta que não é UTF-8 válido."
                ) from error
            if not decoded.startswith("{"):
                # Firmware diagnostics are intentionally ignored, never printed.
                continue
            try:
                document = json.loads(decoded)
            except json.JSONDecodeError as error:
                raise SerialProvisioningError(
                    "O ESP32 enviou uma resposta JSON inválida."
                ) from error
            if not isinstance(document, dict):
                raise SerialProvisioningError(
                    "O ESP32 enviou uma resposta serial inválida."
                )
            if len(document) > MAXIMUM_RESPONSE_FIELDS:
                raise SerialProvisioningError(
                    "O ESP32 enviou uma resposta com campos em excesso."
                )

            message_type = document.get("type")
            protocol = document.get("protocol")
            response_provider = document.get("provider")
            if type(protocol) is not int or protocol != PROTOCOL_VERSION:
                raise SerialProvisioningError(
                    "Versão de protocolo incompatível."
                )
            if not isinstance(response_provider, str):
                raise SerialProvisioningError(
                    "O ESP32 respondeu sem provedor válido."
                )
            if response_provider not in SUPPORTED_PROVIDERS:
                raise SerialProvisioningError(
                    "O ESP32 respondeu com provedor desconhecido."
                )
            if response_provider != provider:
                raise SerialProvisioningError(
                    "A resposta do ESP32 pertence a outro provedor."
                )
            if not isinstance(message_type, str):
                raise SerialProvisioningError(
                    "O ESP32 respondeu sem tipo de mensagem válido."
                )
            if message_type in accepted:
                return document
            if message_type in {
                "validation_failed",
                "storage_failed",
                "incompatible_version",
            }:
                reason = document.get("reason")
                message = (
                    _FIRMWARE_ERRORS.get(reason)
                    if isinstance(reason, str)
                    else None
                )
                raise SerialProvisioningError(
                    message or "O ESP32 recusou a operação serial."
                )
            raise SerialProvisioningError(
                "O ESP32 enviou uma mensagem fora da sequência esperada."
            )
        raise SerialProvisioningError(
            "Tempo limite aguardando confirmação do ESP32.",
            retryable=True,
        )
