import io
import json
import os
import socket
import sys
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.transcription.deepgram import (  # noqa: E402
    DeepgramConfigurationError,
    DeepgramTranscriptionProvider,
)

KEY = "dg-secret-key-123"
URLOPEN = "core.transcription.deepgram.urllib.request.urlopen"


def dg_payload(transcript="my sister is ill today", utterances=None, duration=2.5):
    body = {
        "metadata": {"duration": duration},
        "results": {"channels": [{"alternatives": [{"transcript": transcript}]}]},
    }
    if utterances is not None:
        body["results"]["utterances"] = utterances
    return body


def fake_response(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda *a: False
    return resp


def http_error(code):
    return urllib.error.HTTPError(
        "https://api.deepgram.com/v1/listen", code, "err", {}, io.BytesIO(b'{"err_msg":"x"}')
    )


@pytest.fixture
def provider():
    return DeepgramTranscriptionProvider(api_key=KEY)


class TestTranscribe:
    def test_valid_response(self, provider):
        with patch(URLOPEN, return_value=fake_response(dg_payload())):
            r = provider.transcribe(b"audio", "webm")
        assert r.success and r.text == "my sister is ill today"
        assert r.provider == "deepgram" and r.model == "nova-3"
        assert r.duration_seconds == 2.5 and r.segments is None

    def test_multiple_utterances_and_timestamps(self, provider):
        utts = [
            {"transcript": "My sister is ill today.", "start": 0.1, "end": 1.9},
            {"transcript": "She did not eat.", "start": 2.2, "end": 3.4},
        ]
        with patch(URLOPEN, return_value=fake_response(dg_payload("x", utts))):
            r = provider.transcribe(b"audio", "webm")
        assert r.segments == [
            {"text": "My sister is ill today.", "start_time": 0.1, "end_time": 1.9},
            {"text": "She did not eat.", "start_time": 2.2, "end_time": 3.4},
        ]

    def test_missing_timing_is_null_not_invented(self, provider):
        with patch(URLOPEN, return_value=fake_response(dg_payload("a", [{"transcript": "a"}]))):
            r = provider.transcribe(b"audio", "webm")
        assert r.segments == [{"text": "a", "start_time": None, "end_time": None}]

    def test_empty_transcript(self, provider):
        with patch(URLOPEN, return_value=fake_response(dg_payload("", []))):
            r = provider.transcribe(b"audio", "webm")
        assert r.success and r.text == "" and r.segments is None

    @pytest.mark.parametrize(
        "payload", [{}, {"results": {}}, {"results": {"channels": []}}, {"results": {"channels": [{"alternatives": [{}]}]}}]
    )
    def test_malformed_response(self, provider, payload):
        with patch(URLOPEN, return_value=fake_response(payload)):
            r = provider.transcribe(b"audio", "webm")
        assert not r.success and "Malformed Deepgram response" in r.error and r.text == ""

    def test_non_json_response(self, provider):
        resp = fake_response({})
        resp.read.return_value = b"<html>"
        with patch(URLOPEN, return_value=resp):
            r = provider.transcribe(b"audio", "webm")
        assert not r.success and "Malformed" in r.error

    @pytest.mark.parametrize("code", [401, 403])
    def test_auth_errors(self, provider, code):
        with patch(URLOPEN, side_effect=http_error(code)):
            r = provider.transcribe(b"audio", "webm")
        assert not r.success and f"HTTP {code}" in r.error and "API key" in r.error

    def test_rate_limit(self, provider):
        with patch(URLOPEN, side_effect=http_error(429)):
            r = provider.transcribe(b"audio", "webm")
        assert not r.success and "429" in r.error and "retry" in r.error

    def test_server_error(self, provider):
        with patch(URLOPEN, side_effect=http_error(503)):
            r = provider.transcribe(b"audio", "webm")
        assert not r.success and "server error (HTTP 503)" in r.error

    @pytest.mark.parametrize(
        "exc", [socket.timeout(), urllib.error.URLError(socket.timeout())]
    )
    def test_timeout(self, provider, exc):
        with patch(URLOPEN, side_effect=exc):
            r = provider.transcribe(b"audio", "webm")
        assert not r.success and "timed out" in r.error

    def test_network_error(self, provider):
        with patch(URLOPEN, side_effect=urllib.error.URLError(ConnectionRefusedError())):
            r = provider.transcribe(b"audio", "webm")
        assert not r.success and "network error" in r.error

    def test_empty_audio_and_unsupported_format_make_no_request(self, provider):
        with patch(URLOPEN) as m:
            assert not provider.transcribe(b"", "webm").success
            assert not provider.transcribe(b"x", "aiff").success
        m.assert_not_called()


class TestRequest:
    @pytest.mark.parametrize(
        "fmt,ctype",
        [("webm", "audio/webm"), ("m4a", "audio/mp4"), ("mp4", "audio/mp4"),
         ("wav", "audio/wav"), ("mp3", "audio/mpeg"), ("WEBM", "audio/webm")],
    )
    def test_content_type_and_request_shape(self, provider, fmt, ctype):
        with patch(URLOPEN, return_value=fake_response(dg_payload())) as m:
            provider.transcribe(b"raw-bytes", fmt)
        req = m.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.full_url.startswith("https://api.deepgram.com/v1/listen?")
        assert req.data == b"raw-bytes"
        assert req.get_header("Content-type") == ctype
        assert req.get_header("Authorization") == f"Token {KEY}"
        for q in ("model=nova-3", "language=en", "smart_format=true", "punctuate=true", "utterances=true"):
            assert q in req.full_url
        for unwanted in ("diarize", "sentiment", "summarize"):
            assert unwanted not in req.full_url
        assert KEY not in req.full_url

    def test_language_override(self, provider):
        with patch(URLOPEN, return_value=fake_response(dg_payload())) as m:
            r = provider.transcribe(b"a", "webm", language="hi")
        assert "language=hi" in m.call_args[0][0].full_url and r.language == "hi"


class TestConfigAndSecrets:
    def test_missing_key_is_config_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(DeepgramConfigurationError) as e:
                DeepgramTranscriptionProvider()
        assert isinstance(e.value, ValueError) and "DEEPGRAM_API_KEY" in str(e.value)

    def test_key_from_env(self):
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": KEY}):
            assert DeepgramTranscriptionProvider().provider_name == "deepgram"

    def test_key_never_in_errors_or_output(self, provider, capsys):
        leaky = urllib.error.URLError(f"boom {KEY}")
        cases = [http_error(401), http_error(500), socket.timeout(), leaky]
        for exc in cases:
            with patch(URLOPEN, side_effect=exc):
                r = provider.transcribe(b"audio", "webm")
            assert KEY not in (r.error or "")
        assert provider._safe(f"x {KEY} y") == "x [REDACTED] y"
        out = capsys.readouterr()
        assert KEY not in out.out + out.err


class TestFactory:
    @pytest.fixture(autouse=True)
    def _imports(self):
        from backend.lambdas.process_audio.handler import get_provider
        self.get_provider = get_provider

    def test_deepgram_selected(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "deepgram", "DEEPGRAM_API_KEY": KEY}):
            assert self.get_provider().provider_name == "deepgram"

    def test_deepgram_without_key_fails_no_fallback(self):
        env = {"TRANSCRIPTION_PROVIDER": "deepgram"}
        with patch.dict(os.environ, env):
            os.environ.pop("DEEPGRAM_API_KEY", None)
            with pytest.raises(ValueError, match="DEEPGRAM_API_KEY"):
                self.get_provider()

    def test_mock_selected(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "mock"}):
            assert self.get_provider().provider_name == "mock"

    def test_voxtral_selected(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "voxtral"}):
            with patch("core.transcription.voxtral.boto3.client"):
                assert self.get_provider().provider_name == "voxtral"
