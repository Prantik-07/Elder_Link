from typing import Optional

from .types import TranscriptionResult
from .service import TranscriptionProvider


MOCK_TRANSCRIPT = (
    "Papa ne subah wali medicine le li thi, lekin lunch bahut kam khaya "
    "aur shaam ko ghutne mein phir dard tha."
)


class MockTranscriptionProvider(TranscriptionProvider):
    def __init__(self, fixed_transcript: Optional[str] = None):
        self._fixed_transcript = fixed_transcript or MOCK_TRANSCRIPT

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_id(self) -> str:
        return "mock-transcriber-v1"

    def transcribe(
        self,
        audio_bytes: bytes,
        audio_format: str,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        if not audio_bytes:
            return TranscriptionResult.failure_result(
                model=self.model_id,
                provider=self.provider_name,
                error="Empty audio bytes provided",
            )

        return TranscriptionResult.success_result(
            text=self._fixed_transcript,
            model=self.model_id,
            provider=self.provider_name,
            language=language or "hi-IN",
            duration_seconds=len(audio_bytes) / 16000.0,
        )