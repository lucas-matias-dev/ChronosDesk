import base64
import hashlib
import json
import unittest
from urllib.parse import parse_qs, urlparse

from callback_server import CallbackError, parse_callback_target
from serial_transport import PROTOCOL_VERSION, build_message
from spotify_auth import (
    REQUIRED_SCOPE,
    SpotifyAuthorizationError,
    build_authorization_url,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
    parse_token_payload,
)


class PkceTests(unittest.TestCase):
    def test_verifier_and_challenge_are_url_safe_without_padding(self):
        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        self.assertEqual(challenge, expected)
        self.assertNotIn("=", challenge)

    def test_state_is_random_and_non_empty(self):
        self.assertNotEqual(generate_state(), generate_state())

    def test_authorization_url_requests_only_required_scope(self):
        url = build_authorization_url("client", "http://127.0.0.1:8888/callback", "c", "s")
        parameters = parse_qs(urlparse(url).query)
        self.assertEqual(parameters["scope"], [REQUIRED_SCOPE])
        self.assertEqual(parameters["code_challenge_method"], ["S256"])


class CallbackTests(unittest.TestCase):
    def test_valid_callback(self):
        result = parse_callback_target("/callback?code=abc&state=expected", "expected")
        self.assertEqual(result.authorization_code, "abc")

    def test_wrong_state_is_rejected(self):
        with self.assertRaises(CallbackError):
            parse_callback_target("/callback?code=abc&state=wrong", "expected")

    def test_access_denied_is_rejected(self):
        with self.assertRaisesRegex(CallbackError, "recusada"):
            parse_callback_target(
                "/callback?error=access_denied&state=expected", "expected"
            )


class TokenTests(unittest.TestCase):
    def test_token_payload(self):
        result = parse_token_payload(
            json.dumps(
                {"refresh_token": "x" * 32, "scope": REQUIRED_SCOPE}
            ).encode()
        )
        self.assertEqual(result.scopes, REQUIRED_SCOPE)
        result.clear()
        self.assertEqual(result.refresh_token, "")

    def test_missing_token_is_rejected(self):
        with self.assertRaises(SpotifyAuthorizationError):
            parse_token_payload(json.dumps({"scope": REQUIRED_SCOPE}).encode())


class SerialProtocolTests(unittest.TestCase):
    def test_versioned_newline_delimited_json(self):
        message = build_message("provision_begin")
        self.assertTrue(message.endswith(b"\n"))
        document = json.loads(message)
        self.assertEqual(document["protocol"], PROTOCOL_VERSION)
        self.assertEqual(document["type"], "provision_begin")


if __name__ == "__main__":
    unittest.main()
