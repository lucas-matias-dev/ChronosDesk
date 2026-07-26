#include "SpotifyProvisioningService.h"

#include <ArduinoJson.h>

#include "../config/AppConfig.h"

SpotifyProvisioningService::SpotifyProvisioningService(
    SpotifyTokenStorage& storage)
    : storage_(storage) {}

void SpotifyProvisioningService::update() {
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
      lineLength_ = 0;
      discardLine_ = false;
      continue;
    }
    if (discardLine_) {
      continue;
    }
    if (lineLength_ >= AppConfig::Spotify::maximumSerialLineBytes) {
      discardLine_ = true;
      sendMessage("validation_failed", "message_too_large");
      continue;
    }
    lineBuffer_[lineLength_++] = character;
  }
}

bool SpotifyProvisioningService::credentialsChanged() {
  const bool changed = credentialsChanged_;
  credentialsChanged_ = false;
  return changed;
}

void SpotifyProvisioningService::handleLine(const char* line) {
  JsonDocument document;
  if (deserializeJson(document, line) != DeserializationError::Ok) {
    sendMessage("validation_failed", "invalid_json");
    return;
  }

  const int protocol = document["protocol"] | 0;
  if (protocol != AppConfig::Spotify::protocolVersion) {
    sendMessage("incompatible_version", "unsupported_protocol");
    return;
  }

  const char* type = document["type"] | "";
  if (strcmp(type, "provision_begin") == 0) {
    sendMessage("provision_ready");
    return;
  }
  if (strcmp(type, "erase_credentials") == 0) {
    if (storage_.clear()) {
      credentialsChanged_ = true;
      sendMessage("credentials_erased");
    } else {
      sendMessage("storage_failed", "erase_failed");
    }
    return;
  }
  if (strcmp(type, "store_credentials") != 0) {
    sendMessage("validation_failed", "unknown_message");
    return;
  }

  SpotifyCredentials credentials;
  credentials.refreshToken = document["refresh_token"] | "";
  credentials.scopes = document["scopes"] | "";
  credentials.authorizedAt = document["authorized_at"] | 0ULL;
  credentials.formatVersion = AppConfig::Spotify::storageVersion;

  if (!storage_.isValid(credentials)) {
    credentials.clear();
    sendMessage("validation_failed", "invalid_credentials");
    return;
  }

  if (!storage_.save(credentials)) {
    credentials.clear();
    sendMessage("storage_failed", "nvs_write_failed");
    return;
  }

  credentials.clear();
  credentialsChanged_ = true;
  sendMessage("storage_complete");
  Serial.println("[SPOTIFY][PROVISION] Credenciais armazenadas");
}

void SpotifyProvisioningService::sendMessage(const char* type,
                                              const char* reason) {
  JsonDocument response;
  response["protocol"] = AppConfig::Spotify::protocolVersion;
  response["type"] = type;
  if (reason != nullptr) {
    response["reason"] = reason;
  }
  serializeJson(response, Serial);
  Serial.println();
}
