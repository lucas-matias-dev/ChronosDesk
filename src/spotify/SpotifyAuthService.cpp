#include "SpotifyAuthService.h"

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>

#include "../config/AppConfig.h"
#include "../config/Secrets.h"
#include "SpotifyCertificates.h"
#include "SpotifyHttpUtils.h"

namespace {
constexpr char tokenEndpoint[] = "https://accounts.spotify.com/api/token";
}

SpotifyAuthService::SpotifyAuthService(SpotifyTokenStorage& storage)
    : storage_(storage) {}

void SpotifyAuthService::begin() {
  reloadCredentials();
}

bool SpotifyAuthService::ensureAccessToken(uint32_t nowMs) {
  if (hasAccessToken(nowMs)) {
    return true;
  }
  if (state_ == SpotifyAuthState::NotProvisioned ||
      state_ == SpotifyAuthState::ReauthorizationRequired ||
      static_cast<int32_t>(nowMs - retryAtMs_) < 0) {
    return false;
  }
  return refreshAccessToken(nowMs);
}

void SpotifyAuthService::invalidateAccessToken() {
  clearAccessToken();
  setState(credentials_.refreshToken.isEmpty()
               ? SpotifyAuthState::NotProvisioned
               : SpotifyAuthState::ReadyToRefresh);
}

void SpotifyAuthService::reloadCredentials() {
  clearAccessToken();
  if (storage_.load(credentials_)) {
    setState(SpotifyAuthState::ReadyToRefresh);
    Serial.println("[SPOTIFY][AUTH] Credenciais carregadas");
  } else {
    credentials_.clear();
    setState(SpotifyAuthState::NotProvisioned);
    Serial.println("[SPOTIFY][AUTH] Dispositivo nao provisionado");
  }
}

bool SpotifyAuthService::hasAccessToken(uint32_t nowMs) const {
  return !accessToken_.isEmpty() &&
         static_cast<int32_t>(refreshAtMs_ - nowMs) > 0;
}

const String& SpotifyAuthService::accessToken() const {
  return accessToken_;
}

SpotifyAuthState SpotifyAuthService::state() const {
  return state_;
}

bool SpotifyAuthService::stateChanged() {
  const bool changed = stateChanged_;
  stateChanged_ = false;
  return changed;
}

bool SpotifyAuthService::refreshAccessToken(uint32_t nowMs) {
  if (configuredSpotifyClientId[0] == '\0') {
    setState(SpotifyAuthState::ReauthorizationRequired);
    Serial.println("[SPOTIFY][AUTH] SPOTIFY_CLIENT_ID nao configurado");
    return false;
  }

  setState(SpotifyAuthState::Refreshing);
  Serial.println("[SPOTIFY][AUTH] Solicitando access token");

  NetworkClientSecure client;
  client.setCACert(spotifyRootCa);
  client.setHandshakeTimeout(AppConfig::Spotify::requestTimeoutMs / 1000);

  HTTPClient http;
  http.setConnectTimeout(AppConfig::Spotify::requestTimeoutMs);
  http.setTimeout(AppConfig::Spotify::requestTimeoutMs);
  if (!http.begin(client, tokenEndpoint)) {
    setState(SpotifyAuthState::TemporaryError);
    retryAtMs_ = nowMs + AppConfig::Spotify::initialBackoffMs;
    return false;
  }

  http.addHeader("Content-Type", "application/x-www-form-urlencoded");
  const String body =
      "grant_type=refresh_token&refresh_token=" +
      formUrlEncode(credentials_.refreshToken) +
      "&client_id=" + formUrlEncode(configuredSpotifyClientId);
  const int statusCode = http.POST(body);
  const String response = http.getString();
  http.end();

  JsonDocument document;
  const DeserializationError jsonError = deserializeJson(document, response);
  if (statusCode == 200 && jsonError == DeserializationError::Ok) {
    const char* token = document["access_token"] | "";
    const uint32_t expiresIn = document["expires_in"] | 0;
    if (token[0] == '\0' || expiresIn <= AppConfig::Spotify::tokenRefreshMarginSeconds) {
      setState(SpotifyAuthState::TemporaryError);
      retryAtMs_ = nowMs + AppConfig::Spotify::initialBackoffMs;
      return false;
    }

    accessToken_ = token;
    const uint32_t validForSeconds =
        expiresIn - AppConfig::Spotify::tokenRefreshMarginSeconds;
    refreshAtMs_ = nowMs + validForSeconds * 1000UL;

    const char* replacementRefreshToken = document["refresh_token"] | "";
    if (replacementRefreshToken[0] != '\0') {
      credentials_.refreshToken = replacementRefreshToken;
      if (!storage_.save(credentials_)) {
        Serial.println("[SPOTIFY][AUTH] Falha ao persistir token rotacionado");
      }
    }
    setState(SpotifyAuthState::Authorized);
    Serial.printf("[SPOTIFY][AUTH] Token obtido; renovacao em %lu s\n",
                  static_cast<unsigned long>(validForSeconds));
    return true;
  }

  const char* oauthError =
      jsonError == DeserializationError::Ok ? document["error"] | "" : "";
  if (statusCode == 400 && strcmp(oauthError, "invalid_grant") == 0) {
    clearAccessToken();
    storage_.clear();
    credentials_.clear();
    setState(SpotifyAuthState::ReauthorizationRequired);
    Serial.println("[SPOTIFY][AUTH] Refresh token invalido; reautorize");
    return false;
  }

  setState(SpotifyAuthState::TemporaryError);
  retryAtMs_ = nowMs + AppConfig::Spotify::initialBackoffMs;
  Serial.printf("[SPOTIFY][AUTH] Falha temporaria HTTP %d\n", statusCode);
  return false;
}

void SpotifyAuthService::clearAccessToken() {
  accessToken_ = "";
  refreshAtMs_ = 0;
}

void SpotifyAuthService::setState(SpotifyAuthState newState) {
  if (state_ == newState) {
    return;
  }
  state_ = newState;
  stateChanged_ = true;
}
