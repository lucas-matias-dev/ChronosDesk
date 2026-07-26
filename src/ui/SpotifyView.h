#pragma once

#include <Arduino.h>

#include "../display/DisplayManager.h"
#include "../spotify/SpotifyPlayback.h"

enum class SpotifyViewState {
  Initializing,
  NotConfigured,
  Connecting,
  WaitingForTime,
  Authorizing,
  Playing,
  Paused,
  NothingPlaying,
  AuthorizationRequired,
  RateLimited,
  Unavailable,
  NoWiFi
};

class SpotifyView {
 public:
  explicit SpotifyView(DisplayManager& displayManager);

  void draw();
  void updateDateTime(const char* formattedDateTime, bool valid);
  void updateWiFi(bool connected);
  void updateState(SpotifyViewState state);
  void updatePlayback(const SpotifyPlayback& playback);
  void updateProgress(const SpotifyPlayback& playback);

 private:
  void printClippedLine(const char* text, int16_t x, int16_t y);
  void formatDuration(uint32_t milliseconds,
                      char* destination,
                      size_t destinationSize);

  DisplayManager& displayManager_;
};
