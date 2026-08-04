"""Secure Google Calendar credential provisioning orchestration."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from .auth import GoogleAuthorization, GoogleOAuthClient, REQUIRED_SCOPE
from .config import GoogleCalendarConfig
from .errors import GoogleCalendarProvisioningError, GoogleOAuthError

GOOGLE_CREDENTIAL_FORMAT_VERSION = 1
MAXIMUM_CLIENT_ID_LENGTH = 256
MINIMUM_REFRESH_TOKEN_LENGTH = 16
MAXIMUM_REFRESH_TOKEN_LENGTH = 2048
MAXIMUM_SCOPES_LENGTH = 128
MAXIMUM_TIMESTAMP_LENGTH = 20
_UTC_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
)


class GoogleProvisioningTransport(Protocol):
    def provision_google(
        self,
        *,
        google_client_id: str,
        refresh_token: str,
        authorized_at: str,
        scopes: str,
        credential_format_version: int,
    ) -> None: ...

    def erase_google(self) -> None: ...


@dataclass(repr=False)
class GoogleCalendarProvisioningMaterial:
    """Validated sensitive values with an intentionally redacted repr."""

    google_client_id: str
    refresh_token: str
    authorized_at: str
    scopes: str
    credential_format_version: int = GOOGLE_CREDENTIAL_FORMAT_VERSION

    @classmethod
    def create(
        cls,
        *,
        google_client_id: Any,
        refresh_token: Any,
        authorized_at: Any,
        scopes: Any,
        credential_format_version: Any = GOOGLE_CREDENTIAL_FORMAT_VERSION,
    ) -> GoogleCalendarProvisioningMaterial:
        if (
            not isinstance(google_client_id, str)
            or not google_client_id
            or google_client_id != google_client_id.strip()
            or len(google_client_id) > MAXIMUM_CLIENT_ID_LENGTH
        ):
            raise GoogleCalendarProvisioningError(
                "O Google Client ID validado está ausente ou é inválido."
            )
        if (
            not isinstance(refresh_token, str)
            or refresh_token != refresh_token.strip()
            or not MINIMUM_REFRESH_TOKEN_LENGTH
            <= len(refresh_token)
            <= MAXIMUM_REFRESH_TOKEN_LENGTH
        ):
            raise GoogleCalendarProvisioningError(
                "O OAuth Google não forneceu um refresh token válido."
            )
        if (
            not isinstance(scopes, str)
            or len(scopes) > MAXIMUM_SCOPES_LENGTH
            or scopes != REQUIRED_SCOPE
        ):
            raise GoogleCalendarProvisioningError(
                "O escopo necessário do Google Agenda não foi concedido."
            )
        if not cls._is_valid_timestamp(authorized_at):
            raise GoogleCalendarProvisioningError(
                "O timestamp UTC de autorização é inválido."
            )
        if (
            type(credential_format_version) is not int
            or credential_format_version != GOOGLE_CREDENTIAL_FORMAT_VERSION
        ):
            raise GoogleCalendarProvisioningError(
                "A versão do formato de credenciais Google é incompatível."
            )
        return cls(
            google_client_id=google_client_id,
            refresh_token=refresh_token,
            authorized_at=authorized_at,
            scopes=scopes,
            credential_format_version=credential_format_version,
        )

    @staticmethod
    def _is_valid_timestamp(value: Any) -> bool:
        if (
            not isinstance(value, str)
            or len(value) > MAXIMUM_TIMESTAMP_LENGTH
            or _UTC_TIMESTAMP_PATTERN.fullmatch(value) is None
        ):
            return False
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return False
        return True

    def clear(self) -> None:
        self.google_client_id = ""
        self.refresh_token = ""
        self.authorized_at = ""
        self.scopes = ""
        self.credential_format_version = 0

    def __repr__(self) -> str:
        return "GoogleCalendarProvisioningMaterial(<redacted>)"


class GoogleCalendarProvisioningUseCase:
    def __init__(
        self,
        oauth_client: GoogleOAuthClient,
        transport_factory: Callable[[str], GoogleProvisioningTransport],
        *,
        clock: Callable[[], datetime] | None = None,
        output: Callable[[str], None] = print,
    ) -> None:
        self._oauth_client = oauth_client
        self._transport_factory = transport_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._output = output

    def execute(
        self,
        config: GoogleCalendarConfig,
        port: str,
        timeout_seconds: int,
    ) -> None:
        self._output("[GCAL] Iniciando autorização no navegador.")
        authorization = self._oauth_client.authorize(config, timeout_seconds)
        material: GoogleCalendarProvisioningMaterial | None = None
        credentials = authorization.credentials
        try:
            self._validate_authorization(authorization)
            now = self._clock()
            if now.tzinfo is None:
                raise GoogleCalendarProvisioningError(
                    "O relógio usado no provisionamento não possui timezone."
                )
            authorized_at = now.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            material = GoogleCalendarProvisioningMaterial.create(
                google_client_id=config.google_client_id,
                refresh_token=getattr(credentials, "refresh_token", None),
                authorized_at=authorized_at,
                scopes=REQUIRED_SCOPE,
            )

            # The short-lived access token is not needed after OAuth validation.
            self._discard_credential_attribute(credentials, "token")
            self._discard_credential_attribute(credentials, "refresh_token")

            self._output("[GCAL] Autorização e material validados.")
            self._output("[GCAL] Feche o Monitor Serial; iniciando comunicação.")
            transport = self._transport_factory(port)
            transport.provision_google(
                google_client_id=material.google_client_id,
                refresh_token=material.refresh_token,
                authorized_at=material.authorized_at,
                scopes=material.scopes,
                credential_format_version=material.credential_format_version,
            )
            self._output("[GCAL] Credenciais armazenadas e confirmadas pelo ESP32.")
        finally:
            self._discard_credential_attribute(credentials, "token")
            self._discard_credential_attribute(credentials, "refresh_token")
            if material is not None:
                material.clear()

    @staticmethod
    def _validate_authorization(authorization: GoogleAuthorization) -> None:
        if not authorization.refresh_token_received:
            raise GoogleOAuthError(
                "O Google não retornou refresh token; revogue o acesso anterior "
                "e autorize novamente com consentimento."
            )
        has_scopes = getattr(authorization.credentials, "has_scopes", None)
        if not callable(has_scopes) or not has_scopes([REQUIRED_SCOPE]):
            raise GoogleOAuthError(
                "O escopo necessário do Google Agenda não foi concedido."
            )

    @staticmethod
    def _discard_credential_attribute(credentials: Any, name: str) -> None:
        try:
            setattr(credentials, name, None)
        except (AttributeError, TypeError):
            pass


class GoogleCalendarEraseUseCase:
    def __init__(
        self,
        transport_factory: Callable[[str], GoogleProvisioningTransport],
        *,
        output: Callable[[str], None] = print,
    ) -> None:
        self._transport_factory = transport_factory
        self._output = output

    def execute(self, port: str) -> None:
        self._output("[GCAL] Feche o Monitor Serial; iniciando apagamento local.")
        self._transport_factory(port).erase_google()
        self._output("[GCAL] Credenciais Google apagadas do ESP32.")
