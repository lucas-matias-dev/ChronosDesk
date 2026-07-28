"""Convert the restricted Calendar API payload into domain events."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import CalendarEventParseError
from .models import CalendarEvent


class CalendarEventParser:
    def __init__(self, default_timezone: ZoneInfo) -> None:
        self._default_timezone = default_timezone

    def parse_many(self, raw_events: list[dict[str, Any]]) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for raw_event in raw_events:
            parsed = self.parse(raw_event)
            if parsed is not None:
                events.append(parsed)
        return events

    def parse(self, raw_event: dict[str, Any]) -> CalendarEvent | None:
        if raw_event.get("status") == "cancelled":
            return None

        start_data = raw_event.get("start")
        end_data = raw_event.get("end")
        if not isinstance(start_data, dict):
            raise CalendarEventParseError(
                "Evento retornado pelo Google Agenda sem início válido."
            )
        if end_data is not None and not isinstance(end_data, dict):
            raise CalendarEventParseError(
                "Evento retornado pelo Google Agenda com fim inválido."
            )

        all_day = "date" in start_data
        try:
            if all_day:
                start = self._parse_date(start_data["date"])
                end = (
                    self._parse_date(end_data["date"])
                    if end_data and end_data.get("date")
                    else start + timedelta(days=1)
                )
            elif "dateTime" in start_data:
                start = self._parse_datetime(start_data)
                end = (
                    self._parse_datetime(end_data)
                    if end_data and end_data.get("dateTime")
                    else start
                )
            else:
                raise CalendarEventParseError(
                    "Evento retornado pelo Google Agenda sem data válida."
                )
        except (TypeError, ValueError, KeyError) as error:
            raise CalendarEventParseError(
                "Evento retornado pelo Google Agenda com data ou horário inválido."
            ) from error

        if end < start:
            raise CalendarEventParseError(
                "Evento retornado pelo Google Agenda termina antes de começar."
            )

        event_id = raw_event.get("id")
        title = raw_event.get("summary")
        return CalendarEvent(
            id=event_id if isinstance(event_id, str) else "",
            title=title.strip() if isinstance(title, str) and title.strip() else "Sem título",
            start=start,
            end=end,
            all_day=all_day,
        )

    def _parse_date(self, value: Any) -> datetime:
        parsed = date.fromisoformat(value)
        return datetime.combine(parsed, time.min, self._default_timezone)

    def _parse_datetime(self, data: dict[str, Any]) -> datetime:
        value = data["dateTime"]
        if not isinstance(value, str):
            raise ValueError("dateTime precisa ser texto")
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self._event_timezone(data))
        return parsed.astimezone(self._default_timezone)

    def _event_timezone(self, data: dict[str, Any]) -> ZoneInfo:
        timezone_name = data.get("timeZone")
        if not timezone_name:
            return self._default_timezone
        if not isinstance(timezone_name, str):
            raise ValueError("timeZone precisa ser texto")
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timeZone desconhecido") from error
