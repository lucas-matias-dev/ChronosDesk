#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

#include "../config/AppConfig.h"
#include "../google_calendar/GoogleCalendarTokenStorage.h"
#include "../spotify/SpotifyCredentials.h"
#include "../spotify/SpotifyTokenStorage.h"

class ProvisioningService {
 public:
  ProvisioningService(
      SpotifyTokenStorage& spotifyStorage,
      GoogleCalendarTokenStorage& googleCalendarStorage);

  void update();
  bool credentialsChanged();

 private:
  enum class Provider : uint8_t {
    None,
    Spotify,
    GoogleCalendar,
    Unknown
  };

  enum class State : uint8_t {
    Idle,
    Ready,
    ReceivingCredentials,
    Storing
  };

  void handleLine(const char* line);
  void handleStore(JsonObjectConst document, Provider provider);
  void handleSpotifyStore(JsonObjectConst document);
  void handleGoogleCalendarStore(JsonObjectConst document);
  void resetNegotiation();
  void clearLineBuffer();
  void sendMessage(const char* type,
                   Provider provider,
                   const char* reason = nullptr);
  static Provider parseProvider(const char* provider);
  static const char* providerName(Provider provider);

  SpotifyTokenStorage& spotifyStorage_;
  GoogleCalendarTokenStorage& googleCalendarStorage_;
  char lineBuffer_[AppConfig::Provisioning::maximumSerialLineBytes + 1] {};
  size_t lineLength_ = 0;
  size_t discardedBytes_ = 0;
  bool discardLine_ = false;
  bool credentialsChanged_ = false;
  State state_ = State::Idle;
  Provider negotiatedProvider_ = Provider::None;
  uint32_t negotiationStartedMs_ = 0;
};
