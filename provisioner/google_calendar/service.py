"""Daily Calendar use case independent from terminal and HTTP details."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .client import GoogleCalendarClient
from .errors import GoogleCalendarError
from .models import CalendarDay, CalendarEvent
from .parser import CalendarEventParser


def day_bounds(now: datetime, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    if now.tzinfo is None:
        raise GoogleCalendarError("O relógio usado pelo calendário não possui timezone.")
    local_now = now.astimezone(timezone)
    start = datetime.combine(local_now.date(), time.min, timezone)
    return start, start + timedelta(days=1)


class GoogleCalendarDayService:
    def __init__(
        self,
        client: GoogleCalendarClient,
        parser: CalendarEventParser,
        timezone: ZoneInfo,
        timezone_name: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._parser = parser
        self._timezone = timezone
        self._timezone_name = timezone_name
        self._clock = clock or (lambda: datetime.now(timezone))

    def get_today(self) -> CalendarDay:
        now = self._clock()
        start, end = day_bounds(now, self._timezone)
        parsed_events = self._parser.parse_many(
            self._client.list_events(start, end, self._timezone_name)
        )
        events = tuple(
            sorted(
                (
                    event
                    for event in parsed_events
                    if self._overlaps_day(event, start, end)
                ),
                key=lambda event: (event.start, event.end, event.title),
            )
        )
        local_now = now.astimezone(self._timezone)
        current = next(
            (
                event
                for event in events
                if not event.all_day and event.start <= local_now < event.end
            ),
            None,
        )
        upcoming = next(
            (
                event
                for event in events
                if not event.all_day and event.start > local_now
            ),
            None,
        )
        return CalendarDay(
            date=start.date(),
            events=events,
            current_event=current,
            next_event=upcoming,
        )

    @staticmethod
    def _overlaps_day(
        event: CalendarEvent, start: datetime, end: datetime
    ) -> bool:
        if event.end == event.start:
            return start <= event.start < end
        return event.start < end and event.end > start
