#include "GoogleCalendarTokenStorage.h"

#include <Preferences.h>

#include "../config/AppConfig.h"

namespace {
constexpr char storageNamespace[] = "gcal";
constexpr char activeSlotKey[] = "active";
constexpr uint8_t invalidSlot = 0xff;
constexpr char versionKeys[][5] = {"ver0", "ver1"};
constexpr char clientIdKeys[][8] = {"client0", "client1"};
constexpr char refreshTokenKeys[][9] = {"refresh0", "refresh1"};
constexpr char authorizedAtKeys[][9] = {"auth_at0", "auth_at1"};
constexpr char scopesKeys[][8] = {"scopes0", "scopes1"};

bool isDigit(char value) {
  return value >= '0' && value <= '9';
}

uint16_t parseDigits(const String& value, size_t offset, size_t count) {
  uint16_t parsed = 0;
  for (size_t index = 0; index < count; ++index) {
    parsed = parsed * 10 + static_cast<uint16_t>(value[offset + index] - '0');
  }
  return parsed;
}

bool isLeapYear(uint16_t year) {
  return (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
}

bool isValidUtcTimestamp(const String& value) {
  if (value.length() != AppConfig::GoogleCalendar::maximumTimestampLength ||
      value[4] != '-' || value[7] != '-' || value[10] != 'T' ||
      value[13] != ':' || value[16] != ':' || value[19] != 'Z') {
    return false;
  }
  constexpr uint8_t digitIndexes[] = {
      0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18};
  for (uint8_t index : digitIndexes) {
    if (!isDigit(value[index])) {
      return false;
    }
  }

  const uint16_t year = parseDigits(value, 0, 4);
  const uint8_t month = static_cast<uint8_t>(parseDigits(value, 5, 2));
  const uint8_t day = static_cast<uint8_t>(parseDigits(value, 8, 2));
  const uint8_t hour = static_cast<uint8_t>(parseDigits(value, 11, 2));
  const uint8_t minute = static_cast<uint8_t>(parseDigits(value, 14, 2));
  const uint8_t second = static_cast<uint8_t>(parseDigits(value, 17, 2));
  if (year < 2000 || month < 1 || month > 12 || hour > 23 || minute > 59 ||
      second > 59) {
    return false;
  }
  constexpr uint8_t daysPerMonth[] = {
      31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
  uint8_t maximumDay = daysPerMonth[month - 1];
  if (month == 2 && isLeapYear(year)) {
    maximumDay = 29;
  }
  return day >= 1 && day <= maximumDay;
}

bool hasBoundaryWhitespace(const String& value) {
  if (value.isEmpty()) {
    return false;
  }
  const char first = value[0];
  const char last = value[value.length() - 1];
  return first == ' ' || first == '\t' || first == '\r' || first == '\n' ||
         last == ' ' || last == '\t' || last == '\r' || last == '\n';
}

void readSlot(Preferences& preferences,
              uint8_t slot,
              GoogleCalendarCredentials& credentials) {
  credentials.clear();
  credentials.formatVersion = preferences.getUChar(versionKeys[slot], 0);
  credentials.googleClientId = preferences.getString(clientIdKeys[slot], "");
  credentials.refreshToken =
      preferences.getString(refreshTokenKeys[slot], "");
  credentials.authorizedAt =
      preferences.getString(authorizedAtKeys[slot], "");
  credentials.scopes = preferences.getString(scopesKeys[slot], "");
}

void removeSlot(Preferences& preferences, uint8_t slot) {
  preferences.remove(versionKeys[slot]);
  preferences.remove(clientIdKeys[slot]);
  preferences.remove(refreshTokenKeys[slot]);
  preferences.remove(authorizedAtKeys[slot]);
  preferences.remove(scopesKeys[slot]);
}

bool sameCredentials(const GoogleCalendarCredentials& left,
                     const GoogleCalendarCredentials& right) {
  return left.formatVersion == right.formatVersion &&
         left.googleClientId == right.googleClientId &&
         left.refreshToken == right.refreshToken &&
         left.authorizedAt == right.authorizedAt &&
         left.scopes == right.scopes;
}
}  // namespace

bool GoogleCalendarTokenStorage::load(
    GoogleCalendarCredentials& credentials) {
  credentials.clear();
  Preferences preferences;
  if (!preferences.begin(storageNamespace, true)) {
    Serial.println("[GCAL][NVS] Falha ao abrir armazenamento");
    return false;
  }

  const uint8_t activeSlot = preferences.getUChar(activeSlotKey, invalidSlot);
  if (activeSlot <= 1) {
    readSlot(preferences, activeSlot, credentials);
  }
  preferences.end();

  if (activeSlot > 1 || !isValid(credentials)) {
    credentials.clear();
    return false;
  }
  return true;
}

bool GoogleCalendarTokenStorage::save(
    const GoogleCalendarCredentials& credentials) {
  if (!isValid(credentials)) {
    return false;
  }

  Preferences preferences;
  if (!preferences.begin(storageNamespace, false)) {
    return false;
  }

  const uint8_t currentSlot = preferences.getUChar(activeSlotKey, invalidSlot);
  const uint8_t targetSlot = currentSlot == 0 ? 1 : 0;
  removeSlot(preferences, targetSlot);
  const bool written =
      preferences.putUChar(versionKeys[targetSlot], credentials.formatVersion) ==
          sizeof(uint8_t) &&
      preferences.putString(clientIdKeys[targetSlot],
                            credentials.googleClientId) ==
          credentials.googleClientId.length() &&
      preferences.putString(refreshTokenKeys[targetSlot],
                            credentials.refreshToken) ==
          credentials.refreshToken.length() &&
      preferences.putString(authorizedAtKeys[targetSlot],
                            credentials.authorizedAt) ==
          credentials.authorizedAt.length() &&
      preferences.putString(scopesKeys[targetSlot], credentials.scopes) ==
          credentials.scopes.length();

  GoogleCalendarCredentials verified;
  if (written) {
    readSlot(preferences, targetSlot, verified);
  }
  const bool verifiedWrite =
      written && isValid(verified) && sameCredentials(credentials, verified);
  const bool committed =
      verifiedWrite &&
      preferences.putUChar(activeSlotKey, targetSlot) == sizeof(uint8_t);

  if (committed) {
    if (currentSlot <= 1 && currentSlot != targetSlot) {
      removeSlot(preferences, currentSlot);
    }
  } else {
    removeSlot(preferences, targetSlot);
  }
  preferences.end();
  verified.clear();
  return committed;
}

bool GoogleCalendarTokenStorage::clear() {
  Preferences preferences;
  if (!preferences.begin(storageNamespace, false)) {
    return false;
  }
  const bool cleared = preferences.clear();
  preferences.end();
  return cleared;
}

bool GoogleCalendarTokenStorage::hasValidCredentials() {
  GoogleCalendarCredentials credentials;
  const bool valid = load(credentials);
  credentials.clear();
  return valid;
}

bool GoogleCalendarTokenStorage::isValid(
    const GoogleCalendarCredentials& credentials) const {
  return credentials.formatVersion ==
             AppConfig::GoogleCalendar::storageVersion &&
         !credentials.googleClientId.isEmpty() &&
         credentials.googleClientId.length() <=
             AppConfig::GoogleCalendar::maximumClientIdLength &&
         !hasBoundaryWhitespace(credentials.googleClientId) &&
         credentials.refreshToken.length() >=
             AppConfig::GoogleCalendar::minimumRefreshTokenLength &&
         credentials.refreshToken.length() <=
             AppConfig::GoogleCalendar::maximumRefreshTokenLength &&
         !hasBoundaryWhitespace(credentials.refreshToken) &&
         credentials.scopes.length() <=
             AppConfig::GoogleCalendar::maximumScopesLength &&
         credentials.scopes == AppConfig::GoogleCalendar::requiredScope &&
         isValidUtcTimestamp(credentials.authorizedAt);
}
