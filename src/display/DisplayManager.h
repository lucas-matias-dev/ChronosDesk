#pragma once

#include <Adafruit_ST7735.h>

class DisplayManager {
 public:
  DisplayManager();

  void begin();
  Adafruit_ST7735& screen();

 private:
  Adafruit_ST7735 display_;
};
