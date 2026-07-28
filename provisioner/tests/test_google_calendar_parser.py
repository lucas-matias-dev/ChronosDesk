import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from google_calendar.errors import CalendarEventParseError
from google_calendar.parser import CalendarEventParser


TZ = ZoneInfo("America/Sao_Paulo")


def timed_event(**overrides):
    event = {
        "id": "event-1",
        "summary": "Reunião técnica",
        "status": "confirmed",
        "start": {"dateTime": "2026-07-27T15:00:00-03:00"},
        "end": {"dateTime": "2026-07-27T16:00:00-03:00"},
    }
    event.update(overrides)
    return event


class CalendarEventParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = CalendarEventParser(TZ)

    def test_timed_event(self):
        event = self.parser.parse(timed_event())
        self.assertEqual(event.start.hour, 15)
        self.assertEqual(event.end.hour, 16)
        self.assertFalse(event.all_day)
        self.assertIsNotNone(event.start.tzinfo)

    def test_all_day_event_uses_exclusive_end_date(self):
        event = self.parser.parse(
            timed_event(
                start={"date": "2026-07-27"},
                end={"date": "2026-07-29"},
            )
        )
        self.assertTrue(event.all_day)
        self.assertEqual((event.end - event.start).days, 2)

    def test_cancelled_event_is_discarded(self):
        self.assertIsNone(self.parser.parse(timed_event(status="cancelled")))

    def test_missing_title_uses_default(self):
        event = self.parser.parse(timed_event(summary=""))
        self.assertEqual(event.title, "Sem título")

    def test_missing_timed_end_uses_start(self):
        event = self.parser.parse(timed_event(end=None))
        self.assertEqual(event.end, event.start)

    def test_explicit_timezone_is_used_for_naive_datetime(self):
        event = self.parser.parse(
            timed_event(
                start={
                    "dateTime": "2026-07-27T18:00:00",
                    "timeZone": "Europe/London",
                },
                end={
                    "dateTime": "2026-07-27T19:00:00",
                    "timeZone": "Europe/London",
                },
            )
        )
        self.assertEqual(event.start.hour, 14)

    def test_missing_timezone_uses_configured_timezone(self):
        event = self.parser.parse(
            timed_event(
                start={"dateTime": "2026-07-27T10:00:00"},
                end={"dateTime": "2026-07-27T11:00:00"},
            )
        )
        self.assertEqual(event.start.utcoffset().total_seconds(), -10800)

    def test_multiple_events_and_unicode_are_preserved(self):
        events = self.parser.parse_many(
            [timed_event(summary="Álgebra"), timed_event(summary="Programação")]
        )
        self.assertEqual([event.title for event in events], ["Álgebra", "Programação"])

    def test_empty_response(self):
        self.assertEqual(self.parser.parse_many([]), [])

    def test_incomplete_event_is_rejected(self):
        with self.assertRaises(CalendarEventParseError):
            self.parser.parse({"summary": "Inválido"})

    def test_end_before_start_is_rejected(self):
        with self.assertRaisesRegex(CalendarEventParseError, "antes"):
            self.parser.parse(
                timed_event(
                    end={"dateTime": "2026-07-27T14:00:00-03:00"}
                )
            )

    def test_utc_suffix_is_converted_to_local_timezone(self):
        event = self.parser.parse(
            timed_event(
                start={"dateTime": "2026-07-27T18:00:00Z"},
                end={"dateTime": "2026-07-27T19:00:00Z"},
            )
        )
        self.assertEqual(
            event.start,
            datetime(2026, 7, 27, 15, 0, tzinfo=TZ),
        )


if __name__ == "__main__":
    unittest.main()
