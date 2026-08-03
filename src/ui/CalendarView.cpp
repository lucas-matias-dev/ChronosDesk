#include "CalendarView.h"

#include <Adafruit_GFX.h>

namespace {
constexpr int16_t footerHeight = 19;
constexpr int16_t clockX = 5;
constexpr int16_t wifiX = 120;
}

CalendarView::CalendarView(DisplayManager& displayManager)
    : displayManager_(displayManager) {}

void CalendarView::draw() {
  Adafruit_ST7735& display = displayManager_.screen();
  display.fillScreen(ST7735_BLUE);
  display.setTextWrap(false);
  display.setTextSize(2);
  display.setTextColor(ST7735_CYAN);
  display.setCursor(4, 5);
  display.print("CALENDARIO");
  display.drawFastHLine(0, 24, display.width(), ST7735_CYAN);

  display.setTextSize(1);
  display.setTextColor(ST7735_WHITE);
  display.setCursor(17, 44);
  display.print("Pagina de teste");
  display.setTextColor(ST7735_YELLOW);
  display.setCursor(20, 68);
  display.print("Google Calendar");
  display.setTextColor(ST7735_WHITE);
  display.setCursor(25, 84);
  display.print("ainda nao");
  display.setCursor(37, 96);
  display.print("integrado");

  display.drawFastHLine(
      0, display.height() - footerHeight, display.width(), ST7735_WHITE);
  updateDateTime("--/--/--  --:--", false);
  updateWiFi(false);
  Serial.println("[UI] Tela Calendario estatica desenhada");
}

void CalendarView::updateDateTime(const char* formattedDateTime, bool valid) {
  Adafruit_ST7735& display = displayManager_.screen();
  const int16_t clockY = display.height() - 12;
  display.fillRect(clockX, clockY, 105, 9, ST7735_BLUE);
  display.setTextSize(1);
  display.setTextColor(valid ? ST7735_GREEN : ST7735_YELLOW);
  display.setCursor(clockX, clockY);
  display.print(formattedDateTime);
}

void CalendarView::updateWiFi(bool connected) {
  Adafruit_ST7735& display = displayManager_.screen();
  const int16_t wifiY = display.height() - 5;
  const uint16_t color = connected ? ST7735_GREEN : ST7735_RED;
  display.fillRect(wifiX - 10, wifiY - 10, 21, 15, ST7735_BLUE);
  display.fillCircle(wifiX, wifiY, 2, color);
  display.drawCircle(wifiX, wifiY, 5, color);
  display.drawCircle(wifiX, wifiY, 9, color);
  display.fillRect(wifiX - 10, wifiY + 1, 21, 10, ST7735_BLUE);
  display.fillTriangle(
      wifiX, wifiY, wifiX - 10, wifiY, wifiX - 10, wifiY - 10, ST7735_BLUE);
  display.fillTriangle(
      wifiX, wifiY, wifiX + 10, wifiY, wifiX + 10, wifiY - 10, ST7735_BLUE);
}
