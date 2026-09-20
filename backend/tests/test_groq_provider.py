import io
import json
import os
import socket
import sys
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.transcription.groq import (  # noqa: E402
    GroqConfigurationError,
    GroqTranscriptionProvider,
)

KEY = "gsk_secretkey1234567890"
URLOPEN = "core.transcription.groq.urllib.request.urlopen"

VERBOSE = {
    "language": "English",
    "duration": 2.4,
    "text": " My sister is ill today. She did not eat.",
    "segments": [
        {"text": " My sister is ill today.", "start": 0.0, "end": 1.6},
        {"text": " She did not eat.", "start": 1.8, "end": 2.4},
        {"text": "  ", "start": 2.4, "end": 2.5},
    ],
}


def fake_response(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda *a: False
    return resp


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://api.groq.com/x", code, "err", {}, io.BytesIO(body))


@pytest.fixture
def provider():
    return GroqTranscriptionProvider(api_key=KEY)


class TestTranscribe:
    def test_text_segments_and_timestamps(self, provider):
        with patch(URLOPEN, return_value=fake_response(VERBOSE)):
            r = provider.transcribe(b"a", "webm")
        assert r.success and r.text == "My sister is ill today. She did not eat."
        assert r.provider == "groq" and r.model == "whisper-large-v3-turbo"
        assert r.duration_seconds == 2.4 and r.language == "English"
        assert r.segments == [
            {"text": "My sister is ill today.", "start_time": 0.0, "end_time": 1.6},
            {"text": "She did not eat.", "start_time": 1.8, "end_time": 2.4},
        ]

    def test_missing_timing_is_null(self, provider):
        payload = {"text": "a", "segments": [{"text": "a"}]}
        with patch(URLOPEN, return_value=fake_response(payload)):
            r = provider.transcribe(b"a", "webm")
        assert r.segments == [{"text": "a", "start_time": None, "end_time": None}]

    def test_no_segments_returns_none(self, provider):
        with patch(URLOPEN, return_value=fake_response({"text": "hello"})):
            r = provider.transcribe(b"a", "webm")
        assert r.success and r.text == "hello" and r.segments is None

    def test_empty_transcript(self, provider):
        with patch(URLOPEN, return_value=fake_response({"text": "", "segments": []})):
            r = provider.transcribe(b"a", "webm")
        assert r.success and r.text == "" and r.segments is None

    @pytest.mark.parametrize("payload", [{}, {"text": None}, {"text": 5}])
    def test_malformed_response(self, provider, payload):
        with patch(URLOPEN, return_value=fake_response(payload)):
            r = provider.transcribe(b"a", "webm")
        assert not r.success and "Malformed Groq response" in r.error and r.text == ""

    def test_non_json_response(self, provider):
        resp = fake_response({})
        resp.read.return_value = b"<html>"
        with patch(URLOPEN, return_value=resp):
            assert not provider.transcribe(b"a", "webm").success

    @pytest.mark.parametrize("code", [401, 403])
    def test_auth_errors(self, provider, code):
        with patch(URLOPEN, side_effect=http_error(code)):
            r = provider.transcribe(b"a", "webm")
        assert not r.success and f"HTTP {code}" in r.error and "GROQ_API_KEY" in r.error

    def test_429_exposes_code_and_message(self, provider):
        body = json.dumps({"error": {"message": "Rate limit reached", "code": "rate_limit_exceeded"}}).encode()
        with patch(URLOPEN, side_effect=http_error(429, body)):
            r = provider.transcribe(b"a", "webm")
        assert "HTTP 429" in r.error and "code=rate_limit_exceeded" in r.error

    def test_429_unparseable_body_safe(self, provider):
        with patch(URLOPEN, side_effect=http_error(429, b"nope")):
            assert "details unavailable" in provider.transcribe(b"a", "webm").error

    def test_error_detail_scrubs_credentials(self, provider):
        msg = f"bad {KEY} gsk_abcdef123456 sk-proj-abcdef123456 " + "x" * 500
        body = json.dumps({"error": {"message": msg, "code": "invalid_api_key"}}).encode()
        with patch(URLOPEN, side_effect=http_error(401, body)):
            err = provider.transcribe(b"a", "webm").error
        assert KEY not in err and "gsk_abcdef" not in err and "sk-proj" not in err
        assert "[REDACTED]" in err and len(err) < 400

    def test_server_error(self, provider):
        with patch(URLOPEN, side_effect=http_error(503)):
            assert "server error (HTTP 503)" in provider.transcribe(b"a", "webm").error

    @pytest.mark.parametrize("exc", [socket.timeout(), urllib.error.URLError(socket.timeout())])
    def test_timeout(self, provider, exc):
        with patch(URLOPEN, side_effect=exc):
            r = provider.transcribe(b"a", "webm")
        assert not r.success and "timed out" in r.error

    def test_network_error(self, provider):
        with patch(URLOPEN, side_effect=urllib.error.URLError(ConnectionRefusedError())):
            assert "network error" in provider.transcribe(b"a", "webm").error

    def test_empty_audio_and_unsupported_format_make_no_request(self, provider):
        with patch(URLOPEN) as m:
            assert not provider.transcribe(b"", "webm").success
            assert not provider.transcribe(b"x", "aiff").success
        m.assert_not_called()


class TestRequest:
    @pytest.mark.parametrize(
        "fmt,ctype",
        [("webm", "audio/webm"), ("m4a", "audio/mp4"), ("mp4", "audio/mp4"),
         ("wav", "audio/wav"), ("mp3", "audio/mpeg"), ("flac", "audio/flac"),
         ("ogg", "audio/ogg"), ("WEBM", "audio/webm")],
    )
    def test_multipart_request_shape(self, provider, fmt, ctype):
        with patch(URLOPEN, return_value=fake_response(VERBOSE)) as m:
            provider.transcribe(b"RAW-AUDIO", fmt)
        req = m.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.full_url == "https://api.groq.com/openai/v1/audio/transcriptions"
        assert req.get_header("Authorization") == f"Bearer {KEY}"
        assert req.get_header("User-agent") == "ElderLink/1.0"
        assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
        body = req.data
        assert b'name="model"\r\n\r\nwhisper-large-v3-turbo' in body
        assert b'name="response_format"\r\n\r\nverbose_json' in body
        assert b'name="timestamp_granularities[]"\r\n\r\nsegment' in body
        assert f'filename="audio.{fmt.lower()}"'.encode() in body
        assert f"Content-Type: {ctype}".encode() in body
        assert b"RAW-AUDIO" in body and KEY.encode() not in body
        assert b'name="language"' not in body

    def test_language_hint(self, provider):
        with patch(URLOPEN, return_value=fake_response(VERBOSE)) as m:
            provider.transcribe(b"a", "webm", language="en")
        assert b'name="language"\r\n\r\nen' in m.call_args[0][0].data


class TestConfigAndSecrets:
    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(GroqConfigurationError) as e:
                GroqTranscriptionProvider()
        assert isinstance(e.value, ValueError) and "GROQ_API_KEY" in str(e.value)

    def test_env_config(self):
        env = {"GROQ_API_KEY": KEY, "GROQ_TRANSCRIPTION_MODEL": "whisper-large-v3"}
        with patch.dict(os.environ, env):
            p = GroqTranscriptionProvider()
        assert p.model_id == "whisper-large-v3" and p.provider_name == "groq"

    def test_key_never_in_errors_or_output(self, provider, capsys):
        for exc in [http_error(401), http_error(500), socket.timeout(),
                    urllib.error.URLError(f"boom {KEY}")]:
            with patch(URLOPEN, side_effect=exc):
                assert KEY not in (provider.transcribe(b"a", "webm").error or "")
        assert provider._safe(f"x {KEY}") == "x [REDACTED]"
        out = capsys.readouterr()
        assert KEY not in out.out + out.err


class TestFactory:
    @pytest.fixture(autouse=True)
    def _imports(self):
        from backend.lambdas.process_audio.handler import get_provider
        self.get_provider = get_provider

    def test_groq_selected(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "groq", "GROQ_API_KEY": KEY}):
            assert self.get_provider().provider_name == "groq"

    def test_groq_without_key_fails_no_fallback(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "groq"}):
            os.environ.pop("GROQ_API_KEY", None)
            with pytest.raises(ValueError, match="GROQ_API_KEY"):
                self.get_provider()

    def test_other_providers_unchanged(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "mock"}):
            assert self.get_provider().provider_name == "mock"
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openai", "OPENAI_API_KEY": "k"}):
            assert self.get_provider().provider_name == "openai"


def _run(payload=None, side_effect=None):
    from backend.lambdas.process_audio.handler import lambda_handler
    s3 = MagicMock()
    s3.head_object.side_effect = [
        {"ContentLength": 10},
        ClientError({"Error": {"Code": "404", "Message": "nf"}}, "HeadObject"),
    ]
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"webm-bytes")}
    ev = {"detail": {"bucket": {"name": "b"}, "object": {"key": "audio/n1.webm"}}}
    with patch("backend.lambdas.process_audio.handler.boto3.client", return_value=s3), \
         patch("backend.lambdas.process_audio.handler.get_provider",
               return_value=GroqTranscriptionProvider(api_key=KEY)), \
         patch.dict(os.environ, {"AUDIO_BUCKET_NAME": "b"}), \
         patch(URLOPEN, return_value=fake_response(payload) if payload else None,
               side_effect=side_effect):
        lambda_handler(ev, None)
    return json.loads(s3.put_object.call_args[1]["Body"])


def test_process_audio_groq_success_writes_segments():
    written = _run(VERBOSE)
    assert written["status"] == "completed" and written["provider"] == "groq"
    assert written["transcript"].startswith("My sister is ill today.")
    assert written["segments"][0] == {"text": "My sister is ill today.", "start_time": 0.0, "end_time": 1.6}
    assert KEY not in json.dumps(written)


def test_process_audio_groq_failure_no_fake_transcript():
    written = _run(side_effect=http_error(401))
    assert written["status"] == "failed" and written["transcript"] == ""
    assert "segments" not in written and KEY not in json.dumps(written)
