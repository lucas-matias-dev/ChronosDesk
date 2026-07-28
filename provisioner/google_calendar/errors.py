"""Sanitized exceptions for the Google Calendar validation flow."""


class GoogleCalendarError(RuntimeError):
    """Base error whose message is safe to display in the terminal."""


class GoogleCalendarConfigError(GoogleCalendarError):
    """Local configuration is missing or invalid."""


class GoogleOAuthError(GoogleCalendarError):
    """OAuth authorization did not complete safely."""


class GoogleCalendarApiError(GoogleCalendarError):
    """Google Calendar returned an unusable response."""


class CalendarEventParseError(GoogleCalendarError):
    """An event could not be converted to the internal model."""
