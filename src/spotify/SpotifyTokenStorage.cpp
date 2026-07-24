#include "SpotifyTokenStorage.h"

#include <Preferences.h>

#include "../config/AppConfig.h"

namespace {
constexpr char storageNamespace[] = "spotify";
constexpr char versionKey[] = "version";
constexpr char tokenKey[] = "refresh";
constexpr char scopesKey[] = "scopes";
constexpr char authorizedAtKey[] = "auth_at";
constexpr size_t minimumTokenLength = 16;
constexpr size_t maximumTokenLength = 1024;
}

bool SpotifyTokenStorage::load(SpotifyCredentials& credentials) {
  credentials.clear();
  Preferences preferences;
  if (!preferences.begin(storageNamespace, true)) {
    Serial.println("[SPOTIFY][NVS] Falha ao abrir armazenamento");
    return false;
  }

  credentials.formatVersion = preferences.getUChar(versionKey, 0);
  credentials.refreshToken = preferences.getString(tokenKey, "");
  credentials.scopes = preferences.getString(scopesKey, "");
  credentials.authorizedAt = preferences.getULong64(authorizedAtKey, 0);
  preferences.end();

  if (!isValid(credentials)) {
    credentials.clear();
    return false;
  }
  return true;
}

bool SpotifyTokenStorage::save(const SpotifyCredentials& credentials) {
  if (!isValid(credentials)) {
    return false;
  }

  Preferences preferences;
  if (!preferences.begin(storageNamespace, false)) {
    return false;
  }
  const bool saved =
      preferences.putUChar(versionKey, AppConfig::Spotify::storageVersion) == 1 &&
      preferences.putString(tokenKey, credentials.refreshToken) > 0 &&
      preferences.putString(scopesKey, credentials.scopes) > 0 &&
      preferences.putULong64(authorizedAtKey, credentials.authorizedAt) ==
          sizeof(uint64_t);
  preferences.end();
  return saved;
}

bool SpotifyTokenStorage::clear() {
  Preferences preferences;
  if (!preferences.begin(storageNamespace, false)) {
    return false;
  }
  const bool cleared = preferences.clear();
  preferences.end();
  return cleared;
}

bool SpotifyTokenStorage::isValid(
    const SpotifyCredentials& credentials) const {
  return credentials.formatVersion == AppConfig::Spotify::storageVersion &&
         credentials.refreshToken.length() >= minimumTokenLength &&
         credentials.refreshToken.length() <= maximumTokenLength &&
         credentials.authorizedAt > 0 &&
         credentials.scopes == AppConfig::Spotify::requiredScope;
}
