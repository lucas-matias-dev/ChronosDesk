#pragma once

#include <Arduino.h>

namespace AppConfig {
namespace Display {
constexpr uint8_t chipSelectPin = 5;
constexpr uint8_t dataCommandPin = 2;
constexpr uint8_t resetPin = 4;
}  // namespace Display

namespace Network {
constexpr uint32_t reconnectIntervalMs = 15000;
constexpr uint32_t connectionTimeoutMs = 10000;
}  // namespace Network

namespace Clock {
constexpr char ntpServer[] = "pool.ntp.org";
// POSIX TZ: horario de Brasilia (UTC-3), sem horario de verao automatico.
constexpr char timezone[] = "<-03>3";
constexpr uint32_t pollIntervalMs = 1000;
}  // namespace Clock

namespace Spotify {
constexpr uint8_t protocolVersion = 1;
constexpr uint8_t storageVersion = 1;
constexpr char requiredScope[] = "user-read-currently-playing";
constexpr uint32_t apiPollIntervalMs = 5000;
constexpr uint32_t progressUpdateIntervalMs = 1000;
constexpr uint32_t tokenRefreshMarginSeconds = 120;
constexpr uint32_t requestTimeoutMs = 8000;
constexpr uint32_t initialBackoffMs = 5000;
constexpr uint32_t maximumBackoffMs = 60000;
constexpr size_t maximumResponseBytes = 24576;
constexpr size_t maximumSerialLineBytes = 2048;
constexpr size_t maximumTitleLength = 63;
constexpr size_t maximumArtistLength = 63;
constexpr size_t maximumItemIdLength = 47;
}  // namespace Spotify
}  // namespace AppConfig
