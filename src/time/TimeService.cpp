#include "TimeService.h"

#include "../config/AppConfig.h"
#include "../diagnostics/ResourceMonitor.h"

namespace {
constexpr time_t minimumValidEpoch = 1609459200;  // 2021-01-01 UTC
}

void TimeService::begin() {
  configTzTime(AppConfig::Clock::timezone, AppConfig::Clock::ntpServer);
  configured_ = true;
  Serial.println("[NTP] Configurado; aguardando horario valido");
}

void TimeService::update(uint32_t nowMs, bool networkAvailable) {
  if (!configured_ || nowMs - lastPollMs_ < AppConfig::Clock::pollIntervalMs) {
    return;
  }
  lastPollMs_ = nowMs;
  const bool wasValid = validTime_;

  struct tm localTime {};
  if (!readLocalTime(localTime)) {
    validTime_ = false;
    if (networkAvailable && !synchronizationLogged_) {
      Serial.println("[NTP] Horario ainda indisponivel");
      synchronizationLogged_ = true;
    }
    return;
  }

  currentTime_ = localTime;
  validTime_ = true;

  const int32_t minuteKey =
      (currentTime_.tm_year * 366 + currentTime_.tm_yday) * 1440 +
      currentTime_.tm_hour * 60 + currentTime_.tm_min;
  if (minuteKey != lastMinuteKey_) {
    lastMinuteKey_ = minuteKey;
    minuteChanged_ = true;
  }

  if (!wasValid) {
    ResourceMonitor::checkpoint("ntp:synchronized");
  }
  if (synchronizationLogged_) {
    Serial.println("[NTP] Horario sincronizado");
  }
  synchronizationLogged_ = false;
}

bool TimeService::hasValidTime() const {
  return validTime_;
}

bool TimeService::minuteChanged() {
  const bool changed = minuteChanged_;
  minuteChanged_ = false;
  return changed;
}

void TimeService::formatDateTime(char* destination,
                                 size_t destinationSize) const {
  if (!validTime_) {
    snprintf(destination, destinationSize, "--/--/--  --:--");
    return;
  }
  strftime(destination, destinationSize, "%d/%m/%y  %H:%M", &currentTime_);
}

bool TimeService::readLocalTime(struct tm& destination) const {
  const time_t now = time(nullptr);
  if (now < minimumValidEpoch) {
    return false;
  }
  return localtime_r(&now, &destination) != nullptr;
}
