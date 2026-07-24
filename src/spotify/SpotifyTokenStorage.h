#pragma once

#include "SpotifyCredentials.h"

class SpotifyTokenStorage {
 public:
  bool load(SpotifyCredentials& credentials);
  bool save(const SpotifyCredentials& credentials);
  bool clear();
  bool isValid(const SpotifyCredentials& credentials) const;
};
