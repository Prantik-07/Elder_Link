from dataclasses import dataclass
from typing import Optional


@dataclass
class TranscriptionResult:
    text: str
    model: str
    provider: str
    success: bool
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None

    @classmethod
    def success_result(
        cls,
        text: str,
        model: str,
        provider: str,
        language: Optional[str] = None,
        duration_seconds: Optional[float] = None,
    ) -> "TranscriptionResult":
        return cls(
            text=text,
            model=model,
            provider=provider,
            success=True,
            language=language,
            duration_seconds=duration_seconds,
            error=None,
        )

    @classmethod
    def failure_result(
        cls,
        model: str,
        provider: str,
        error: str,
    ) -> "TranscriptionResult":
        return cls(
            text="",
            model=model,
            provider=provider,
            success=False,
            error=error,
        )