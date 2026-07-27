#pragma once

#include <Arduino.h>

#ifndef ENABLE_RESOURCE_DIAGNOSTICS
#define ENABLE_RESOURCE_DIAGNOSTICS 0
#endif

class ResourceMonitor {
 public:
#if ENABLE_RESOURCE_DIAGNOSTICS
  static void begin();
  static void update(uint32_t nowMs);
  static void checkpoint(const char* name);
  static void recordWiFiReconnect();
  static void recordSpotifyRequest();
  static void recordSpotifyFailure();
  static void recordHttpStatus(int statusCode);
#else
  static void begin() {}
  static void update(uint32_t) {}
  static void checkpoint(const char*) {}
  static void recordWiFiReconnect() {}
  static void recordSpotifyRequest() {}
  static void recordSpotifyFailure() {}
  static void recordHttpStatus(int) {}
#endif
};
