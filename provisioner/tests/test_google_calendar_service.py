import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from google_calendar.errors import GoogleCalendarError
from google_calendar.parser import CalendarEventParser
from google_calendar.service import GoogleCalendarDayService, day_bounds


TZ = ZoneInfo("America/Sao_Paulo")


def raw_event(identifier, start, end, title=None):
    return {
        "id": identifier,
        "summary": title or identifier,
        "status": "confirmed",
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }


class StubClient:
    def __init__(self, events):
        self.events = events
        self.arguments = None

    def list_events(self, start, end, timezone_name):
        self.arguments = (start, end, timezone_name)
        return self.events


class GoogleCalendarServiceTests(unittest.TestCase):
    def service(self, events, now):
        client = StubClient(events)
        service = GoogleCalendarDayService(
            client,
            CalendarEventParser(TZ),
            TZ,
            TZ.key,
            clock=lambda: now,
        )
        return service, client

    def test_day_bounds_are_local_midnights(self):
        start, end = day_bounds(
            datetime(2026, 7, 27, 12, 30, tzinfo=TZ), TZ
        )
        self.assertEqual(start, datetime(2026, 7, 27, tzinfo=TZ))
        self.assertEqual(end, datetime(2026, 7, 28, tzinfo=TZ))

    def test_naive_clock_is_rejected(self):
        with self.assertRaisesRegex(GoogleCalendarError, "timezone"):
            day_bounds(datetime(2026, 7, 27), TZ)

    def test_event_exactly_at_midnight_is_included(self):
        service, client = self.service(
            [
                raw_event(
                    "midnight",
                    "2026-07-27T00:00:00-03:00",
                    "2026-07-27T00:30:00-03:00",
                )
            ],
            datetime(2026, 7, 27, 10, tzinfo=TZ),
        )
        day = service.get_today()
        self.assertEqual(day.total, 1)
        self.assertEqual(client.arguments[0].hour, 0)

    def test_event_crossing_midnight_is_included(self):
        service, _ = self.service(
            [
                raw_event(
                    "crossing",
                    "2026-07-26T23:30:00-03:00",
                    "2026-07-27T00:30:00-03:00",
                )
            ],
            datetime(2026, 7, 27, 0, 15, tzinfo=TZ),
        )
        day = service.get_today()
        self.assertEqual(day.total, 1)
        self.assertEqual(day.current_event.id, "crossing")

    def test_current_next_and_finished_events(self):
        service, _ = self.service(
            [
                raw_event(
                    "next",
                    "2026-07-27T12:00:00-03:00",
                    "2026-07-27T13:00:00-03:00",
                ),
                raw_event(
                    "finished",
                    "2026-07-27T08:00:00-03:00",
                    "2026-07-27T09:00:00-03:00",
                ),
                raw_event(
                    "current",
                    "2026-07-27T09:30:00-03:00",
                    "2026-07-27T11:00:00-03:00",
                ),
            ],
            datetime(2026, 7, 27, 10, tzinfo=TZ),
        )
        day = service.get_today()
        self.assertEqual([event.id for event in day.events], ["finished", "current", "next"])
        self.assertEqual(day.current_event.id, "current")
        self.assertEqual(day.next_event.id, "next")

    def test_empty_event_list(self):
        service, _ = self.service([], datetime(2026, 7, 27, 10, tzinfo=TZ))
        day = service.get_today()
        self.assertEqual(day.total, 0)
        self.assertIsNone(day.current_event)
        self.assertIsNone(day.next_event)


if __name__ == "__main__":
    unittest.main()
