#include "ProvisioningService.h"

#include <ArduinoJson.h>
#include <cstring>

#include "../config/AppConfig.h"

ProvisioningService::ProvisioningService(
    SpotifyTokenStorage& spotifyStorage,
    GoogleCalendarTokenStorage& googleCalendarStorage)
    : spotifyStorage_(spotifyStorage),
      googleCalendarStorage_(googleCalendarStorage) {}

void ProvisioningService::update() {
  if (state_ != State::Idle &&
      millis() - negotiationStartedMs_ >=
          AppConfig::Provisioning::negotiationTimeoutMs) {
    resetNegotiation();
    clearLineBuffer();
    Serial.println("[PROVISION] Negociacao expirada");
  }

  while (Serial.available() > 0) {
    const char character = static_cast<char>(Serial.read());
    if (character == '\r') {
      continue;
    }
    if (character == '\n') {
      if (!discardLine_ && lineLength_ > 0) {
        lineBuffer_[lineLength_] = '\0';
        handleLine(lineBuffer_);
      }
      clearLineBuffer();
      discardLine_ = false;
      discardedBytes_ = 0;
      continue;
    }
    if (discardLine_) {
      if (discardedBytes_ <
          AppConfig::Provisioning::maximumDiscardedBytes) {
        ++discardedBytes_;
      }
      continue;
    }
    if (lineLength_ >= AppConfig::Provisioning::maximumSerialLineBytes) {
      const Provider responseProvider =
          negotiatedProvider_ == Provider::None ? Provider::Unknown
                                                : negotiatedProvider_;
      discardLine_ = true;
      discardedBytes_ = 0;
      sendMessage(
          "validation_failed", responseProvider, "message_too_large");
      resetNegotiation();
      clearLineBuffer();
      continue;
    }
    lineBuffer_[lineLength_++] = character;
  }
}

bool ProvisioningService::credentialsChanged() {
  const bool changed = credentialsChanged_;
  credentialsChanged_ = false;
  return changed;
}

void ProvisioningService::handleLine(const char* line) {
  const Provider activeProvider =
      negotiatedProvider_ == Provider::None ? Provider::Unknown
                                            : negotiatedProvider_;
  if (strlen(line) > AppConfig::Provisioning::maximumJsonBytes) {
    sendMessage("validation_failed", activeProvider, "message_too_large");
    resetNegotiation();
    return;
  }

  JsonDocument document;
  if (deserializeJson(document, line) != DeserializationError::Ok) {
    sendMessage("validation_failed", activeProvider, "invalid_json");
    resetNegotiation();
    return;
  }
  if (!document.is<JsonObject>()) {
    sendMessage("validation_failed", activeProvider, "invalid_message");
    resetNegotiation();
    return;
  }
  JsonObjectConst object = document.as<JsonObjectConst>();
  if (object.size() > AppConfig::Provisioning::maximumFields) {
    sendMessage("validation_failed", activeProvider, "too_many_fields");
    resetNegotiation();
    return;
  }

  if (!object["type"].is<const char*>() ||
      !object["provider"].is<const char*>()) {
    sendMessage("validation_failed", activeProvider, "invalid_message");
    resetNegotiation();
    return;
  }
  const char* type = object["type"].as<const char*>();
  const Provider provider =
      parseProvider(object["provider"].as<const char*>());
  if (provider == Provider::Unknown || provider == Provider::None) {
    sendMessage("validation_failed", Provider::Unknown, "invalid_provider");
    resetNegotiation();
    return;
  }

  if (!object["protocol"].is<int>() ||
      object["protocol"].as<int>() !=
          AppConfig::Provisioning::protocolVersion) {
    sendMessage("incompatible_version", provider, "unsupported_protocol");
    resetNegotiation();
    return;
  }

  if (strcmp(type, "provision_begin") == 0) {
    if (object.size() != 3) {
      sendMessage("validation_failed", provider, "invalid_message");
      resetNegotiation();
      return;
    }
    if (state_ != State::Idle && negotiatedProvider_ != provider) {
      sendMessage("validation_failed", provider, "provider_mismatch");
      resetNegotiation();
      return;
    }
    state_ = State::Ready;
    negotiatedProvider_ = provider;
    negotiationStartedMs_ = millis();
    sendMessage("provision_ready", provider);
    return;
  }

  if (state_ != State::Ready) {
    sendMessage("validation_failed", provider, "invalid_sequence");
    resetNegotiation();
    return;
  }
  if (negotiatedProvider_ != provider) {
    sendMessage("validation_failed", provider, "provider_mismatch");
    resetNegotiation();
    return;
  }

  if (strcmp(type, "erase_credentials") == 0) {
    if (object.size() != 3) {
      sendMessage("validation_failed", provider, "invalid_message");
      resetNegotiation();
      return;
    }
    const bool cleared = provider == Provider::Spotify
                             ? spotifyStorage_.clear()
                             : googleCalendarStorage_.clear();
    resetNegotiation();
    if (cleared) {
      if (provider == Provider::Spotify) {
        credentialsChanged_ = true;
        Serial.println("[SPOTIFY][PROVISION] Credenciais apagadas");
      } else {
        Serial.println("[GCAL][PROVISION] Credenciais apagadas");
      }
      sendMessage("credentials_erased", provider);
    } else {
      sendMessage("storage_failed", provider, "erase_failed");
    }
    return;
  }
  if (strcmp(type, "store_credentials") != 0) {
    sendMessage("validation_failed", provider, "invalid_message");
    resetNegotiation();
    return;
  }

  handleStore(object, provider);
}

void ProvisioningService::handleStore(JsonObjectConst document,
                                      Provider provider) {
  state_ = State::ReceivingCredentials;
  if (provider == Provider::Spotify) {
    handleSpotifyStore(document);
  } else {
    handleGoogleCalendarStore(document);
  }
}

void ProvisioningService::handleSpotifyStore(
    JsonObjectConst document) {
  if (document.size() != 7 ||
      !document["credential_format_version"].is<int>() ||
      !document["refresh_token"].is<const char*>() ||
      !document["authorized_at"].is<uint64_t>() ||
      !document["scopes"].is<const char*>()) {
    sendMessage(
        "validation_failed", Provider::Spotify, "invalid_credentials");
    resetNegotiation();
    return;
  }
  if (document["credential_format_version"].as<int>() !=
      AppConfig::Spotify::storageVersion) {
    sendMessage("validation_failed",
                Provider::Spotify,
                "invalid_credential_format");
    resetNegotiation();
    return;
  }

  SpotifyCredentials credentials;
  credentials.refreshToken = document["refresh_token"].as<const char*>();
  credentials.scopes = document["scopes"].as<const char*>();
  credentials.authorizedAt = document["authorized_at"].as<uint64_t>();
  credentials.formatVersion =
      document["credential_format_version"].as<int>();

  if (!spotifyStorage_.isValid(credentials)) {
    credentials.clear();
    sendMessage(
        "validation_failed", Provider::Spotify, "invalid_credentials");
    resetNegotiation();
    return;
  }

  state_ = State::Storing;
  if (!spotifyStorage_.save(credentials)) {
    credentials.clear();
    sendMessage("storage_failed", Provider::Spotify, "nvs_write_failed");
    resetNegotiation();
    return;
  }

  credentials.clear();
  credentialsChanged_ = true;
  resetNegotiation();
  sendMessage("storage_complete", Provider::Spotify);
  Serial.println("[SPOTIFY][PROVISION] Credenciais armazenadas");
}

void ProvisioningService::handleGoogleCalendarStore(
    JsonObjectConst document) {
  if (document.size() != 8 ||
      !document["credential_format_version"].is<int>() ||
      !document["google_client_id"].is<const char*>() ||
      !document["refresh_token"].is<const char*>() ||
      !document["authorized_at"].is<const char*>() ||
      !document["scopes"].is<const char*>()) {
    sendMessage("validation_failed",
                Provider::GoogleCalendar,
                "invalid_credentials");
    resetNegotiation();
    return;
  }
  if (document["credential_format_version"].as<int>() !=
      AppConfig::GoogleCalendar::storageVersion) {
    sendMessage("validation_failed",
                Provider::GoogleCalendar,
                "invalid_credential_format");
    resetNegotiation();
    return;
  }

  GoogleCalendarCredentials credentials;
  credentials.googleClientId =
      document["google_client_id"].as<const char*>();
  credentials.refreshToken = document["refresh_token"].as<const char*>();
  credentials.authorizedAt = document["authorized_at"].as<const char*>();
  credentials.scopes = document["scopes"].as<const char*>();
  credentials.formatVersion =
      document["credential_format_version"].as<int>();

  if (!googleCalendarStorage_.isValid(credentials)) {
    credentials.clear();
    sendMessage("validation_failed",
                Provider::GoogleCalendar,
                "invalid_credentials");
    resetNegotiation();
    return;
  }

  state_ = State::Storing;
  if (!googleCalendarStorage_.save(credentials)) {
    credentials.clear();
    sendMessage(
        "storage_failed", Provider::GoogleCalendar, "nvs_write_failed");
    resetNegotiation();
    return;
  }

  credentials.clear();
  resetNegotiation();
  sendMessage("storage_complete", Provider::GoogleCalendar);
  Serial.println("[GCAL][PROVISION] Credenciais armazenadas");
}

void ProvisioningService::resetNegotiation() {
  state_ = State::Idle;
  negotiatedProvider_ = Provider::None;
  negotiationStartedMs_ = 0;
}

void ProvisioningService::clearLineBuffer() {
  memset(lineBuffer_, 0, sizeof(lineBuffer_));
  lineLength_ = 0;
}

void ProvisioningService::sendMessage(const char* type,
                                      Provider provider,
                                      const char* reason) {
  JsonDocument response;
  response["protocol"] = AppConfig::Provisioning::protocolVersion;
  response["type"] = type;
  response["provider"] = providerName(provider);
  if (reason != nullptr) {
    response["reason"] = reason;
  }
  serializeJson(response, Serial);
  Serial.println();
}

ProvisioningService::Provider ProvisioningService::parseProvider(
    const char* provider) {
  if (provider == nullptr) {
    return Provider::None;
  }
  if (strcmp(provider, "spotify") == 0) {
    return Provider::Spotify;
  }
  if (strcmp(provider, "google_calendar") == 0) {
    return Provider::GoogleCalendar;
  }
  return Provider::Unknown;
}

const char* ProvisioningService::providerName(Provider provider) {
  switch (provider) {
    case Provider::Spotify:
      return "spotify";
    case Provider::GoogleCalendar:
      return "google_calendar";
    case Provider::None:
    case Provider::Unknown:
      return "unknown";
  }
  return "unknown";
}
