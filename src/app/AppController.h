#pragma once

#include "../display/DisplayManager.h"
#include "../input/RotaryEncoderService.h"
#include "../network/WiFiService.h"
#include "../spotify/SpotifyApiService.h"
#include "../spotify/SpotifyAuthService.h"
#include "../spotify/SpotifyPlayback.h"
#include "../spotify/SpotifyProvisioningService.h"
#include "../spotify/SpotifyTokenStorage.h"
#include "../time/TimeService.h"
#include "../ui/CalendarView.h"
#include "../ui/SpotifyView.h"

enum class AppPage : uint8_t {
  Spotify,
  Calendar,
  Count
};

class AppController {
 public:
  AppController();

  void begin();
  void update();

 private:
  void handleInputAction(InputAction action);
  void nextPage();
  void previousPage();
  void setPage(AppPage page);
  void renderCurrentPage();
  void updateSpotify(uint32_t nowMs);
  void handleApiResponse(const SpotifyApiResponse& response, uint32_t nowMs);
  void setViewState(SpotifyViewState state);
  void resetApiBackoff();
  void increaseApiBackoff(uint32_t nowMs);

  DisplayManager displayManager_;
  SpotifyView spotifyView_;
  CalendarView calendarView_;
  RotaryEncoderService rotaryEncoderService_;
  WiFiService wifiService_;
  TimeService timeService_;
  SpotifyTokenStorage tokenStorage_;
  SpotifyProvisioningService provisioningService_;
  SpotifyAuthService authService_;
  SpotifyApiService apiService_;
  SpotifyPlayback playback_;
  AppPage activePage_ = AppPage::Spotify;
  SpotifyViewState viewState_ = SpotifyViewState::Initializing;
  uint32_t lastApiRequestMs_ = 0;
  uint32_t nextApiRequestMs_ = 0;
  uint32_t apiBackoffMs_ = 0;
  uint32_t lastProgressUpdateMs_ = 0;
  bool forceApiRequest_ = true;
  bool started_ = false;
};
