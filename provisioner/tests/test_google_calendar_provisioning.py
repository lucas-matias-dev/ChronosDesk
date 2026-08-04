import json
import unittest
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from google_calendar.auth import GoogleAuthorization, REQUIRED_SCOPE
from google_calendar.config import GoogleCalendarConfig
from google_calendar.errors import (
    GoogleCalendarProvisioningError,
    GoogleOAuthError,
)
from google_calendar.provisioning import (
    GOOGLE_CREDENTIAL_FORMAT_VERSION,
    GoogleCalendarEraseUseCase,
    GoogleCalendarProvisioningMaterial,
    GoogleCalendarProvisioningUseCase,
)
from serial_transport import (
    GOOGLE_CALENDAR_PROVIDER,
    PROTOCOL_VERSION,
    SPOTIFY_PROVIDER,
    SerialProvisioningError,
    SerialTransport,
    build_message,
)

FAKE_CLIENT_ID = "fake-google-client-id.example.invalid"
FAKE_REFRESH_TOKEN = "fake-refresh-token-for-tests-only"
FAKE_ACCESS_TOKEN = "fake-access-token-for-tests-only"
FAKE_CLIENT_SECRET = "fake-client-secret-for-tests-only"
VALID_TIMESTAMP = "2026-08-03T12:34:56Z"
TZ = ZoneInfo("America/Sao_Paulo")


def make_config(client_id=FAKE_CLIENT_ID):
    return GoogleCalendarConfig(
        Path("fake-desktop.json"),
        TZ.key,
        TZ,
        client_id,
    )


class FakeCredentials:
    def __init__(self, *, refresh_token=FAKE_REFRESH_TOKEN, scopes=True):
        self.refresh_token = refresh_token
        self.token = FAKE_ACCESS_TOKEN
        self.client_secret = FAKE_CLIENT_SECRET
        self.scopes_valid = scopes

    def has_scopes(self, scopes):
        return self.scopes_valid and scopes == [REQUIRED_SCOPE]


class FakeOAuth:
    def __init__(self, credentials=None, *, refresh_received=True, error=None, events=None):
        self.credentials = credentials or FakeCredentials()
        self.refresh_received = refresh_received
        self.error = error
        self.events = events if events is not None else []

    def authorize(self, _config, _timeout_seconds):
        self.events.append("oauth")
        if self.error is not None:
            raise self.error
        return GoogleAuthorization(self.credentials, self.refresh_received)


class FakeProvisioningTransport:
    def __init__(self, events=None):
        self.events = events if events is not None else []
        self.provisioned = None
        self.erased = False

    def provision_google(self, **fields):
        self.events.append("serial")
        self.provisioned = fields

    def erase_google(self):
        self.events.append("erase")
        self.erased = True


class RecordingTransportFactory:
    def __init__(self, transport, events=None):
        self.transport = transport
        self.events = events if events is not None else []
        self.ports = []

    def __call__(self, port):
        self.events.append("transport_factory")
        self.ports.append(port)
        return self.transport


class ProvisioningMaterialTests(unittest.TestCase):
    def create(self, **changes):
        values = {
            "google_client_id": FAKE_CLIENT_ID,
            "refresh_token": FAKE_REFRESH_TOKEN,
            "authorized_at": VALID_TIMESTAMP,
            "scopes": REQUIRED_SCOPE,
        }
        values.update(changes)
        return GoogleCalendarProvisioningMaterial.create(**values)

    def test_valid_material_and_timestamp(self):
        material = self.create()
        self.assertEqual(
            material.credential_format_version,
            GOOGLE_CREDENTIAL_FORMAT_VERSION,
        )
        self.assertEqual(material.authorized_at, VALID_TIMESTAMP)

    def test_missing_client_id_is_rejected(self):
        with self.assertRaisesRegex(
            GoogleCalendarProvisioningError, "Client ID"
        ):
            self.create(google_client_id="")

    def test_missing_refresh_token_is_rejected(self):
        with self.assertRaisesRegex(
            GoogleCalendarProvisioningError, "refresh token"
        ):
            self.create(refresh_token="")

    def test_missing_or_incorrect_scope_is_rejected(self):
        for scopes in ("", "https://example.invalid/broader-scope"):
            with self.subTest(scopes=scopes):
                with self.assertRaisesRegex(
                    GoogleCalendarProvisioningError, "escopo"
                ):
                    self.create(scopes=scopes)

    def test_invalid_timestamp_is_rejected(self):
        for timestamp in (
            "2026-08-03T12:34:56+00:00",
            "2026-02-30T12:34:56Z",
            "",
        ):
            with self.subTest(timestamp=timestamp):
                with self.assertRaisesRegex(
                    GoogleCalendarProvisioningError, "timestamp"
                ):
                    self.create(authorized_at=timestamp)

    def test_incompatible_credential_format_is_rejected(self):
        with self.assertRaisesRegex(
            GoogleCalendarProvisioningError, "formato"
        ):
            self.create(credential_format_version=2)

    def test_repr_and_exceptions_do_not_contain_sensitive_values(self):
        material = self.create()
        representation = repr(material)
        self.assertNotIn(FAKE_CLIENT_ID, representation)
        self.assertNotIn(FAKE_REFRESH_TOKEN, representation)
        marker = "fake-private-marker-for-tests-only"
        with self.assertRaises(GoogleCalendarProvisioningError) as raised:
            self.create(refresh_token=f"{marker} ")
        self.assertNotIn(marker, str(raised.exception))

    def test_clear_removes_all_material_references(self):
        material = self.create()
        material.clear()
        self.assertEqual(material.google_client_id, "")
        self.assertEqual(material.refresh_token, "")
        self.assertEqual(material.authorized_at, "")
        self.assertEqual(material.scopes, "")


class GoogleProvisioningUseCaseTests(unittest.TestCase):
    def execute(self, oauth=None, config=None):
        events = []
        credentials = FakeCredentials()
        oauth = oauth or FakeOAuth(credentials, events=events)
        transport = FakeProvisioningTransport(events)
        factory = RecordingTransportFactory(transport, events)
        output = []
        use_case = GoogleCalendarProvisioningUseCase(
            oauth,
            factory,
            clock=lambda: datetime(2026, 8, 3, 12, 34, 56, tzinfo=timezone.utc),
            output=output.append,
        )
        use_case.execute(config or make_config(), "COM-FAKE", 15)
        return events, credentials, transport, factory, output

    def test_oauth_and_validation_happen_before_serial_factory(self):
        events, _, _, factory, _ = self.execute()
        self.assertEqual(events, ["oauth", "transport_factory", "serial"])
        self.assertEqual(factory.ports, ["COM-FAKE"])

    def test_payload_contains_only_persistent_google_material(self):
        _, credentials, transport, _, output = self.execute()
        payload = transport.provisioned
        self.assertEqual(payload["google_client_id"], FAKE_CLIENT_ID)
        self.assertEqual(payload["refresh_token"], FAKE_REFRESH_TOKEN)
        self.assertEqual(payload["authorized_at"], VALID_TIMESTAMP)
        self.assertEqual(payload["scopes"], REQUIRED_SCOPE)
        self.assertNotIn("token", payload)
        self.assertNotIn("access_token", payload)
        self.assertNotIn("client_secret", payload)
        self.assertIsNone(credentials.token)
        self.assertIsNone(credentials.refresh_token)
        rendered_output = "\n".join(output)
        self.assertNotIn(FAKE_CLIENT_ID, rendered_output)
        self.assertNotIn(FAKE_REFRESH_TOKEN, rendered_output)
        self.assertNotIn(FAKE_ACCESS_TOKEN, rendered_output)

    def test_oauth_failure_never_creates_transport(self):
        events = []
        oauth = FakeOAuth(
            error=GoogleOAuthError("falha OAuth sanitizada"),
            events=events,
        )
        factory = RecordingTransportFactory(FakeProvisioningTransport(), events)
        use_case = GoogleCalendarProvisioningUseCase(oauth, factory, output=lambda _line: None)
        with self.assertRaises(GoogleOAuthError):
            use_case.execute(make_config(), "COM-FAKE", 15)
        self.assertEqual(events, ["oauth"])
        self.assertEqual(factory.ports, [])

    def test_missing_refresh_token_never_creates_transport(self):
        events = []
        credentials = FakeCredentials(refresh_token=None)
        oauth = FakeOAuth(
            credentials,
            refresh_received=False,
            events=events,
        )
        factory = RecordingTransportFactory(FakeProvisioningTransport(), events)
        use_case = GoogleCalendarProvisioningUseCase(oauth, factory, output=lambda _line: None)
        with self.assertRaisesRegex(GoogleOAuthError, "refresh token"):
            use_case.execute(make_config(), "COM-FAKE", 15)
        self.assertEqual(events, ["oauth"])

    def test_missing_scope_never_creates_transport(self):
        events = []
        oauth = FakeOAuth(FakeCredentials(scopes=False), events=events)
        factory = RecordingTransportFactory(FakeProvisioningTransport(), events)
        use_case = GoogleCalendarProvisioningUseCase(oauth, factory, output=lambda _line: None)
        with self.assertRaisesRegex(GoogleOAuthError, "escopo"):
            use_case.execute(make_config(), "COM-FAKE", 15)
        self.assertEqual(events, ["oauth"])

    def test_missing_client_id_never_creates_transport(self):
        events = []
        oauth = FakeOAuth(events=events)
        factory = RecordingTransportFactory(FakeProvisioningTransport(), events)
        use_case = GoogleCalendarProvisioningUseCase(oauth, factory, output=lambda _line: None)
        with self.assertRaisesRegex(
            GoogleCalendarProvisioningError, "Client ID"
        ):
            use_case.execute(make_config(""), "COM-FAKE", 15)
        self.assertEqual(events, ["oauth"])

    def test_naive_clock_never_creates_transport(self):
        events = []
        factory = RecordingTransportFactory(FakeProvisioningTransport(), events)
        use_case = GoogleCalendarProvisioningUseCase(
            FakeOAuth(events=events),
            factory,
            clock=lambda: datetime(2026, 8, 3, 12, 34, 56),
            output=lambda _line: None,
        )
        with self.assertRaisesRegex(
            GoogleCalendarProvisioningError, "timezone"
        ):
            use_case.execute(make_config(), "COM-FAKE", 15)
        self.assertEqual(events, ["oauth"])

    def test_erase_has_no_oauth_and_selects_google_transport(self):
        events = []
        transport = FakeProvisioningTransport(events)
        factory = RecordingTransportFactory(transport, events)
        output = []
        GoogleCalendarEraseUseCase(factory, output=output.append).execute(
            "COM-FAKE"
        )
        self.assertEqual(events, ["transport_factory", "erase"])
        self.assertTrue(transport.erased)
        self.assertEqual(factory.ports, ["COM-FAKE"])
        self.assertNotIn(FAKE_REFRESH_TOKEN, "\n".join(output))


class FakeConnection:
    def __init__(self, responses):
        self.responses = deque(responses)
        self.writes = []
        self.reset = False

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        return False

    def reset_input_buffer(self):
        self.reset = True

    def write(self, message):
        self.writes.append(message)
        return len(message)

    def read_until(self, *, expected, size):
        self.last_read_limit = (expected, size)
        return self.responses.popleft() if self.responses else b""


class FakeSerialFactory:
    def __init__(self, connections):
        self.connections = deque(connections)
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.connections.popleft()


class TickingClock:
    def __init__(self):
        self.value = -1

    def __call__(self):
        self.value += 1
        return self.value


def response(message_type, *, provider=GOOGLE_CALENDAR_PROVIDER, protocol=PROTOCOL_VERSION, reason=None):
    document = {
        "protocol": protocol,
        "type": message_type,
        "provider": provider,
    }
    if reason is not None:
        document["reason"] = reason
    return (json.dumps(document, separators=(",", ":")) + "\n").encode()


class SerialTransportTests(unittest.TestCase):
    def transport(self, connection, **changes):
        factory = FakeSerialFactory([connection])
        values = {
            "port": "COM-FAKE",
            "maximum_attempts": 1,
            "serial_factory": factory,
            "sleeper": lambda _seconds: None,
            "monotonic": TickingClock(),
        }
        values.update(changes)
        return SerialTransport(**values), factory

    def provision_google(self, transport):
        transport.provision_google(
            google_client_id=FAKE_CLIENT_ID,
            refresh_token=FAKE_REFRESH_TOKEN,
            authorized_at=VALID_TIMESTAMP,
            scopes=REQUIRED_SCOPE,
            credential_format_version=GOOGLE_CREDENTIAL_FORMAT_VERSION,
        )

    def test_google_handshake_and_storage_are_versioned_and_explicit(self):
        connection = FakeConnection(
            [response("provision_ready"), response("storage_complete")]
        )
        transport, factory = self.transport(connection)
        self.provision_google(transport)
        self.assertTrue(connection.reset)
        self.assertEqual(len(factory.calls), 1)
        begin, store = [json.loads(message) for message in connection.writes]
        self.assertEqual(begin["provider"], GOOGLE_CALENDAR_PROVIDER)
        self.assertEqual(begin["protocol"], PROTOCOL_VERSION)
        self.assertEqual(store["provider"], GOOGLE_CALENDAR_PROVIDER)
        self.assertEqual(store["credential_format_version"], 1)
        self.assertNotIn("access_token", store)
        self.assertNotIn("client_secret", store)

    def test_outgoing_message_size_and_field_count_are_bounded(self):
        marker = "fake-oversized-sensitive-value-for-tests-only"
        with self.assertRaises(SerialProvisioningError) as oversized:
            build_message(
                "store_credentials",
                provider=GOOGLE_CALENDAR_PROVIDER,
                refresh_token=marker * 100,
            )
        self.assertNotIn(marker, str(oversized.exception))

        with self.assertRaisesRegex(SerialProvisioningError, "campos"):
            build_message(
                "store_credentials",
                provider=GOOGLE_CALENDAR_PROVIDER,
                **{f"field_{index}": index for index in range(6)},
            )

    def test_outgoing_unknown_provider_and_reserved_fields_are_rejected(self):
        with self.assertRaisesRegex(SerialProvisioningError, "desconhecido"):
            build_message("provision_begin", provider="unknown-provider")
        with self.assertRaisesRegex(SerialProvisioningError, "reservado"):
            build_message(
                "provision_begin",
                provider=GOOGLE_CALENDAR_PROVIDER,
                protocol=99,
            )

    def test_spotify_messages_remain_supported_with_explicit_provider(self):
        connection = FakeConnection(
            [
                response("provision_ready", provider=SPOTIFY_PROVIDER),
                response("storage_complete", provider=SPOTIFY_PROVIDER),
            ]
        )
        transport, _ = self.transport(connection)
        transport.provision(
            "fake-spotify-refresh-for-tests-only",
            1770000000,
            "user-read-currently-playing",
        )
        messages = [json.loads(message) for message in connection.writes]
        self.assertTrue(
            all(message["provider"] == SPOTIFY_PROVIDER for message in messages)
        )
        self.assertEqual(messages[1]["credential_format_version"], 1)

    def test_response_for_other_provider_is_rejected(self):
        connection = FakeConnection(
            [response("provision_ready", provider=SPOTIFY_PROVIDER)]
        )
        transport, _ = self.transport(connection)
        with self.assertRaisesRegex(SerialProvisioningError, "outro provedor"):
            self.provision_google(transport)

    def test_unknown_provider_is_rejected(self):
        connection = FakeConnection(
            [response("provision_ready", provider="unknown-provider")]
        )
        transport, _ = self.transport(connection)
        with self.assertRaisesRegex(SerialProvisioningError, "desconhecido"):
            self.provision_google(transport)

    def test_incompatible_version_is_rejected(self):
        connection = FakeConnection(
            [response("incompatible_version", protocol=1)]
        )
        transport, _ = self.transport(connection)
        with self.assertRaisesRegex(SerialProvisioningError, "protocolo"):
            self.provision_google(transport)

    def test_handshake_timeout_is_bounded(self):
        connection = FakeConnection([])
        transport, _ = self.transport(
            connection, handshake_timeout_seconds=1
        )
        with self.assertRaisesRegex(SerialProvisioningError, "Tempo limite"):
            self.provision_google(transport)

    def test_storage_timeout_is_bounded(self):
        connection = FakeConnection([response("provision_ready")])
        transport, _ = self.transport(
            connection,
            handshake_timeout_seconds=10,
            confirmation_timeout_seconds=1,
        )
        with self.assertRaisesRegex(SerialProvisioningError, "Tempo limite"):
            self.provision_google(transport)

    def test_retry_restarts_the_complete_negotiation(self):
        first = FakeConnection([])
        second = FakeConnection(
            [response("provision_ready"), response("storage_complete")]
        )
        factory = FakeSerialFactory([first, second])
        transport = SerialTransport(
            "COM-FAKE",
            handshake_timeout_seconds=2,
            confirmation_timeout_seconds=2,
            maximum_attempts=2,
            serial_factory=factory,
            sleeper=lambda _seconds: None,
            monotonic=TickingClock(),
        )
        self.provision_google(transport)
        self.assertEqual(len(factory.calls), 2)
        self.assertEqual(len(first.writes), 1)
        self.assertEqual(len(second.writes), 2)

    def test_firmware_validation_and_storage_errors_are_sanitized(self):
        for message_type, reason in (
            ("validation_failed", "invalid_credentials"),
            ("storage_failed", "nvs_write_failed"),
        ):
            with self.subTest(message_type=message_type):
                connection = FakeConnection(
                    [response("provision_ready"), response(message_type, reason=reason)]
                )
                transport, _ = self.transport(connection)
                with self.assertRaises(SerialProvisioningError) as raised:
                    self.provision_google(transport)
                self.assertNotIn(FAKE_REFRESH_TOKEN, str(raised.exception))
                self.assertNotIn(FAKE_CLIENT_ID, str(raised.exception))

    def test_unknown_firmware_reason_is_not_echoed(self):
        marker = "fake-sensitive-reason-for-tests-only"
        connection = FakeConnection(
            [
                response("provision_ready"),
                response("validation_failed", reason=marker),
            ]
        )
        transport, _ = self.transport(connection)
        with self.assertRaises(SerialProvisioningError) as raised:
            self.provision_google(transport)
        self.assertNotIn(marker, str(raised.exception))

    def test_invalid_json_and_unexpected_message_are_rejected(self):
        for invalid_response in (
            b"{invalid-json\n",
            response("credentials_erased"),
        ):
            with self.subTest(invalid_response=invalid_response):
                connection = FakeConnection([invalid_response])
                transport, _ = self.transport(connection)
                with self.assertRaises(SerialProvisioningError):
                    self.provision_google(transport)

    def test_google_erase_negotiates_without_sensitive_payload(self):
        connection = FakeConnection(
            [response("provision_ready"), response("credentials_erased")]
        )
        transport, _ = self.transport(connection)
        transport.erase_google()
        messages = [json.loads(message) for message in connection.writes]
        self.assertEqual(
            [message["type"] for message in messages],
            ["provision_begin", "erase_credentials"],
        )
        self.assertTrue(
            all(
                message["provider"] == GOOGLE_CALENDAR_PROVIDER
                for message in messages
            )
        )
        rendered = json.dumps(messages)
        self.assertNotIn("refresh_token", rendered)
        self.assertNotIn("google_client_id", rendered)

    def test_google_erase_timeout_is_reported(self):
        connection = FakeConnection([])
        transport, _ = self.transport(
            connection, handshake_timeout_seconds=1
        )
        with self.assertRaisesRegex(SerialProvisioningError, "Tempo limite"):
            transport.erase_google()


if __name__ == "__main__":
    unittest.main()
