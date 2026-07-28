"""Minimal authenticated REST client for Google Calendar."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

import requests
from google.auth.exceptions import GoogleAuthError, TransportError

from .errors import GoogleCalendarApiError

EVENTS_ENDPOINT = (
    "https://www.googleapis.com/calendar/v3/calendars/primary/events"
)
EVENT_FIELDS = (
    "nextPageToken,timeZone,"
    "items(id,summary,status,"
    "start(date,dateTime,timeZone),"
    "end(date,dateTime,timeZone))"
)
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


class HttpSession(Protocol):
    def get(
        self, url: str, *, params: dict[str, Any], timeout: float
    ) -> Any: ...


class GoogleCalendarClient:
    def __init__(
        self,
        session: HttpSession,
        *,
        timeout_seconds: float = 15,
        max_attempts: int = 3,
        max_pages: int = 10,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._session = session
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._max_pages = max_pages
        self._sleeper = sleeper

    def list_events(
        self,
        day_start: datetime,
        day_end: datetime,
        timezone_name: str,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeMin": day_start.isoformat(),
            "timeMax": day_end.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "showDeleted": "false",
            "timeZone": timezone_name,
            "maxResults": 250,
            "fields": EVENT_FIELDS,
        }
        all_items: list[dict[str, Any]] = []

        for page_number in range(self._max_pages):
            document = self._request_page(params)
            items = document.get("items")
            if not isinstance(items, list):
                raise GoogleCalendarApiError(
                    "A resposta do Google Agenda não contém uma lista de eventos."
                )
            if not all(isinstance(item, dict) for item in items):
                raise GoogleCalendarApiError(
                    "A resposta do Google Agenda contém um evento malformado."
                )
            all_items.extend(items)

            next_page_token = document.get("nextPageToken")
            if not next_page_token:
                return all_items
            if not isinstance(next_page_token, str):
                raise GoogleCalendarApiError(
                    "A paginação do Google Agenda é inválida."
                )
            params["pageToken"] = next_page_token

        raise GoogleCalendarApiError(
            f"O limite defensivo de {self._max_pages} páginas foi atingido."
        )

    def _request_page(self, params: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self._max_attempts):
            try:
                response = self._session.get(
                    EVENTS_ENDPOINT,
                    params=params,
                    timeout=self._timeout_seconds,
                )
            except requests.exceptions.SSLError as error:
                raise GoogleCalendarApiError(
                    "Falha TLS ao consultar o Google Agenda."
                ) from error
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                TransportError,
            ) as error:
                if attempt + 1 >= self._max_attempts:
                    raise GoogleCalendarApiError(
                        "Falha de rede, DNS ou timeout ao consultar o Google Agenda."
                    ) from error
                self._sleep_before_retry(attempt, None)
                continue
            except GoogleAuthError as error:
                raise GoogleCalendarApiError(
                    "A credencial Google não pôde autorizar a consulta."
                ) from error
            except requests.exceptions.RequestException as error:
                raise GoogleCalendarApiError(
                    "Falha HTTP ao consultar o Google Agenda."
                ) from error

            status = response.status_code
            if status == 200:
                try:
                    document = response.json()
                except ValueError as error:
                    raise GoogleCalendarApiError(
                        "O Google Agenda retornou JSON inválido."
                    ) from error
                if not isinstance(document, dict):
                    raise GoogleCalendarApiError(
                        "O Google Agenda retornou uma resposta inválida."
                    )
                return document

            if status in TRANSIENT_STATUS_CODES:
                if attempt + 1 >= self._max_attempts:
                    raise GoogleCalendarApiError(
                        f"Google Agenda indisponível após tentativas limitadas (HTTP {status})."
                    )
                self._sleep_before_retry(attempt, response)
                continue

            if status in {400, 401, 403}:
                guidance = {
                    400: "requisição recusada",
                    401: "autorização inválida ou expirada",
                    403: "acesso proibido; confira API, usuário de teste e escopo",
                }[status]
                raise GoogleCalendarApiError(
                    f"Google Agenda: {guidance} (HTTP {status})."
                )
            raise GoogleCalendarApiError(
                f"Google Agenda retornou um erro HTTP não esperado ({status})."
            )

        raise AssertionError("Tentativas HTTP encerradas sem resultado.")

    def _sleep_before_retry(self, attempt: int, response: Any | None) -> None:
        delay = 0.5 * (2**attempt)
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "")
            try:
                delay = min(max(float(retry_after), delay), 5.0)
            except (TypeError, ValueError):
                pass
        self._sleeper(delay)
