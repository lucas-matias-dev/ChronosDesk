"""Orchestration for the on-demand desktop Calendar validation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from google.auth.transport.requests import AuthorizedSession

from .auth import GoogleOAuthClient
from .client import GoogleCalendarClient
from .config import GoogleCalendarConfig
from .errors import GoogleOAuthError
from .parser import CalendarEventParser
from .presenter import CalendarConsolePresenter
from .service import GoogleCalendarDayService


class GoogleCalendarValidationUseCase:
    def __init__(
        self,
        oauth_client: GoogleOAuthClient,
        presenter: CalendarConsolePresenter,
        *,
        session_factory: Callable[[Any], Any] = AuthorizedSession,
        client_factory: Callable[[Any], GoogleCalendarClient] = GoogleCalendarClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._oauth_client = oauth_client
        self._presenter = presenter
        self._session_factory = session_factory
        self._client_factory = client_factory
        self._clock = clock

    def execute(
        self, config: GoogleCalendarConfig, timeout_seconds: int
    ) -> None:
        authorization = self._oauth_client.authorize(config, timeout_seconds)
        self._presenter.authorization_succeeded(
            authorization.refresh_token_received
        )
        if not authorization.refresh_token_received:
            raise GoogleOAuthError(
                "O Google não retornou refresh token; revogue o acesso anterior "
                "e autorize novamente com consentimento."
            )

        session = self._session_factory(authorization.credentials)
        try:
            client = self._client_factory(session)
            parser = CalendarEventParser(config.timezone)
            day = GoogleCalendarDayService(
                client,
                parser,
                config.timezone,
                config.timezone_name,
                clock=self._clock,
            ).get_today()
            self._presenter.show_day(day)
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()
