import contextlib
import io
import unittest
from unittest.mock import patch

import main
from google_calendar.errors import GoogleCalendarError


class GoogleCalendarCliTests(unittest.TestCase):
    def test_default_command_preserves_spotify_flow(self):
        with (
            patch("main.load_local_environment") as load_env,
            patch("main.choose_serial_port", return_value="COM-FAKE") as choose,
            patch("main.run_provisioning") as provision,
        ):
            result = main.main([])
        self.assertEqual(result, 0)
        load_env.assert_called_once()
        choose.assert_called_once_with(None)
        provision.assert_called_once_with("COM-FAKE", 8888, 180)

    def test_google_command_selects_only_google_flow(self):
        with (
            patch("main.run_google_calendar_test") as google,
            patch("main.choose_serial_port") as choose,
            patch("main.run_provisioning") as spotify,
        ):
            result = main.main(["google-calendar-test"])
        self.assertEqual(result, 0)
        google.assert_called_once_with(180)
        choose.assert_not_called()
        spotify.assert_not_called()

    def test_google_command_accepts_timeout(self):
        with patch("main.run_google_calendar_test") as google:
            result = main.main(["google-calendar-test", "--timeout", "15"])
        self.assertEqual(result, 0)
        google.assert_called_once_with(15)

    def test_help_works_without_running_any_flow(self):
        output = io.StringIO()
        with (
            patch("main.run_google_calendar_test") as google,
            patch("main.choose_serial_port") as choose,
            contextlib.redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            main.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("google-calendar-test", output.getvalue())
        google.assert_not_called()
        choose.assert_not_called()

    def test_google_error_is_sanitized_by_exception_contract(self):
        output = io.StringIO()
        with (
            patch(
                "main.run_google_calendar_test",
                side_effect=GoogleCalendarError("configuração inválida"),
            ),
            contextlib.redirect_stdout(output),
        ):
            result = main.main(["google-calendar-test"])
        self.assertEqual(result, 1)
        self.assertIn("[GCAL] Erro: configuração inválida", output.getvalue())

    def test_ctrl_c_is_handled(self):
        output = io.StringIO()
        with (
            patch("main.run_google_calendar_test", side_effect=KeyboardInterrupt),
            contextlib.redirect_stdout(output),
        ):
            result = main.main(["google-calendar-test"])
        self.assertEqual(result, 130)
        self.assertIn("cancelada", output.getvalue())


if __name__ == "__main__":
    unittest.main()
