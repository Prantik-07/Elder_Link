import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from .types import TranscriptionResult
from .service import TranscriptionProvider


class DeepgramConfigurationError(ValueError):
    """Missing/invalid Deepgram configuration. A ValueError subclass so
    process_audio's existing misconfiguration handling (log + re-raise, so
    Lambda records an execution error) applies without any handler change."""


class DeepgramTranscriptionProvider(TranscriptionProvider):
    ENDPOINT = "https://api.deepgram.com/v1/listen"
    DEFAULT_MODEL = "nova-3"
    DEFAULT_LANGUAGE = "en"

    # Extension (as derived by process_audio.get_audio_format) -> the real
    # Content-Type sent to Deepgram. Browser recordings are labelled by what
    # they actually are; nothing is blindly sent as audio/wav. Note m4a is
    # what audio_upload_url stores Safari's audio/mp4 recordings as.
    CONTENT_TYPES = {
        "webm": "audio/webm",
        "mp4": "audio/mp4",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "ogg": "audio/ogg",
    }
    SUPPORTED_FORMATS = set(CONTENT_TYPES)

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
        timeout_seconds: float = 40.0,
    ):
        self._api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not self._api_key:
            raise DeepgramConfigurationError(
                "DEEPGRAM_API_KEY environment variable not set"
            )
        self._model = model or os.getenv("DEEPGRAM_MODEL", self.DEFAULT_MODEL)
        self._language = language or os.getenv("DEEPGRAM_LANGUAGE", self.DEFAULT_LANGUAGE)
        self._timeout = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "deepgram"

    @property
    def model_id(self) -> str:
        return self._model

    def _safe(self, message: str) -> str:
        # Defence in depth: the key is never intentionally put in a message,
        # but scrub it in case an upstream error string echoes it.
        return message.replace(self._api_key, "[REDACTED]")

    def _failure(self, error: str) -> TranscriptionResult:
        return TranscriptionResult.failure_result(
            model=self._model,
            provider=self.provider_name,
            error=self._safe(error),
        )

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

        query = urllib.parse.urlencode(
            {
                "model": self._model,
                "language": language or self._language,
                "smart_format": "true",
                "punctuate": "true",
                "utterances": "true",
            }
        )
        request = urllib.request.Request(
            f"{self.ENDPOINT}?{query}",
            data=audio_bytes,
            method="POST",
            headers={
                "Authorization": f"Token {self._api_key}",
                "Content-Type": content_type,
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as e:
            return self._failure(self._http_error_message(e))
        except (socket.timeout, TimeoutError):
            return self._failure(
                f"Deepgram request timed out after {self._timeout:g}s"
            )
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                return self._failure(
                    f"Deepgram request timed out after {self._timeout:g}s"
                )
            return self._failure(f"Deepgram network error: {type(e.reason).__name__}")
        except OSError as e:
            return self._failure(f"Deepgram network error: {type(e).__name__}")

        try:
            payload = json.loads(raw)
            return self._parse(payload, language or self._language)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
            return self._failure(
                f"Malformed Deepgram response: {type(e).__name__}: {e}"
            )

    @staticmethod
    def _http_error_message(e: urllib.error.HTTPError) -> str:
        code = e.code
        if code in (401, 403):
            return (
                f"Deepgram rejected the API key (HTTP {code}); "
                "check DEEPGRAM_API_KEY permissions"
            )
        if code == 429:
            return "Deepgram rate limit or concurrency limit hit (HTTP 429); retry later"
        if code >= 500:
            return f"Deepgram server error (HTTP {code})"
        return f"Deepgram request failed (HTTP {code})"

    def _parse(self, payload: dict[str, Any], language: str) -> TranscriptionResult:
        results = payload["results"]
        alternative = results["channels"][0]["alternatives"][0]
        text = alternative["transcript"]
        if not isinstance(text, str):
            raise TypeError("transcript is not a string")
        text = text.strip()

        duration = (payload.get("metadata") or {}).get("duration")
        segments = self._segments(results.get("utterances"))

        result = TranscriptionResult.success_result(
            text=text,
            model=self._model,
            provider=self.provider_name,
            language=language,
            duration_seconds=duration if isinstance(duration, (int, float)) else None,
        )
        # Only real utterances become segments; when Deepgram returns none the
        # downstream adapter falls back to its own sentence split of `text`.
        result.segments = segments if text else None
        return result

    @staticmethod
    def _segments(utterances: Any) -> Optional[list[dict[str, Any]]]:
        if not utterances:
            return None
        segments = []
        for u in utterances:
            seg_text = str(u["transcript"]).strip()
            if not seg_text:
                continue
            start, end = u.get("start"), u.get("end")
            segments.append(
                {
                    "text": seg_text,
                    "start_time": float(start) if isinstance(start, (int, float)) else None,
                    "end_time": float(end) if isinstance(end, (int, float)) else None,
                }
            )
        return segments or None
