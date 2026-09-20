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

from core.transcription.openai import (  # noqa: E402
    OpenAIConfigurationError,
    OpenAITranscriptionProvider,
)

KEY = "sk-secret-key-123"
URLOPEN = "core.transcription.openai.urllib.request.urlopen"


def fake_response(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda *a: False
    return resp


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://api.openai.com/x", code, "err", {}, io.BytesIO(body))


@pytest.fixture
def provider():
    return OpenAITranscriptionProvider(api_key=KEY)


GPT = {"text": " My sister is ill today. ", "languages": [{"code": "en"}]}
WHISPER = {
    "language": "english",
    "duration": 2.4,
    "text": "My sister is ill today. She did not eat.",
    "segments": [
        {"text": " My sister is ill today.", "start": 0.0, "end": 1.6},
        {"text": " She did not eat.", "start": 1.8, "end": 2.4},
        {"text": "  ", "start": 2.4, "end": 2.5},
    ],
}


class TestTranscribe:
    def test_gpt_transcribe_text_no_segments(self, provider):
        with patch(URLOPEN, return_value=fake_response(GPT)):
            r = provider.transcribe(b"a", "webm")
        assert r.success and r.text == "My sister is ill today."
        assert r.provider == "openai" and r.model == "gpt-transcribe"
        assert r.language == "en" and r.segments is None

    def test_whisper_segments_and_timestamps(self):
        p = OpenAITranscriptionProvider(api_key=KEY, model="whisper-1")
        with patch(URLOPEN, return_value=fake_response(WHISPER)):
            r = p.transcribe(b"a", "webm")
        assert r.segments == [
            {"text": "My sister is ill today.", "start_time": 0.0, "end_time": 1.6},
            {"text": "She did not eat.", "start_time": 1.8, "end_time": 2.4},
        ]
        assert r.duration_seconds == 2.4

    def test_missing_timing_is_null(self):
        p = OpenAITranscriptionProvider(api_key=KEY, model="whisper-1")
        with patch(URLOPEN, return_value=fake_response({"text": "a", "segments": [{"text": "a"}]})):
            r = p.transcribe(b"a", "webm")
        assert r.segments == [{"text": "a", "start_time": None, "end_time": None}]

    def test_empty_transcript(self, provider):
        with patch(URLOPEN, return_value=fake_response({"text": "", "languages": []})):
            r = provider.transcribe(b"a", "webm")
        assert r.success and r.text == "" and r.segments is None and r.language is None

    @pytest.mark.parametrize("payload", [{}, {"text": None}, {"text": 5}])
    def test_malformed_response(self, provider, payload):
        with patch(URLOPEN, return_value=fake_response(payload)):
            r = provider.transcribe(b"a", "webm")
        assert not r.success and "Malformed OpenAI response" in r.error and r.text == ""

    def test_non_json_response(self, provider):
        resp = fake_response({})
        resp.read.return_value = b"<html>"
        with patch(URLOPEN, return_value=resp):
            assert not provider.transcribe(b"a", "webm").success

    @pytest.mark.parametrize("code", [401, 403])
    def test_auth_errors(self, provider, code):
        with patch(URLOPEN, side_effect=http_error(code)):
            r = provider.transcribe(b"a", "webm")
        assert not r.success and f"HTTP {code}" in r.error and "API key" in r.error

    def test_rate_limit(self, provider):
        with patch(URLOPEN, side_effect=http_error(429)):
            r = provider.transcribe(b"a", "webm")
        assert not r.success and "429" in r.error

    @pytest.mark.parametrize(
        "code,message",
        [
            ("insufficient_quota", "You exceeded your current quota, please check your plan and billing details."),
            ("rate_limit_exceeded", "Rate limit reached for gpt-transcribe in organization on requests per min."),
        ],
    )
    def test_429_exposes_error_code_and_message(self, provider, code, message):
        body = json.dumps({"error": {"message": message, "type": "x", "code": code}}).encode()
        with patch(URLOPEN, side_effect=http_error(429, body)):
            r = provider.transcribe(b"a", "webm")
        assert not r.success and "HTTP 429" in r.error
        assert f"code={code}" in r.error and message[:40] in r.error

    def test_429_falls_back_to_type_when_code_null(self, provider):
        body = b'{"error":{"message":"slow down","type":"requests","code":null}}'
        with patch(URLOPEN, side_effect=http_error(429, body)):
            assert "code=requests" in provider.transcribe(b"a", "webm").error

    @pytest.mark.parametrize("body", [b"", b"not json", b"[]", b'{"error":"str"}', b'{"error":{}}'])
    def test_429_unparseable_body_is_safe(self, provider, body):
        with patch(URLOPEN, side_effect=http_error(429, body)):
            r = provider.transcribe(b"a", "webm")
        assert not r.success and "HTTP 429" in r.error and "details unavailable" in r.error

    def test_429_detail_scrubs_key_credentials_and_truncates(self, provider):
        msg = f"bad {KEY} and sk-proj-abcdef123456 org-AbCdEf123 " + "x" * 500
        body = json.dumps({"error": {"message": msg, "code": "rate_limit_exceeded"}}).encode()
        with patch(URLOPEN, side_effect=http_error(429, body)):
            err = provider.transcribe(b"a", "webm").error
        assert KEY not in err and "sk-proj" not in err and "org-AbCdEf" not in err
        assert "[REDACTED]" in err and len(err) < 400

    def test_server_error(self, provider):
        with patch(URLOPEN, side_effect=http_error(502)):
            r = provider.transcribe(b"a", "webm")
        assert not r.success and "server error (HTTP 502)" in r.error

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
            assert not provider.transcribe(b"x", "flac").success
        m.assert_not_called()


class TestRequest:
    @pytest.mark.parametrize(
        "fmt,ctype",
        [("webm", "audio/webm"), ("m4a", "audio/mp4"), ("mp4", "audio/mp4"),
         ("wav", "audio/wav"), ("mp3", "audio/mpeg"), ("WEBM", "audio/webm")],
    )
    def test_multipart_request_shape(self, provider, fmt, ctype):
        with patch(URLOPEN, return_value=fake_response(GPT)) as m:
            provider.transcribe(b"RAW-AUDIO", fmt)
        req = m.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.full_url == "https://api.openai.com/v1/audio/transcriptions"
        assert req.get_header("Authorization") == f"Bearer {KEY}"
        assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
        body = req.data
        assert b'name="model"\r\n\r\ngpt-transcribe' in body
        assert b'name="response_format"\r\n\r\njson' in body
        assert f'filename="audio.{fmt.lower()}"'.encode() in body
        assert f"Content-Type: {ctype}".encode() in body
        assert b"RAW-AUDIO" in body and KEY.encode() not in body
        assert b"timestamp_granularities" not in body and b"languages" not in body

    def test_whisper_request_fields(self):
        p = OpenAITranscriptionProvider(api_key=KEY, model="whisper-1")
        with patch(URLOPEN, return_value=fake_response(WHISPER)) as m:
            p.transcribe(b"a", "webm", language="en")
        body = m.call_args[0][0].data
        assert b"verbose_json" in body and b"timestamp_granularities[]" in body
        assert b'name="language"\r\n\r\nen' in body

    def test_gpt_language_hint_uses_languages(self, provider):
        with patch(URLOPEN, return_value=fake_response(GPT)) as m:
            provider.transcribe(b"a", "webm", language="en")
        assert b'name="languages"\r\n\r\nen' in m.call_args[0][0].data


class TestConfigAndSecrets:
    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(OpenAIConfigurationError) as e:
                OpenAITranscriptionProvider()
        assert isinstance(e.value, ValueError) and "OPENAI_API_KEY" in str(e.value)

    def test_env_config(self):
        env = {"OPENAI_API_KEY": KEY, "OPENAI_TRANSCRIPTION_MODEL": "gpt-4o-transcribe"}
        with patch.dict(os.environ, env):
            p = OpenAITranscriptionProvider()
        assert p.model_id == "gpt-4o-transcribe" and p.provider_name == "openai"

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

    def test_openai_selected(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openai", "OPENAI_API_KEY": KEY}):
            assert self.get_provider().provider_name == "openai"

    def test_openai_without_key_fails_no_fallback(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "openai"}):
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                self.get_provider()

    def test_other_providers_unchanged(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "mock"}):
            assert self.get_provider().provider_name == "mock"
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "deepgram", "DEEPGRAM_API_KEY": "k"}):
            assert self.get_provider().provider_name == "deepgram"


def _s3():
    s3 = MagicMock()
    s3.head_object.side_effect = [
        {"ContentLength": 10},
        ClientError({"Error": {"Code": "404", "Message": "nf"}}, "HeadObject"),
    ]
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"webm-bytes")}
    return s3


def _run(payload=None, side_effect=None):
    from backend.lambdas.process_audio.handler import lambda_handler
    s3 = _s3()
    provider = OpenAITranscriptionProvider(api_key=KEY)
    ev = {"detail": {"bucket": {"name": "b"}, "object": {"key": "audio/n1.webm"}}}
    with patch("backend.lambdas.process_audio.handler.boto3.client", return_value=s3), \
         patch("backend.lambdas.process_audio.handler.get_provider", return_value=provider), \
         patch.dict(os.environ, {"AUDIO_BUCKET_NAME": "b"}), \
         patch(URLOPEN, return_value=fake_response(payload) if payload else None,
               side_effect=side_effect):
        lambda_handler(ev, None)
    return json.loads(s3.put_object.call_args[1]["Body"])


def test_process_audio_openai_success_writes_real_transcript():
    written = _run(GPT)
    assert written["status"] == "completed" and written["provider"] == "openai"
    assert written["transcript"] == "My sister is ill today."
    assert "segments" not in written and KEY not in json.dumps(written)


def test_process_audio_openai_failure_no_fake_transcript():
    written = _run(side_effect=http_error(401))
    assert written["status"] == "failed" and written["transcript"] == ""
    assert "HTTP 401" in written["error"] and KEY not in json.dumps(written)
