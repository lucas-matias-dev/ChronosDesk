#pragma once

#include <Arduino.h>

#include "SpotifyPlayback.h"

enum class SpotifyApiResult {
  PlaybackAvailable,
  NothingPlaying,
  Unauthorized,
  Forbidden,
  RateLimited,
  TemporaryFailure,
  InvalidResponse
};

struct SpotifyApiResponse {
  SpotifyApiResult result = SpotifyApiResult::TemporaryFailure;
  uint32_t retryAfterMs = 0;
};

class SpotifyApiService {
 public:
  SpotifyApiResponse fetchCurrentPlayback(const String& accessToken,
                                          uint32_t nowMs,
                                          SpotifyPlayback& playback);

 private:
  bool parsePlayback(Stream& stream,
                     uint32_t nowMs,
                     SpotifyPlayback& playback);
};
