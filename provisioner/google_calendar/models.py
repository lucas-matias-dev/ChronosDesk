"""Immutable domain models for a calendar day."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool


@dataclass(frozen=True)
class CalendarDay:
    date: date
    events: tuple[CalendarEvent, ...]
    current_event: CalendarEvent | None
    next_event: CalendarEvent | None

    @property
    def total(self) -> int:
        return len(self.events)
