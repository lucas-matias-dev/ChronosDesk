#pragma once

#include <Arduino.h>

#include "SpotifyCredentials.h"
#include "SpotifyTokenStorage.h"

enum class SpotifyAuthState {
  NotProvisioned,
  ReadyToRefresh,
  Refreshing,
  Authorized,
  ReauthorizationRequired,
  TemporaryError
};

class SpotifyAuthService {
 public:
  explicit SpotifyAuthService(SpotifyTokenStorage& storage);

  void begin();
  bool ensureAccessToken(uint32_t nowMs);
  void invalidateAccessToken();
  void reloadCredentials();

  bool hasAccessToken(uint32_t nowMs) const;
  const String& accessToken() const;
  SpotifyAuthState state() const;
  bool stateChanged();

 private:
  bool refreshAccessToken(uint32_t nowMs);
  void clearAccessToken();
  void setState(SpotifyAuthState newState);

  SpotifyTokenStorage& storage_;
  SpotifyCredentials credentials_;
  String accessToken_;
  uint32_t refreshAtMs_ = 0;
  uint32_t retryAtMs_ = 0;
  SpotifyAuthState state_ = SpotifyAuthState::NotProvisioned;
  bool stateChanged_ = false;
};
