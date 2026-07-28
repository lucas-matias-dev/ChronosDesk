import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from google_calendar.client import (
    EVENTS_ENDPOINT,
    EVENT_FIELDS,
    GoogleCalendarClient,
)
from google_calendar.errors import GoogleCalendarApiError


TZ = ZoneInfo("America/Sao_Paulo")
START = datetime(2026, 7, 27, tzinfo=TZ)
END = datetime(2026, 7, 28, tzinfo=TZ)


class FakeResponse:
    def __init__(self, status_code=200, document=None, json_error=None, headers=None):
        self.status_code = status_code
        self.document = {"items": []} if document is None else document
        self.json_error = json_error
        self.headers = headers or {}

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.document


class QueueSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, dict(params), timeout))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class GoogleCalendarClientTests(unittest.TestCase):
    def make_client(self, outcomes, **kwargs):
        self.session = QueueSession(outcomes)
        self.sleeps = []
        return GoogleCalendarClient(
            self.session, sleeper=self.sleeps.append, **kwargs
        )

    def test_success_uses_primary_calendar_restricted_fields_and_day(self):
        item = {"id": "fake", "start": {"date": "2026-07-27"}}
        client = self.make_client([FakeResponse(document={"items": [item]})])
        self.assertEqual(client.list_events(START, END, TZ.key), [item])
        url, params, timeout = self.session.calls[0]
        self.assertEqual(url, EVENTS_ENDPOINT)
        self.assertIn("/primary/events", url)
        self.assertEqual(params["timeMin"], START.isoformat())
        self.assertEqual(params["timeMax"], END.isoformat())
        self.assertEqual(params["singleEvents"], "true")
        self.assertEqual(params["orderBy"], "startTime")
        self.assertEqual(params["showDeleted"], "false")
        self.assertEqual(params["fields"], EVENT_FIELDS)
        self.assertNotIn("description", params["fields"])
        self.assertEqual(timeout, 15)

    def test_multiple_pages(self):
        client = self.make_client(
            [
                FakeResponse(
                    document={"items": [{"id": "1"}], "nextPageToken": "next"}
                ),
                FakeResponse(document={"items": [{"id": "2"}]}),
            ]
        )
        self.assertEqual(
            [item["id"] for item in client.list_events(START, END, TZ.key)],
            ["1", "2"],
        )
        self.assertNotIn("pageToken", self.session.calls[0][1])
        self.assertEqual(self.session.calls[1][1]["pageToken"], "next")

    def test_absent_next_page_token_stops(self):
        client = self.make_client([FakeResponse(document={"items": []})])
        client.list_events(START, END, TZ.key)
        self.assertEqual(len(self.session.calls), 1)

    def test_defensive_page_limit(self):
        client = self.make_client(
            [
                FakeResponse(document={"items": [], "nextPageToken": "a"}),
                FakeResponse(document={"items": [], "nextPageToken": "b"}),
            ],
            max_pages=2,
        )
        with self.assertRaisesRegex(GoogleCalendarApiError, "limite defensivo"):
            client.list_events(START, END, TZ.key)

    def test_http_400_401_403_do_not_retry(self):
        for status in (400, 401, 403):
            with self.subTest(status=status):
                client = self.make_client([FakeResponse(status)])
                with self.assertRaisesRegex(GoogleCalendarApiError, str(status)):
                    client.list_events(START, END, TZ.key)
                self.assertEqual(len(self.session.calls), 1)
                self.assertEqual(self.sleeps, [])

    def test_http_429_retries_with_limit(self):
        client = self.make_client(
            [
                FakeResponse(429, headers={"Retry-After": "1"}),
                FakeResponse(429),
                FakeResponse(document={"items": []}),
            ]
        )
        client.list_events(START, END, TZ.key)
        self.assertEqual(len(self.session.calls), 3)
        self.assertEqual(self.sleeps, [1.0, 1.0])

    def test_http_500_retries_with_limit(self):
        client = self.make_client(
            [FakeResponse(500), FakeResponse(500), FakeResponse(500)]
        )
        with self.assertRaisesRegex(GoogleCalendarApiError, "tentativas"):
            client.list_events(START, END, TZ.key)
        self.assertEqual(len(self.session.calls), 3)

    def test_timeout_retries_with_limit(self):
        client = self.make_client(
            [
                requests.exceptions.Timeout(),
                requests.exceptions.Timeout(),
                requests.exceptions.Timeout(),
            ]
        )
        with self.assertRaisesRegex(GoogleCalendarApiError, "timeout"):
            client.list_events(START, END, TZ.key)
        self.assertEqual(len(self.session.calls), 3)

    def test_tls_error_is_not_retried(self):
        client = self.make_client([requests.exceptions.SSLError()])
        with self.assertRaisesRegex(GoogleCalendarApiError, "TLS"):
            client.list_events(START, END, TZ.key)
        self.assertEqual(len(self.session.calls), 1)

    def test_invalid_json(self):
        client = self.make_client(
            [FakeResponse(json_error=ValueError("private body"))]
        )
        with self.assertRaisesRegex(GoogleCalendarApiError, "JSON inválido"):
            client.list_events(START, END, TZ.key)

    def test_response_without_items(self):
        client = self.make_client([FakeResponse(document={"timeZone": TZ.key})])
        with self.assertRaisesRegex(GoogleCalendarApiError, "lista de eventos"):
            client.list_events(START, END, TZ.key)

    def test_malformed_event_entry(self):
        client = self.make_client([FakeResponse(document={"items": ["invalid"]})])
        with self.assertRaisesRegex(GoogleCalendarApiError, "malformado"):
            client.list_events(START, END, TZ.key)


if __name__ == "__main__":
    unittest.main()
