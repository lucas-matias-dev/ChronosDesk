#pragma once

#include <Arduino.h>

#include "../config/AppConfig.h"
#include "SpotifyCredentials.h"
#include "SpotifyTokenStorage.h"

class SpotifyProvisioningService {
 public:
  explicit SpotifyProvisioningService(SpotifyTokenStorage& storage);

  void update();
  bool credentialsChanged();

 private:
  void handleLine(const char* line);
  void sendMessage(const char* type, const char* reason = nullptr);

  SpotifyTokenStorage& storage_;
  char lineBuffer_[AppConfig::Spotify::maximumSerialLineBytes + 1] {};
  size_t lineLength_ = 0;
  bool discardLine_ = false;
  bool credentialsChanged_ = false;
};
