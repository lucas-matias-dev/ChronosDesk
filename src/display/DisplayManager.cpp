#include "DisplayManager.h"

#include "../config/AppConfig.h"

DisplayManager::DisplayManager()
    : display_(AppConfig::Display::chipSelectPin,
               AppConfig::Display::dataCommandPin,
               AppConfig::Display::resetPin) {}

void DisplayManager::begin() {
  display_.initR(INITR_BLACKTAB);
  display_.setTextWrap(false);
  Serial.println("[DISPLAY] Inicializado");
}

Adafruit_ST7735& DisplayManager::screen() {
  return display_;
}
