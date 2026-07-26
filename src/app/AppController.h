#pragma once

#include "../display/DisplayManager.h"
#include "../network/WiFiService.h"
#include "../spotify/SpotifyApiService.h"
#include "../spotify/SpotifyAuthService.h"
#include "../spotify/SpotifyPlayback.h"
#include "../spotify/SpotifyProvisioningService.h"
#include "../spotify/SpotifyTokenStorage.h"
#include "../time/TimeService.h"
#include "../ui/SpotifyView.h"

class AppController {
 public:
  AppController();

  void begin();
  void update();

 private:
  void updateSpotify(uint32_t nowMs);
  void handleApiResponse(const SpotifyApiResponse& response, uint32_t nowMs);
  void setViewState(SpotifyViewState state);
  void resetApiBackoff();
  void increaseApiBackoff(uint32_t nowMs);

  DisplayManager displayManager_;
  SpotifyView spotifyView_;
  WiFiService wifiService_;
  TimeService timeService_;
  SpotifyTokenStorage tokenStorage_;
  SpotifyProvisioningService provisioningService_;
  SpotifyAuthService authService_;
  SpotifyApiService apiService_;
  SpotifyPlayback playback_;
  SpotifyViewState viewState_ = SpotifyViewState::Initializing;
  uint32_t lastApiRequestMs_ = 0;
  uint32_t nextApiRequestMs_ = 0;
  uint32_t apiBackoffMs_ = 0;
  uint32_t lastProgressUpdateMs_ = 0;
  bool forceApiRequest_ = true;
  bool started_ = false;
};
