#pragma once

#include <Arduino.h>

struct GoogleCalendarCredentials {
  String googleClientId;
  String refreshToken;
  String authorizedAt;
  String scopes;
  uint8_t formatVersion = 0;

  void clear() {
    googleClientId = "";
    refreshToken = "";
    authorizedAt = "";
    scopes = "";
    formatVersion = 0;
  }
};
