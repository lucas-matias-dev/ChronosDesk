#include "SpotifyView.h"

#include <Adafruit_GFX.h>

#include <cstring>

namespace {
constexpr int16_t footerHeight = 19;
constexpr int16_t clockX = 5;
constexpr int16_t wifiX = 120;
constexpr int16_t titleY = 31;
constexpr int16_t artistY = 49;
constexpr int16_t playbackStateY = 67;
constexpr int16_t timeY = 83;
constexpr int16_t progressY = 96;
constexpr int16_t statusY = 112;
constexpr int16_t progressX = 5;
constexpr int16_t progressWidth = 118;
constexpr int16_t progressHeight = 7;
constexpr size_t displayLineCharacters = 20;
}

SpotifyView::SpotifyView(DisplayManager& displayManager)
    : displayManager_(displayManager) {}

void SpotifyView::draw() {
  Adafruit_ST7735& display = displayManager_.screen();
  display.fillScreen(ST7735_BLACK);
  display.setTextWrap(false);
  display.setTextSize(2);
  display.setTextColor(ST7735_GREEN);
  display.setCursor(22, 5);
  display.print("Spotify");
  display.drawFastHLine(0, 24, display.width(), ST7735_GREEN);
  display.drawFastHLine(
      0, display.height() - footerHeight, display.width(), ST7735_WHITE);

  printClippedLine("--", 4, titleY);
  printClippedLine("--", 4, artistY);
  updateState(SpotifyViewState::Initializing);
  updateDateTime("--/--/--  --:--", false);
  updateWiFi(false);
  Serial.println("[UI] Tela Spotify desenhada");
}

void SpotifyView::updateDateTime(const char* formattedDateTime, bool valid) {
  Adafruit_ST7735& display = displayManager_.screen();
  const int16_t clockY = display.height() - 12;
  display.fillRect(clockX, clockY, 105, 9, ST7735_BLACK);
  display.setTextSize(1);
  display.setTextColor(valid ? ST7735_GREEN : ST7735_YELLOW);
  display.setCursor(clockX, clockY);
  display.print(formattedDateTime);
}

void SpotifyView::updateWiFi(bool connected) {
  Adafruit_ST7735& display = displayManager_.screen();
  const int16_t wifiY = display.height() - 5;
  const uint16_t color = connected ? ST7735_GREEN : ST7735_RED;
  display.fillRect(wifiX - 10, wifiY - 10, 21, 15, ST7735_BLACK);
  display.fillCircle(wifiX, wifiY, 2, color);
  display.drawCircle(wifiX, wifiY, 5, color);
  display.drawCircle(wifiX, wifiY, 9, color);
  display.fillRect(wifiX - 10, wifiY + 1, 21, 10, ST7735_BLACK);
  display.fillTriangle(
      wifiX, wifiY, wifiX - 10, wifiY, wifiX - 10, wifiY - 10, ST7735_BLACK);
  display.fillTriangle(
      wifiX, wifiY, wifiX + 10, wifiY, wifiX + 10, wifiY - 10, ST7735_BLACK);
}

void SpotifyView::updateState(SpotifyViewState state) {
  Adafruit_ST7735& display = displayManager_.screen();
  display.fillRect(0, statusY, display.width(), 10, ST7735_BLACK);
  display.setCursor(2, statusY);
  display.setTextSize(1);
  display.setTextColor(ST7735_YELLOW);

  switch (state) {
    case SpotifyViewState::Initializing:
      display.print("Inicializando...");
      break;
    case SpotifyViewState::NotConfigured:
      display.print("Spotify nao configurado");
      break;
    case SpotifyViewState::Connecting:
      display.print("Conectando...");
      break;
    case SpotifyViewState::WaitingForTime:
      display.print("Sincronizando hora");
      break;
    case SpotifyViewState::Authorizing:
      display.print("Autenticando Spotify");
      break;
    case SpotifyViewState::Playing:
      display.setTextColor(ST7735_GREEN);
      display.print("Tocando");
      break;
    case SpotifyViewState::Paused:
      display.print("Pausado");
      break;
    case SpotifyViewState::NothingPlaying:
      display.print("Nada tocando");
      break;
    case SpotifyViewState::AuthorizationRequired:
      display.setTextColor(ST7735_RED);
      display.print("Autorizacao necessaria");
      break;
    case SpotifyViewState::RateLimited:
      display.setTextColor(ST7735_RED);
      display.print("Limite de requisicoes");
      break;
    case SpotifyViewState::Unavailable:
      display.setTextColor(ST7735_RED);
      display.print("Spotify indisponivel");
      break;
    case SpotifyViewState::NoWiFi:
      display.setTextColor(ST7735_RED);
      display.print("Sem Wi-Fi");
      break;
  }
}

void SpotifyView::updatePlayback(const SpotifyPlayback& playback) {
  Adafruit_ST7735& display = displayManager_.screen();
  display.fillRect(0, titleY, display.width(), 55, ST7735_BLACK);
  if (!playback.hasItem) {
    printClippedLine("--", 4, titleY);
    printClippedLine("--", 4, artistY);
    updateProgress(playback);
    return;
  }

  printClippedLine(playback.title, 4, titleY);
  printClippedLine(playback.artists, 4, artistY);
  display.setTextSize(1);
  display.setTextColor(playback.isPlaying ? ST7735_GREEN : ST7735_YELLOW);
  display.setCursor(4, playbackStateY);
  display.print(playback.isPlaying ? "> TOCANDO" : "|| PAUSADO");
  updateProgress(playback);
}

void SpotifyView::updateProgress(const SpotifyPlayback& playback) {
  Adafruit_ST7735& display = displayManager_.screen();
  char current[8];
  char duration[8];
  formatDuration(playback.progressMs, current, sizeof(current));
  formatDuration(playback.durationMs, duration, sizeof(duration));

  display.fillRect(0, timeY, display.width(), 22, ST7735_BLACK);
  display.setTextSize(1);
  display.setTextColor(ST7735_WHITE);
  display.setCursor(progressX, timeY);
  display.print(current);
  display.setCursor(98, timeY);
  display.print(duration);
  display.drawRect(
      progressX, progressY, progressWidth, progressHeight, ST7735_WHITE);

  const uint32_t innerWidth =
      playback.durationMs == 0
          ? 0
          : (static_cast<uint64_t>(playback.progressMs) *
             (progressWidth - 2)) /
                playback.durationMs;
  display.fillRect(progressX + 1,
                   progressY + 1,
                   progressWidth - 2,
                   progressHeight - 2,
                   ST7735_BLACK);
  if (innerWidth > 0) {
    display.fillRect(progressX + 1,
                     progressY + 1,
                     innerWidth,
                     progressHeight - 2,
                     ST7735_GREEN);
  }
}

void SpotifyView::printClippedLine(const char* text, int16_t x, int16_t y) {
  char line[displayLineCharacters + 1] {};
  snprintf(line, sizeof(line), "%s", text == nullptr ? "" : text);
  if (text != nullptr && strlen(text) > displayLineCharacters) {
    line[displayLineCharacters - 2] = '.';
    line[displayLineCharacters - 1] = '.';
  }

  Adafruit_ST7735& display = displayManager_.screen();
  display.setTextSize(1);
  display.setTextColor(ST7735_WHITE);
  display.setCursor(x, y);
  display.print(line);
}

void SpotifyView::formatDuration(uint32_t milliseconds,
                                 char* destination,
                                 size_t destinationSize) {
  const uint32_t totalSeconds = milliseconds / 1000;
  snprintf(destination,
           destinationSize,
           "%lu:%02lu",
           static_cast<unsigned long>(totalSeconds / 60),
           static_cast<unsigned long>(totalSeconds % 60));
}
