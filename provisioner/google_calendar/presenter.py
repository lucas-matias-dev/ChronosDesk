"""Sanitized console output for the Google Calendar validation."""

from __future__ import annotations

from collections.abc import Callable

from .models import CalendarDay, CalendarEvent


class CalendarConsolePresenter:
    def __init__(self, output: Callable[[str], None] = print) -> None:
        self._output = output

    def authorization_succeeded(self, refresh_token_received: bool) -> None:
        self._output("[GCAL] Autorização concluída com sucesso.")
        self._output("[GCAL] Escopo necessário concedido.")
        answer = "sim" if refresh_token_received else "não"
        self._output(f"[GCAL] Refresh token recebido: {answer}.")

    def show_day(self, calendar_day: CalendarDay) -> None:
        if not calendar_day.events:
            self._output("[GCAL] Sem compromissos para hoje.")
            return

        self._output(
            f"[GCAL] Compromissos encontrados hoje: {calendar_day.total}"
        )
        self._output("")
        for event in calendar_day.events:
            self._output(self._format_event(event, calendar_day))

    @staticmethod
    def _format_event(event: CalendarEvent, calendar_day: CalendarDay) -> str:
        if event.all_day:
            return f"Dia inteiro — {event.title}"
        if event == calendar_day.current_event:
            return f"Agora — {event.title} — até {event.end:%H:%M}"
        return f"{event.start:%H:%M} — {event.title}"
