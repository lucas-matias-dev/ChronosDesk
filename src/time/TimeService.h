#pragma once

#include <Arduino.h>
#include <time.h>

class TimeService {
 public:
  void begin();
  void update(uint32_t nowMs, bool networkAvailable);

  bool hasValidTime() const;
  bool minuteChanged();
  void formatDateTime(char* destination, size_t destinationSize) const;

 private:
  bool readLocalTime(struct tm& destination) const;

  bool configured_ = false;
  bool validTime_ = false;
  bool minuteChanged_ = false;
  bool synchronizationLogged_ = false;
  int32_t lastMinuteKey_ = -1;
  uint32_t lastPollMs_ = 0;
  struct tm currentTime_ {};
};
