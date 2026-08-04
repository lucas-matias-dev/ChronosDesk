import json
import tempfile
import unittest
from pathlib import Path

from google_calendar.config import load_google_calendar_config
from google_calendar.errors import GoogleCalendarConfigError


def desktop_document() -> dict:
    return {
        "installed": {
            "client_id": "fake-client.apps.example",
            "client_secret": "fake-secret-for-tests",
            "auth_uri": "https://accounts.example/authorize",
            "token_uri": "https://accounts.example/token",
            "redirect_uris": ["http://127.0.0.1"],
        }
    }


class GoogleCalendarConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.env_path = self.directory / ".env"
        self.client_path = self.directory / "desktop.json"

    def write_env(self, client_path: str | None = None, timezone="America/Sao_Paulo"):
        lines = []
        if client_path is not None:
            lines.append(f"GOOGLE_OAUTH_CLIENT_FILE={client_path}")
        if timezone is not None:
            lines.append(f"GOOGLE_CALENDAR_TIMEZONE={timezone}")
        self.env_path.write_text("\n".join(lines), encoding="utf-8")

    def write_client(self, document=None):
        self.client_path.write_text(
            json.dumps(document or desktop_document()), encoding="utf-8"
        )

    def test_missing_env_file(self):
        with self.assertRaisesRegex(GoogleCalendarConfigError, "não encontrado"):
            load_google_calendar_config(self.env_path, {})

    def test_missing_client_variable(self):
        self.write_env()
        with self.assertRaisesRegex(
            GoogleCalendarConfigError, "GOOGLE_OAUTH_CLIENT_FILE"
        ):
            load_google_calendar_config(self.env_path, {})

    def test_nonexistent_client_file(self):
        self.write_env("missing.json")
        with self.assertRaisesRegex(GoogleCalendarConfigError, "não encontrado"):
            load_google_calendar_config(self.env_path, {})

    def test_client_path_cannot_be_directory(self):
        self.write_env(".")
        with self.assertRaisesRegex(GoogleCalendarConfigError, "não aponta"):
            load_google_calendar_config(self.env_path, {})

    def test_invalid_json(self):
        self.client_path.write_text("{invalid", encoding="utf-8")
        self.write_env(self.client_path.name)
        with self.assertRaisesRegex(GoogleCalendarConfigError, "JSON OAuth"):
            load_google_calendar_config(self.env_path, {})

    def test_valid_desktop_structure_and_relative_path(self):
        self.write_client()
        self.write_env(self.client_path.name)
        config = load_google_calendar_config(self.env_path, {})
        self.assertEqual(config.client_file, self.client_path.resolve())
        self.assertEqual(config.timezone_name, "America/Sao_Paulo")
        self.assertEqual(
            config.google_client_id, "fake-client.apps.example"
        )
        self.assertNotIn("fake-client.apps.example", repr(config))

    def test_web_client_type_is_rejected(self):
        self.write_client({"web": desktop_document()["installed"]})
        self.write_env(self.client_path.name)
        with self.assertRaisesRegex(GoogleCalendarConfigError, "cliente Desktop"):
            load_google_calendar_config(self.env_path, {})

    def test_missing_fields_are_named_without_values(self):
        self.write_client({"installed": {"client_id": "private-value"}})
        self.write_env(self.client_path.name)
        with self.assertRaises(GoogleCalendarConfigError) as raised:
            load_google_calendar_config(self.env_path, {})
        message = str(raised.exception)
        self.assertIn("installed.client_secret", message)
        self.assertNotIn("private-value", message)

    def test_invalid_field_types_are_named_without_values(self):
        document = desktop_document()
        document["installed"]["client_id"] = ["private-value"]
        self.write_client(document)
        self.write_env(self.client_path.name)
        with self.assertRaises(GoogleCalendarConfigError) as raised:
            load_google_calendar_config(self.env_path, {})
        message = str(raised.exception)
        self.assertIn("installed.client_id", message)
        self.assertNotIn("private-value", message)

    def test_valid_timezone(self):
        self.write_client()
        self.write_env(self.client_path.name, "UTC")
        config = load_google_calendar_config(self.env_path, {})
        self.assertEqual(config.timezone.key, "UTC")

    def test_invalid_timezone(self):
        self.write_client()
        self.write_env(self.client_path.name, "Invalid/Timezone")
        with self.assertRaisesRegex(GoogleCalendarConfigError, "Timezone"):
            load_google_calendar_config(self.env_path, {})

    def test_default_timezone_when_omitted(self):
        self.write_client()
        self.write_env(self.client_path.name, None)
        config = load_google_calendar_config(self.env_path, {})
        self.assertEqual(config.timezone_name, "America/Sao_Paulo")


if __name__ == "__main__":
    unittest.main()
