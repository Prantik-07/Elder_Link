import json
import os
import re
import socket
import urllib.error
import urllib.request
import uuid
from typing import Any, Optional

from .types import TranscriptionResult
from .service import TranscriptionProvider


class OpenAIConfigurationError(ValueError):
    """Missing/invalid OpenAI configuration. A ValueError subclass so
    process_audio's existing misconfiguration handling (log + re-raise)
    applies without any handler change."""


class OpenAITranscriptionProvider(TranscriptionProvider):
    ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
    DEFAULT_MODEL = "gpt-transcribe"

    # Extension (as derived by process_audio.get_audio_format) -> Content-Type
    # of the multipart file part. Accepted input formats per OpenAI's
    # speech-to-text guide: mp3, mp4, mpeg, mpga, m4a, wav, webm. flac/ogg are
    # deliberately not listed there, so they are rejected up front.
    CONTENT_TYPES = {
        "webm": "audio/webm",
        "mp4": "audio/mp4",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "mpeg": "audio/mpeg",
        "mpga": "audio/mpeg",
    }
    SUPPORTED_FORMATS = set(CONTENT_TYPES)

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        timeout_seconds: float = 40.0,
    ):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise OpenAIConfigurationError("OPENAI_API_KEY environment variable not set")
        self._model = model or os.getenv("OPENAI_TRANSCRIPTION_MODEL", self.DEFAULT_MODEL)
        # Optional ISO-639-1 hint; unset means the model auto-detects.
        self._language = language or os.getenv("OPENAI_TRANSCRIPTION_LANGUAGE") or None
        self._timeout = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_id(self) -> str:
        return self._model

    def _safe(self, message: str) -> str:
        return message.replace(self._api_key, "[REDACTED]")

    def _failure(self, error: str) -> TranscriptionResult:
        return TranscriptionResult.failure_result(
            model=self._model,
            provider=self.provider_name,
            error=self._safe(error),
        )

    def _fields(self, language: Optional[str]) -> list[tuple[str, str]]:
        fields = [("model", self._model)]
        lang = language or self._language
        if self._model == "whisper-1":
            # Only whisper-1 returns segment timestamps (verbose_json).
            fields += [
                ("response_format", "verbose_json"),
                ("timestamp_granularities[]", "segment"),
            ]
            if lang:
                fields.append(("language", lang))
        else:
            fields.append(("response_format", "json"))
            if lang:
                # gpt-transcribe/gpt-4o-* take language hints as `languages`.
                fields.append(("languages", lang))
        return fields

    def _multipart(
        self, fields: list[tuple[str, str]], audio: bytes, fmt: str, content_type: str
    ) -> tuple[bytes, str]:
        boundary = f"elderlink{uuid.uuid4().hex}"
        parts: list[bytes] = []
        for name, value in fields:
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
            )
        # The filename extension drives server-side format detection.
        parts.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                f'filename="audio.{fmt}"\r\nContent-Type: {content_type}\r\n\r\n'
            ).encode()
        )
        parts.append(audio)
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        return b"".join(parts), f"multipart/form-data; boundary={boundary}"

    def transcribe(
        self,
        audio_bytes: bytes,
        audio_format: str,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        fmt = (audio_format or "").lower()
        content_type = self.CONTENT_TYPES.get(fmt)
        if content_type is None:
            return self._failure(
                f"Unsupported audio format: {audio_format}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )
        if not audio_bytes:
            return self._failure("Empty audio bytes provided")

        body, multipart_type = self._multipart(
            self._fields(language), audio_bytes, fmt, content_type
        )
        request = urllib.request.Request(
            self.ENDPOINT,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": multipart_type,
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as e:
            return self._failure(self._http_error_message(e))
        except (socket.timeout, TimeoutError):
            return self._failure(f"OpenAI request timed out after {self._timeout:g}s")
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                return self._failure(f"OpenAI request timed out after {self._timeout:g}s")
            return self._failure(f"OpenAI network error: {type(e.reason).__name__}")
        except OSError as e:
            return self._failure(f"OpenAI network error: {type(e).__name__}")

        try:
            return self._parse(json.loads(raw), language or self._language)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
            return self._failure(f"Malformed OpenAI response: {type(e).__name__}: {e}")

    @staticmethod
    def _http_error_message(e: urllib.error.HTTPError) -> str:
        code = e.code
        if code in (401, 403):
            return (
                f"OpenAI rejected the API key (HTTP {code}); "
                "check OPENAI_API_KEY and project permissions"
            )
        if code == 429:
            return f"OpenAI rate limit or quota exceeded (HTTP 429){OpenAITranscriptionProvider._error_detail(e)}"
        if code >= 500:
            return f"OpenAI server error (HTTP {code})"
        return f"OpenAI request failed (HTTP {code})"

    # Credential-looking tokens (sk-..., org-..., proj_...) that an upstream
    # message might echo; removed from anything surfaced from a response body.
    _SECRET_LIKE = re.compile(r"\b(?:sk|org|proj)[-_][A-Za-z0-9_*\-]{4,}")
    _MAX_DETAIL = 200

    @staticmethod
    def _error_detail(e: urllib.error.HTTPError) -> str:
        """Only OpenAI's `error.code` (e.g. insufficient_quota,
        rate_limit_exceeded) and a truncated, credential-scrubbed
        `error.message`. Never request data; never the raw body."""
        try:
            err = json.loads(e.read())["error"]
            code = err.get("code") or err.get("type")
            message = err.get("message")
        except Exception:
            return "; details unavailable"
        parts = []
        if isinstance(code, str) and code:
            parts.append(f"code={OpenAITranscriptionProvider._scrub(code)}")
        if isinstance(message, str) and message:
            parts.append(f"message={OpenAITranscriptionProvider._scrub(message)!r}")
        return f"; {', '.join(parts)}" if parts else "; details unavailable"

    @classmethod
    def _scrub(cls, text: str) -> str:
        text = cls._SECRET_LIKE.sub("[REDACTED]", " ".join(text.split()))
        return text[: cls._MAX_DETAIL]

    def _parse(self, payload: dict[str, Any], language: Optional[str]) -> TranscriptionResult:
        text = payload["text"]
        if not isinstance(text, str):
            raise TypeError("text is not a string")
        text = text.strip()

        # verbose_json (whisper-1) reports the detected language name and
        # duration; json (gpt-transcribe) reports `languages: [{code}]`.
        detected = payload.get("language")
        if not isinstance(detected, str):
            langs = payload.get("languages")
            detected = langs[0].get("code") if isinstance(langs, list) and langs else None
        duration = payload.get("duration")

        result = TranscriptionResult.success_result(
            text=text,
            model=self._model,
            provider=self.provider_name,
            language=detected or language,
            duration_seconds=duration if isinstance(duration, (int, float)) else None,
        )
        # Only real timed segments (whisper-1) are passed on; gpt-transcribe
        # returns none, so the downstream sentence-split adapter is used and
        # timings stay null rather than invented.
        result.segments = self._segments(payload.get("segments")) if text else None
        return result

    @staticmethod
    def _segments(segments: Any) -> Optional[list[dict[str, Any]]]:
        if not segments:
            return None
        out = []
        for s in segments:
            seg_text = str(s["text"]).strip()
            if not seg_text:
                continue
            start, end = s.get("start"), s.get("end")
            out.append(
                {
                    "text": seg_text,
                    "start_time": float(start) if isinstance(start, (int, float)) else None,
                    "end_time": float(end) if isinstance(end, (int, float)) else None,
                }
            )
        return out or None
