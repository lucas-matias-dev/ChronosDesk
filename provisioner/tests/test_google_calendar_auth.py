import unittest
import webbrowser
from pathlib import Path
from zoneinfo import ZoneInfo

from google_auth_oauthlib.flow import WSGITimeoutError
from oauthlib.oauth2 import AccessDeniedError, OAuth2Error
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError

from google_calendar.auth import GoogleOAuthClient, REQUIRED_SCOPE
from google_calendar.config import GoogleCalendarConfig
from google_calendar.errors import GoogleOAuthError


class FakeCredentials:
    def __init__(self, *, scope=True, refresh_token=None):
        self._scope = scope
        self.refresh_token = object() if refresh_token is None else refresh_token

    def has_scopes(self, scopes):
        return self._scope and scopes == [REQUIRED_SCOPE]


class FakeFlow:
    def __init__(self, outcome):
        self.outcome = outcome
        self.run_arguments = None

    def run_local_server(self, **kwargs):
        self.run_arguments = kwargs
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FlowFactory:
    def __init__(self, flow):
        self.flow = flow
        self.arguments = None

    def __call__(self, *args, **kwargs):
        self.arguments = (args, kwargs)
        return self.flow


class FakeBrowser:
    def open(self, _url, **_kwargs):
        return True


class ClosedBrowser:
    def open(self, _url, **_kwargs):
        return False


class GoogleOAuthTests(unittest.TestCase):
    def setUp(self):
        self.config = GoogleCalendarConfig(
            Path("fake-desktop.json"),
            "America/Sao_Paulo",
            ZoneInfo("America/Sao_Paulo"),
        )

    def authorize(self, outcome):
        flow = FakeFlow(outcome)
        factory = FlowFactory(flow)
        result = GoogleOAuthClient(
            factory,
            browser_factory=FakeBrowser,
            browser_registrar=lambda *_args: None,
        ).authorize(self.config, 12)
        return result, flow, factory

    def test_success_uses_pkce_loopback_ephemeral_port_and_offline_consent(self):
        result, flow, factory = self.authorize(FakeCredentials())
        self.assertTrue(result.refresh_token_received)
        self.assertEqual(factory.arguments[1]["scopes"], [REQUIRED_SCOPE])
        self.assertTrue(factory.arguments[1]["autogenerate_code_verifier"])
        self.assertEqual(flow.run_arguments["host"], "127.0.0.1")
        self.assertEqual(flow.run_arguments["bind_addr"], "127.0.0.1")
        self.assertEqual(flow.run_arguments["port"], 0)
        self.assertEqual(flow.run_arguments["timeout_seconds"], 12)
        self.assertEqual(flow.run_arguments["access_type"], "offline")
        self.assertEqual(flow.run_arguments["prompt"], "consent")
        self.assertTrue(flow.run_arguments["browser"].startswith("chronosdesk-google-"))
        self.assertNotIn("{url}", flow.run_arguments["authorization_prompt_message"])

    def test_missing_refresh_token_is_reported_without_its_value(self):
        result, _, _ = self.authorize(FakeCredentials(refresh_token=False))
        self.assertFalse(result.refresh_token_received)

    def test_missing_scope_is_rejected(self):
        with self.assertRaisesRegex(GoogleOAuthError, "escopo necessário"):
            self.authorize(FakeCredentials(scope=False))

    def test_cancellation_is_sanitized(self):
        with self.assertRaisesRegex(GoogleOAuthError, "cancelada"):
            self.authorize(AccessDeniedError())

    def test_timeout_is_sanitized(self):
        with self.assertRaisesRegex(GoogleOAuthError, "expirou"):
            self.authorize(WSGITimeoutError())

    def test_invalid_state_is_sanitized(self):
        with self.assertRaisesRegex(GoogleOAuthError, "state"):
            self.authorize(MismatchingStateError())

    def test_browser_error_is_actionable(self):
        with self.assertRaisesRegex(GoogleOAuthError, "navegador"):
            self.authorize(webbrowser.Error("browser-private-detail"))

    def test_false_browser_result_becomes_an_explicit_error(self):
        registry = {}

        def register(name, _browser_class, instance):
            registry[name] = instance

        class BrowserOpeningFlow:
            def run_local_server(self, **kwargs):
                registry[kwargs["browser"]].open("https://accounts.example")

        client = GoogleOAuthClient(
            FlowFactory(BrowserOpeningFlow()),
            browser_factory=ClosedBrowser,
            browser_registrar=register,
        )
        with self.assertRaisesRegex(GoogleOAuthError, "navegador"):
            client.authorize(self.config, 12)

    def test_provider_error_does_not_expose_original_message(self):
        marker = "fake-sensitive-provider-payload"
        with self.assertRaises(GoogleOAuthError) as raised:
            self.authorize(OAuth2Error(description=marker))
        self.assertNotIn(marker, str(raised.exception))

    def test_credentials_repr_does_not_include_credentials(self):
        result, _, _ = self.authorize(FakeCredentials())
        self.assertNotIn("FakeCredentials", repr(result))


if __name__ == "__main__":
    unittest.main()
