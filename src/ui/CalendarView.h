#pragma once

#include <Arduino.h>

#include "../display/DisplayManager.h"

class CalendarView {
 public:
  explicit CalendarView(DisplayManager& displayManager);

  void draw();
  void updateDateTime(const char* formattedDateTime, bool valid);
  void updateWiFi(bool connected);

 private:
  DisplayManager& displayManager_;
};
