from abc import ABC, abstractmethod
from typing import Optional

from .types import TranscriptionResult


class TranscriptionProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        pass

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        audio_format: str,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        pass