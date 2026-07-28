import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google_calendar.auth import GoogleAuthorization
from google_calendar.config import GoogleCalendarConfig
from google_calendar.errors import GoogleOAuthError
from google_calendar.use_case import GoogleCalendarValidationUseCase


TZ = ZoneInfo("America/Sao_Paulo")


class StubOAuth:
    def __init__(self, refresh_token_received):
        self.result = GoogleAuthorization(object(), refresh_token_received)

    def authorize(self, config, timeout_seconds):
        return self.result


class StubPresenter:
    def __init__(self):
        self.authorization = None
        self.day = None

    def authorization_succeeded(self, refresh_token_received):
        self.authorization = refresh_token_received

    def show_day(self, day):
        self.day = day


class EmptySession:
    def get(self, _url, *, params, timeout):
        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {"items": []}

        return Response()


class GoogleCalendarUseCaseTests(unittest.TestCase):
    def setUp(self):
        self.config = GoogleCalendarConfig(
            Path("fake.json"), TZ.key, TZ
        )

    def test_missing_refresh_token_stops_before_http_session(self):
        presenter = StubPresenter()
        session_calls = []

        def session_factory(credentials):
            session_calls.append(credentials)
            return EmptySession()

        use_case = GoogleCalendarValidationUseCase(
            StubOAuth(False),
            presenter,
            session_factory=session_factory,
        )
        with self.assertRaisesRegex(GoogleOAuthError, "refresh token"):
            use_case.execute(self.config, 10)
        self.assertFalse(presenter.authorization)
        self.assertEqual(session_calls, [])

    def test_success_lists_empty_day_without_persisting_credentials(self):
        presenter = StubPresenter()
        use_case = GoogleCalendarValidationUseCase(
            StubOAuth(True),
            presenter,
            session_factory=lambda _credentials: EmptySession(),
            clock=lambda: datetime(2026, 7, 27, 12, tzinfo=TZ),
        )
        use_case.execute(self.config, 10)
        self.assertTrue(presenter.authorization)
        self.assertEqual(presenter.day.total, 0)


if __name__ == "__main__":
    unittest.main()
