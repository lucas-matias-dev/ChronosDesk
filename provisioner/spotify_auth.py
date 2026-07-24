"""Spotify Authorization Code with PKCE helpers."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

AUTHORIZE_ENDPOINT = "https://accounts.spotify.com/authorize"
TOKEN_ENDPOINT = "https://accounts.spotify.com/api/token"
REQUIRED_SCOPE = "user-read-currently-playing"


class SpotifyAuthorizationError(RuntimeError):
    """Safe OAuth error that never contains token response bodies."""


@dataclass
class TokenResponse:
    refresh_token: str
    scopes: str

    def clear(self) -> None:
        self.refresh_token = ""
        self.scopes = ""


def generate_code_verifier() -> str:
    verifier = secrets.token_urlsafe(64)
    if not 43 <= len(verifier) <= 128:
        raise RuntimeError("Falha ao gerar code_verifier com tamanho PKCE válido.")
    return verifier


def generate_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def build_authorization_url(
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
) -> str:
    parameters = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": REQUIRED_SCOPE,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "state": state,
    }
    return f"{AUTHORIZE_ENDPOINT}?{urllib.parse.urlencode(parameters)}"


def parse_token_payload(payload: bytes) -> TokenResponse:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SpotifyAuthorizationError(
            "O Spotify retornou uma resposta de token inválida."
        ) from error

    refresh_token = document.get("refresh_token")
    scopes = document.get("scope", "")
    if not isinstance(refresh_token, str) or len(refresh_token) < 16:
        raise SpotifyAuthorizationError(
            "A resposta não contém um refresh token válido."
        )
    if set(scopes.split()) != {REQUIRED_SCOPE}:
        raise SpotifyAuthorizationError(
            f"O scope obrigatório {REQUIRED_SCOPE!r} não foi concedido."
        )
    return TokenResponse(refresh_token=refresh_token, scopes=scopes)


def exchange_authorization_code(
    client_id: str,
    authorization_code: str,
    redirect_uri: str,
    code_verifier: str,
    timeout_seconds: float = 15,
) -> TokenResponse:
    form = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
    ).encode("ascii")
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return parse_token_payload(response.read())
    except urllib.error.HTTPError as error:
        raise SpotifyAuthorizationError(
            f"Troca do código recusada pelo Spotify (HTTP {error.code})."
        ) from None
    except urllib.error.URLError as error:
        raise SpotifyAuthorizationError(
            "Não foi possível conectar ao endpoint de tokens do Spotify."
        ) from error
