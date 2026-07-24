#pragma once

#include <Arduino.h>

struct SpotifyCredentials {
  String refreshToken;
  String scopes;
  uint64_t authorizedAt = 0;
  uint8_t formatVersion = 0;

  void clear() {
    refreshToken = "";
    scopes = "";
    authorizedAt = 0;
    formatVersion = 0;
  }
};
