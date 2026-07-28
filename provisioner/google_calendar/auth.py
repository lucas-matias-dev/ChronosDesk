"""OAuth 2.0 installed-app authorization using Google's official library."""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass, field
from typing import Any, Callable

from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
from oauthlib.oauth2 import AccessDeniedError, OAuth2Error
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError

from .config import GoogleCalendarConfig
from .errors import GoogleOAuthError

REQUIRED_SCOPE = (
    "https://www.googleapis.com/auth/calendar.events.owned.readonly"
)
DEFAULT_AUTH_TIMEOUT_SECONDS = 180


@dataclass(frozen=True)
class GoogleAuthorization:
    credentials: Any = field(repr=False)
    refresh_token_received: bool


class _StrictBrowser:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    def open(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        if not self._delegate.open(url, new=new, autoraise=autoraise):
            raise webbrowser.Error("default browser did not open")
        return True


class GoogleOAuthClient:
    def __init__(
        self,
        flow_factory: Callable[..., Any] = InstalledAppFlow.from_client_secrets_file,
        browser_factory: Callable[[], Any] = webbrowser.get,
        browser_registrar: Callable[..., None] = webbrowser.register,
    ) -> None:
        self._flow_factory = flow_factory
        self._browser_factory = browser_factory
        self._browser_registrar = browser_registrar

    def authorize(
        self,
        config: GoogleCalendarConfig,
        timeout_seconds: int = DEFAULT_AUTH_TIMEOUT_SECONDS,
    ) -> GoogleAuthorization:
        try:
            flow = self._flow_factory(
                str(config.client_file),
                scopes=[REQUIRED_SCOPE],
                autogenerate_code_verifier=True,
            )
            browser_name = f"chronosdesk-google-{id(flow)}"
            self._browser_registrar(
                browser_name,
                None,
                _StrictBrowser(self._browser_factory()),
            )
            credentials = flow.run_local_server(
                host="127.0.0.1",
                bind_addr="127.0.0.1",
                port=0,
                open_browser=True,
                browser=browser_name,
                timeout_seconds=timeout_seconds,
                authorization_prompt_message=(
                    "[GCAL] Conclua a autorização no navegador."
                ),
                success_message=(
                    "Autorização do ChronosDesk concluída. "
                    "Você pode fechar esta janela."
                ),
                access_type="offline",
                prompt="consent",
            )
        except WSGITimeoutError as error:
            raise GoogleOAuthError(
                "O callback local expirou antes da conclusão da autorização."
            ) from error
        except AccessDeniedError as error:
            raise GoogleOAuthError("A autorização foi cancelada pelo usuário.") from error
        except MismatchingStateError as error:
            raise GoogleOAuthError(
                "O state retornado pelo Google é inválido."
            ) from error
        except webbrowser.Error as error:
            raise GoogleOAuthError(
                "Não foi possível abrir o navegador padrão."
            ) from error
        except OAuth2Error as error:
            raise GoogleOAuthError(
                "O Google recusou ou não concluiu a autorização."
            ) from error
        except OSError as error:
            raise GoogleOAuthError(
                "Não foi possível iniciar o callback em 127.0.0.1."
            ) from error

        if not credentials.has_scopes([REQUIRED_SCOPE]):
            raise GoogleOAuthError(
                "O escopo necessário do Google Agenda não foi concedido."
            )
        return GoogleAuthorization(
            credentials=credentials,
            refresh_token_received=bool(credentials.refresh_token),
        )
