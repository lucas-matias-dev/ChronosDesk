#pragma once

#include <Arduino.h>

#include "../config/AppConfig.h"

enum class SpotifyContentType {
  None,
  Track,
  Episode,
  Unsupported
};

struct SpotifyPlayback {
  char itemId[AppConfig::Spotify::maximumItemIdLength + 1] {};
  char title[AppConfig::Spotify::maximumTitleLength + 1] {};
  char artists[AppConfig::Spotify::maximumArtistLength + 1] {};
  SpotifyContentType contentType = SpotifyContentType::None;
  uint32_t durationMs = 0;
  uint32_t progressMs = 0;
  uint32_t progressUpdatedAtMs = 0;
  bool isPlaying = false;
  bool hasItem = false;

  void clear();
  void advanceProgress(uint32_t nowMs);
};
