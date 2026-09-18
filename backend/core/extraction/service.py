from abc import ABC, abstractmethod

from backend.core.care_event import TranscriptDocument

from .types import ExtractionResult


class ExtractionProvider(ABC):
    """Analogous to backend.core.transcription.TranscriptionProvider: an
    abstraction the rest of the system depends on instead of any specific
    model/vendor. Nothing outside this package (and its implementations)
    should import Bedrock directly."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        pass

    @abstractmethod
    def extract(self, document: TranscriptDocument) -> ExtractionResult:
        pass
