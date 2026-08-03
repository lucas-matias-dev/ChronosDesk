#include "AppController.h"

#include <cstring>

#include "../config/AppConfig.h"
#include "../diagnostics/ResourceMonitor.h"

AppController::AppController()
    : spotifyView_(displayManager_),
      calendarView_(displayManager_),
      provisioningService_(tokenStorage_),
      authService_(tokenStorage_) {}

void AppController::begin() {
  Serial.begin(115200);
  ResourceMonitor::begin();
  ResourceMonitor::checkpoint("serial:ready");
  displayManager_.begin();
  ResourceMonitor::checkpoint("display:ready");
  spotifyView_.draw();
  rotaryEncoderService_.begin();
  authService_.begin();
  ResourceMonitor::checkpoint("wifi:before_connect");
  wifiService_.begin();
  ResourceMonitor::checkpoint("ntp:before_config");
  timeService_.begin();
  started_ = true;
}

void AppController::update() {
  if (!started_) {
    return;
  }

  const uint32_t nowMs = millis();
  handleInputAction(rotaryEncoderService_.update());
  ResourceMonitor::update(nowMs);
  provisioningService_.update();
  if (provisioningService_.credentialsChanged()) {
    authService_.reloadCredentials();
    playback_.clear();
    if (activePage_ == AppPage::Spotify) {
      spotifyView_.updatePlayback(playback_);
    }
    forceApiRequest_ = true;
  }

  wifiService_.update(nowMs);
  timeService_.update(nowMs, wifiService_.isConnected());

  if (wifiService_.stateChanged()) {
    if (activePage_ == AppPage::Spotify) {
      spotifyView_.updateWiFi(wifiService_.isConnected());
    } else {
      calendarView_.updateWiFi(wifiService_.isConnected());
    }
  }
  if (timeService_.minuteChanged()) {
    char formattedDateTime[20];
    timeService_.formatDateTime(formattedDateTime, sizeof(formattedDateTime));
    if (activePage_ == AppPage::Spotify) {
      spotifyView_.updateDateTime(
          formattedDateTime, timeService_.hasValidTime());
    } else {
      calendarView_.updateDateTime(
          formattedDateTime, timeService_.hasValidTime());
    }
  }

  updateSpotify(nowMs);
}

void AppController::handleInputAction(InputAction action) {
  switch (action) {
    case InputAction::NextPage:
      nextPage();
      break;
    case InputAction::PreviousPage:
      previousPage();
      break;
    case InputAction::None:
      break;
  }
}

void AppController::nextPage() {
  constexpr uint8_t pageCount = static_cast<uint8_t>(AppPage::Count);
  const uint8_t next =
      (static_cast<uint8_t>(activePage_) + 1) % pageCount;
  setPage(static_cast<AppPage>(next));
}

void AppController::previousPage() {
  constexpr uint8_t pageCount = static_cast<uint8_t>(AppPage::Count);
  const uint8_t previous =
      (static_cast<uint8_t>(activePage_) + pageCount - 1) % pageCount;
  setPage(static_cast<AppPage>(previous));
}

void AppController::setPage(AppPage page) {
  if (page == AppPage::Count || page == activePage_) {
    return;
  }
  activePage_ = page;
  renderCurrentPage();
}

void AppController::renderCurrentPage() {
  char formattedDateTime[20];
  timeService_.formatDateTime(formattedDateTime, sizeof(formattedDateTime));

  switch (activePage_) {
    case AppPage::Spotify:
      spotifyView_.draw();
      spotifyView_.updatePlayback(playback_);
      spotifyView_.updateState(viewState_);
      spotifyView_.updateDateTime(
          formattedDateTime, timeService_.hasValidTime());
      spotifyView_.updateWiFi(wifiService_.isConnected());
      break;
    case AppPage::Calendar:
      calendarView_.draw();
      calendarView_.updateDateTime(
          formattedDateTime, timeService_.hasValidTime());
      calendarView_.updateWiFi(wifiService_.isConnected());
      break;
    case AppPage::Count:
      break;
  }
}

void AppController::updateSpotify(uint32_t nowMs) {
  if (authService_.state() == SpotifyAuthState::NotProvisioned) {
    setViewState(SpotifyViewState::NotConfigured);
    return;
  }
  if (authService_.state() == SpotifyAuthState::ReauthorizationRequired) {
    setViewState(SpotifyViewState::AuthorizationRequired);
    return;
  }
  if (!wifiService_.isConnected()) {
    setViewState(wifiService_.state() == WiFiConnectionState::Connecting
                     ? SpotifyViewState::Connecting
                     : SpotifyViewState::NoWiFi);
    return;
  }
  if (!timeService_.hasValidTime()) {
    setViewState(SpotifyViewState::WaitingForTime);
    return;
  }

  if (!authService_.ensureAccessToken(nowMs)) {
    setViewState(authService_.state() ==
                         SpotifyAuthState::ReauthorizationRequired
                     ? SpotifyViewState::AuthorizationRequired
                     : SpotifyViewState::Authorizing);
    return;
  }

  if (nowMs - lastProgressUpdateMs_ >=
      AppConfig::Spotify::progressUpdateIntervalMs) {
    playback_.advanceProgress(nowMs);
    if (playback_.hasItem && activePage_ == AppPage::Spotify) {
      spotifyView_.updateProgress(playback_);
    }
    lastProgressUpdateMs_ = nowMs;
  }

  const bool intervalElapsed =
      nowMs - lastApiRequestMs_ >= AppConfig::Spotify::apiPollIntervalMs;
  const bool backoffElapsed =
      static_cast<int32_t>(nowMs - nextApiRequestMs_) >= 0;
  if ((!forceApiRequest_ && !intervalElapsed) || !backoffElapsed) {
    return;
  }

  forceApiRequest_ = false;
  lastApiRequestMs_ = nowMs;
  Serial.println("[SPOTIFY][API] Consultando reproducao");
  ResourceMonitor::recordSpotifyRequest();
  ResourceMonitor::checkpoint("spotify:before_currently_playing");
  SpotifyPlayback updatedPlayback = playback_;
  const bool hadItem = playback_.hasItem;
  const bool wasPlaying = playback_.isPlaying;
  char itemBefore[sizeof(playback_.itemId)] {};
  snprintf(itemBefore, sizeof(itemBefore), "%s", playback_.itemId);
  const SpotifyApiResponse response = apiService_.fetchCurrentPlayback(
      authService_.accessToken(), nowMs, updatedPlayback);
  playback_ = updatedPlayback;
  handleApiResponse(response, nowMs);

  if (response.result == SpotifyApiResult::PlaybackAvailable) {
    const bool itemChanged = strcmp(itemBefore, playback_.itemId) != 0;
    if (itemChanged) {
      Serial.println("[SPOTIFY][API] Item atual alterado");
      ResourceMonitor::checkpoint("spotify:item_changed");
    }
    if (activePage_ == AppPage::Spotify) {
      spotifyView_.updatePlayback(playback_);
    }
    if (itemChanged || hadItem != playback_.hasItem ||
        wasPlaying != playback_.isPlaying) {
      ResourceMonitor::checkpoint(
          wasPlaying == playback_.isPlaying
              ? "ui:playback_updated"
              : (playback_.isPlaying ? "ui:resumed" : "ui:paused"));
    }
  }
}

void AppController::handleApiResponse(const SpotifyApiResponse& response,
                                      uint32_t nowMs) {
  switch (response.result) {
    case SpotifyApiResult::PlaybackAvailable:
      resetApiBackoff();
      setViewState(playback_.isPlaying ? SpotifyViewState::Playing
                                       : SpotifyViewState::Paused);
      break;
    case SpotifyApiResult::NothingPlaying:
      resetApiBackoff();
      if (activePage_ == AppPage::Spotify) {
        spotifyView_.updatePlayback(playback_);
      }
      setViewState(SpotifyViewState::NothingPlaying);
      break;
    case SpotifyApiResult::Unauthorized:
      ResourceMonitor::recordSpotifyFailure();
      ResourceMonitor::checkpoint("spotify:http_401");
      authService_.invalidateAccessToken();
      nextApiRequestMs_ = nowMs + AppConfig::Spotify::initialBackoffMs;
      setViewState(SpotifyViewState::Authorizing);
      break;
    case SpotifyApiResult::Forbidden:
      ResourceMonitor::recordSpotifyFailure();
      ResourceMonitor::checkpoint("spotify:http_403");
      increaseApiBackoff(nowMs);
      setViewState(SpotifyViewState::Unavailable);
      break;
    case SpotifyApiResult::RateLimited:
      ResourceMonitor::recordSpotifyFailure();
      ResourceMonitor::checkpoint("spotify:http_429");
      nextApiRequestMs_ = nowMs + max(
          response.retryAfterMs, AppConfig::Spotify::initialBackoffMs);
      setViewState(SpotifyViewState::RateLimited);
      break;
    case SpotifyApiResult::TemporaryFailure:
    case SpotifyApiResult::InvalidResponse:
      ResourceMonitor::recordSpotifyFailure();
      ResourceMonitor::checkpoint("spotify:request_error");
      increaseApiBackoff(nowMs);
      setViewState(SpotifyViewState::Unavailable);
      break;
  }
}

void AppController::setViewState(SpotifyViewState state) {
  if (viewState_ == state) {
    return;
  }
  viewState_ = state;
  if (activePage_ == AppPage::Spotify) {
    spotifyView_.updateState(state);
  }
}

void AppController::resetApiBackoff() {
  apiBackoffMs_ = 0;
  nextApiRequestMs_ = 0;
}

void AppController::increaseApiBackoff(uint32_t nowMs) {
  apiBackoffMs_ =
      apiBackoffMs_ == 0
          ? AppConfig::Spotify::initialBackoffMs
          : min(apiBackoffMs_ * 2, AppConfig::Spotify::maximumBackoffMs);
  nextApiRequestMs_ = nowMs + apiBackoffMs_;
}
