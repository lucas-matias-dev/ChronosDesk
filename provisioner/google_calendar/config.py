"""Load and validate local Google Calendar configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import GoogleCalendarConfigError

DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
REQUIRED_DESKTOP_FIELDS = (
    "client_id",
    "client_secret",
    "auth_uri",
    "token_uri",
    "redirect_uris",
)


@dataclass(frozen=True)
class GoogleCalendarConfig:
    client_file: Path
    timezone_name: str
    timezone: ZoneInfo


def _read_env_file(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as error:
        raise GoogleCalendarConfigError(
            f"Arquivo de configuração local não encontrado: {path}"
        ) from error
    except (PermissionError, OSError) as error:
        raise GoogleCalendarConfigError(
            f"Não foi possível ler o arquivo de configuração local: {path}"
        ) from error

    values: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _resolve_client_file(raw_path: str, env_path: Path) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = env_path.parent / candidate
    return candidate.resolve()


def _validate_client_file(path: Path) -> None:
    if not path.exists():
        raise GoogleCalendarConfigError(
            f"Arquivo OAuth do Google não encontrado: {path}"
        )
    if not path.is_file():
        raise GoogleCalendarConfigError(
            f"O caminho OAuth do Google não aponta para um arquivo: {path}"
        )

    try:
        with path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
    except PermissionError as error:
        raise GoogleCalendarConfigError(
            f"Sem permissão para ler o arquivo OAuth do Google: {path}"
        ) from error
    except OSError as error:
        raise GoogleCalendarConfigError(
            f"Não foi possível ler o arquivo OAuth do Google: {path}"
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GoogleCalendarConfigError(
            f"JSON OAuth do Google inválido: {path}"
        ) from error

    if not isinstance(document, dict) or not isinstance(
        document.get("installed"), dict
    ):
        raise GoogleCalendarConfigError(
            f"O arquivo OAuth não é de um cliente Desktop (campo ausente: installed): {path}"
        )

    installed = document["installed"]
    missing = [
        field for field in REQUIRED_DESKTOP_FIELDS if not installed.get(field)
    ]
    if missing:
        fields = ", ".join(f"installed.{field}" for field in missing)
        raise GoogleCalendarConfigError(
            f"Campos ausentes no arquivo OAuth do Google ({fields}): {path}"
        )

    invalid = [
        field
        for field in REQUIRED_DESKTOP_FIELDS
        if (
            field == "redirect_uris"
            and (
                not isinstance(installed[field], list)
                or not all(
                    isinstance(uri, str) and uri for uri in installed[field]
                )
            )
        )
        or (
            field != "redirect_uris"
            and not isinstance(installed[field], str)
        )
    ]
    if invalid:
        fields = ", ".join(f"installed.{field}" for field in invalid)
        raise GoogleCalendarConfigError(
            f"Campos inválidos no arquivo OAuth do Google ({fields}): {path}"
        )


def load_google_calendar_config(
    env_path: Path = DEFAULT_ENV_FILE,
    environment: Mapping[str, str] | None = None,
) -> GoogleCalendarConfig:
    """Build immutable configuration without retaining OAuth JSON contents."""

    local_values = _read_env_file(env_path)
    process_values = os.environ if environment is None else environment
    raw_client_file = (
        process_values.get("GOOGLE_OAUTH_CLIENT_FILE")
        or local_values.get("GOOGLE_OAUTH_CLIENT_FILE")
        or ""
    ).strip()
    if not raw_client_file:
        raise GoogleCalendarConfigError(
            f"Variável GOOGLE_OAUTH_CLIENT_FILE ausente em: {env_path}"
        )

    timezone_name = (
        process_values.get("GOOGLE_CALENDAR_TIMEZONE")
        or local_values.get("GOOGLE_CALENDAR_TIMEZONE")
        or DEFAULT_TIMEZONE
    ).strip()
    try:
        timezone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise GoogleCalendarConfigError(
            f"Timezone GOOGLE_CALENDAR_TIMEZONE inválido: {timezone_name}"
        ) from error

    client_file = _resolve_client_file(raw_client_file, env_path)
    _validate_client_file(client_file)
    return GoogleCalendarConfig(
        client_file=client_file,
        timezone_name=timezone_name,
        timezone=timezone,
    )
