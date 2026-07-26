"""Versioned newline-delimited JSON transport for the ESP32."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import serial
from serial.tools import list_ports

PROTOCOL_VERSION = 1


class SerialProvisioningError(RuntimeError):
    pass


def available_ports() -> list[str]:
    return [port.device for port in list_ports.comports()]


def build_message(message_type: str, **fields: object) -> bytes:
    document = {
        "protocol": PROTOCOL_VERSION,
        "type": message_type,
        **fields,
    }
    return (json.dumps(document, separators=(",", ":")) + "\n").encode("utf-8")


@dataclass
class SerialTransport:
    port: str
    baud_rate: int = 115200
    timeout_seconds: float = 15

    def provision(
        self, refresh_token: str, authorized_at: int, scopes: str
    ) -> None:
        try:
            with serial.Serial(
                self.port,
                self.baud_rate,
                timeout=0.25,
                write_timeout=3,
            ) as connection:
                time.sleep(1.5)
                connection.reset_input_buffer()
                connection.write(build_message("provision_begin"))
                self._wait_for(connection, {"provision_ready"})
                connection.write(
                    build_message(
                        "store_credentials",
                        refresh_token=refresh_token,
                        authorized_at=authorized_at,
                        scopes=scopes,
                    )
                )
                self._wait_for(connection, {"storage_complete"})
        except serial.SerialException as error:
            raise SerialProvisioningError(
                "Falha na porta serial. Feche o Monitor Serial e confira a porta COM."
            ) from error

    def erase(self) -> None:
        try:
            with serial.Serial(
                self.port, self.baud_rate, timeout=0.25, write_timeout=3
            ) as connection:
                time.sleep(1.5)
                connection.reset_input_buffer()
                connection.write(build_message("erase_credentials"))
                self._wait_for(connection, {"credentials_erased"})
        except serial.SerialException as error:
            raise SerialProvisioningError("Falha ao apagar credenciais via serial.") from error

    def _wait_for(self, connection: serial.Serial, accepted: set[str]) -> dict:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            line = connection.readline()
            if not line:
                continue
            try:
                document = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if document.get("protocol") != PROTOCOL_VERSION:
                if document.get("type") == "incompatible_version":
                    raise SerialProvisioningError("Versão de protocolo incompatível.")
                continue
            message_type = document.get("type")
            if message_type in accepted:
                return document
            if message_type in {
                "validation_failed",
                "storage_failed",
                "incompatible_version",
            }:
                reason = document.get("reason", "erro não especificado")
                raise SerialProvisioningError(
                    f"ESP32 recusou o provisionamento: {reason}."
                )
        raise SerialProvisioningError("Tempo limite aguardando confirmação do ESP32.")
