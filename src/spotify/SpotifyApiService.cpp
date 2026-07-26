#include "SpotifyApiService.h"

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>

#include "../config/AppConfig.h"
#include "../diagnostics/ResourceMonitor.h"
#include "SpotifyCertificates.h"

namespace {
constexpr char playbackEndpoint[] =
    "https://api.spotify.com/v1/me/player/currently-playing"
    "?additional_types=track,episode";
constexpr char retryAfterHeader[] = "Retry-After";

class BoundedStream : public Stream {
 public:
  BoundedStream(Stream& source, size_t maximumBytes)
      : source_(source), maximumBytes_(maximumBytes) {}

  int available() override {
    if (bytesRead_ >= maximumBytes_) {
      return 0;
    }
    return min(
        source_.available(), static_cast<int>(maximumBytes_ - bytesRead_));
  }

  int read() override {
    if (bytesRead_ >= maximumBytes_) {
      limitReached_ = true;
      return -1;
    }
    const int value = source_.read();
    if (value >= 0) {
      ++bytesRead_;
    }
    return value;
  }

  int peek() override {
    if (bytesRead_ >= maximumBytes_) {
      limitReached_ = true;
      return -1;
    }
    return source_.peek();
  }

  void flush() override {
    source_.flush();
  }

  size_t write(uint8_t) override {
    return 0;
  }

  bool limitReached() const {
    return limitReached_;
  }

 private:
  Stream& source_;
  size_t maximumBytes_;
  size_t bytesRead_ = 0;
  bool limitReached_ = false;
};

void copyText(char* destination, size_t size, const char* source) {
  if (size == 0) {
    return;
  }
  snprintf(destination, size, "%s", source == nullptr ? "" : source);
}
}

SpotifyApiResponse SpotifyApiService::fetchCurrentPlayback(
    const String& accessToken,
    uint32_t nowMs,
    SpotifyPlayback& playback) {
  NetworkClientSecure client;
  client.setCACert(spotifyRootCa);
  client.setHandshakeTimeout(AppConfig::Spotify::requestTimeoutMs / 1000);

  HTTPClient http;
  http.setConnectTimeout(AppConfig::Spotify::requestTimeoutMs);
  http.setTimeout(AppConfig::Spotify::requestTimeoutMs);
  if (!http.begin(client, playbackEndpoint)) {
    return {SpotifyApiResult::TemporaryFailure, 0};
  }

  const char* collectedHeaders[] = {retryAfterHeader};
  http.collectHeaders(collectedHeaders, 1);
  http.addHeader("Authorization", "Bearer " + accessToken);
  http.addHeader("Accept", "application/json");
  const int statusCode = http.GET();
  ResourceMonitor::recordHttpStatus(statusCode);
  ResourceMonitor::checkpoint("spotify:playback_https_complete");
  Serial.printf("[SPOTIFY][API] HTTP %d\n", statusCode);

  SpotifyApiResponse response;
  switch (statusCode) {
    case 200:
      if (http.getSize() > static_cast<int>(AppConfig::Spotify::maximumResponseBytes)) {
        response.result = SpotifyApiResult::InvalidResponse;
      } else {
        BoundedStream stream(
            *http.getStreamPtr(), AppConfig::Spotify::maximumResponseBytes);
        const bool parsed = parsePlayback(stream, nowMs, playback);
        ResourceMonitor::checkpoint("spotify:playback_json_parsed");
        response.result = parsed && !stream.limitReached()
                              ? SpotifyApiResult::PlaybackAvailable
                              : SpotifyApiResult::InvalidResponse;
      }
      break;
    case 204:
      playback.clear();
      response.result = SpotifyApiResult::NothingPlaying;
      break;
    case 401:
      response.result = SpotifyApiResult::Unauthorized;
      break;
    case 403:
      response.result = SpotifyApiResult::Forbidden;
      break;
    case 429: {
      response.result = SpotifyApiResult::RateLimited;
      const long headerSeconds = http.header(retryAfterHeader).toInt();
      const uint32_t seconds =
          headerSeconds > 0 ? static_cast<uint32_t>(headerSeconds) : 1UL;
      response.retryAfterMs = seconds * 1000UL;
      break;
    }
    default:
      response.result =
          statusCode >= 500 || statusCode < 0
              ? SpotifyApiResult::TemporaryFailure
              : SpotifyApiResult::InvalidResponse;
      break;
  }
  http.end();
  return response;
}

bool SpotifyApiService::parsePlayback(Stream& stream,
                                      uint32_t nowMs,
                                      SpotifyPlayback& playback) {
  JsonDocument filter;
  filter["progress_ms"] = true;
  filter["is_playing"] = true;
  filter["currently_playing_type"] = true;
  filter["item"]["id"] = true;
  filter["item"]["name"] = true;
  filter["item"]["duration_ms"] = true;
  filter["item"]["type"] = true;
  filter["item"]["artists"][0]["name"] = true;
  filter["item"]["show"]["name"] = true;

  JsonDocument document;
  const DeserializationError error = deserializeJson(
      document, stream, DeserializationOption::Filter(filter));
  if (error != DeserializationError::Ok || document["item"].isNull()) {
    return false;
  }

  SpotifyPlayback parsed;
  const char* type = document["item"]["type"] | "";
  if (type[0] == '\0') {
    type = document["currently_playing_type"] | "";
  }
  parsed.contentType =
      strcmp(type, "track") == 0
          ? SpotifyContentType::Track
          : strcmp(type, "episode") == 0 ? SpotifyContentType::Episode
                                          : SpotifyContentType::Unsupported;
  if (parsed.contentType == SpotifyContentType::Unsupported) {
    return false;
  }

  copyText(parsed.itemId, sizeof(parsed.itemId), document["item"]["id"] | "");
  copyText(parsed.title, sizeof(parsed.title), document["item"]["name"] | "");
  if (parsed.contentType == SpotifyContentType::Track) {
    String artists;
    size_t artistCount = 0;
    JsonArray artistArray = document["item"]["artists"].as<JsonArray>();
    for (JsonObject artist : artistArray) {
      const char* name = artist["name"] | "";
      if (name[0] == '\0' || artistCount >= 3) {
        continue;
      }
      if (!artists.isEmpty()) {
        artists += ", ";
      }
      artists += name;
      ++artistCount;
      if (artists.length() >= AppConfig::Spotify::maximumArtistLength) {
        break;
      }
    }
    copyText(parsed.artists, sizeof(parsed.artists), artists.c_str());
  } else {
    copyText(parsed.artists,
             sizeof(parsed.artists),
             document["item"]["show"]["name"] | "");
  }
  parsed.durationMs = document["item"]["duration_ms"] | 0;
  parsed.progressMs = document["progress_ms"] | 0;
  parsed.progressMs = min(parsed.progressMs, parsed.durationMs);
  parsed.progressUpdatedAtMs = nowMs;
  parsed.isPlaying = document["is_playing"] | false;
  parsed.hasItem = parsed.title[0] != '\0' && parsed.durationMs > 0;
  if (!parsed.hasItem) {
    return false;
  }
  playback = parsed;
  return true;
}
