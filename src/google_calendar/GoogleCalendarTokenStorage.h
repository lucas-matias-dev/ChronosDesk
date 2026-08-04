#pragma once

#include "GoogleCalendarCredentials.h"

class GoogleCalendarTokenStorage {
 public:
  bool load(GoogleCalendarCredentials& credentials);
  bool save(const GoogleCalendarCredentials& credentials);
  bool clear();
  bool hasValidCredentials();
  bool isValid(const GoogleCalendarCredentials& credentials) const;
};
