import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from google_calendar.models import CalendarDay, CalendarEvent
from google_calendar.presenter import CalendarConsolePresenter


TZ = ZoneInfo("America/Sao_Paulo")


class CalendarPresenterTests(unittest.TestCase):
    def setUp(self):
        self.lines = []
        self.presenter = CalendarConsolePresenter(self.lines.append)

    def event(self, **changes):
        values = {
            "id": "private-event-id",
            "title": "Aula de Redes",
            "start": datetime(2026, 7, 27, 15, tzinfo=TZ),
            "end": datetime(2026, 7, 27, 16, tzinfo=TZ),
            "all_day": False,
        }
        values.update(changes)
        return CalendarEvent(**values)

    def test_authorization_output_only_confirms_refresh_presence(self):
        self.presenter.authorization_succeeded(True)
        output = "\n".join(self.lines)
        self.assertIn("Refresh token recebido: sim", output)
        self.assertEqual(len(self.lines), 3)

    def test_empty_day(self):
        self.presenter.show_day(CalendarDay(date(2026, 7, 27), (), None, None))
        self.assertEqual(self.lines, ["[GCAL] Sem compromissos para hoje."])

    def test_timed_current_and_all_day_events(self):
        current = self.event()
        all_day = self.event(
            id="all-day",
            title="Entrega de trabalho",
            start=datetime(2026, 7, 27, tzinfo=TZ),
            end=datetime(2026, 7, 28, tzinfo=TZ),
            all_day=True,
        )
        day = CalendarDay(
            date(2026, 7, 27), (all_day, current), current, None
        )
        self.presenter.show_day(day)
        output = "\n".join(self.lines)
        self.assertIn("Dia inteiro — Entrega de trabalho", output)
        self.assertIn("Agora — Aula de Redes — até 16:00", output)
        self.assertNotIn("private-event-id", output)


if __name__ == "__main__":
    unittest.main()
