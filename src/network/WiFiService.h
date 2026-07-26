#pragma once

#include <Arduino.h>

enum class WiFiConnectionState {
  Disconnected,
  Connecting,
  Connected
};

class WiFiService {
 public:
  void begin();
  void update(uint32_t nowMs);

  bool isConnected() const;
  bool stateChanged();
  WiFiConnectionState state() const;

 private:
  void requestConnection(uint32_t nowMs);
  void setState(WiFiConnectionState newState);

  WiFiConnectionState state_ = WiFiConnectionState::Disconnected;
  uint32_t lastConnectionAttemptMs_ = 0;
  bool stateChanged_ = false;
};
