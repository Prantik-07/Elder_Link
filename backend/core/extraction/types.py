from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ExtractionErrorKind(str, Enum):
    """Distinguishes *why* a provider call didn't yield usable candidates,
    so a caller can decide whether retrying makes sense (see pipeline.py -
    only INVALID_JSON is ever worth retrying; the rest are not transient)."""

    INVALID_JSON = "invalid_json"
    MODEL_REFUSAL = "model_refusal"
    PROVIDER_FAILURE = "provider_failure"
    NOT_AVAILABLE = "not_available"  # e.g. Bedrock access not yet granted


@dataclass
class ExtractionResult:
    """The raw, untrusted output of one provider call. `candidate_events`
    are plain dicts (the same JSON shape CareEvent.from_dict expects) - NOT
    yet parsed/validated CareEvents. Parsing and validation happen in
    pipeline.py, deliberately kept out of the provider so every provider is
    held to the same untrusted-until-proven-otherwise standard."""

    success: bool
    provider: str
    model: str
    candidate_events: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    error_kind: Optional[ExtractionErrorKind] = None

    @classmethod
    def success_result(cls, candidate_events: list[dict], provider: str, model: str) -> "ExtractionResult":
        return cls(success=True, provider=provider, model=model, candidate_events=candidate_events)

    @classmethod
    def failure_result(
        cls, provider: str, model: str, error: str, error_kind: ExtractionErrorKind
    ) -> "ExtractionResult":
        return cls(success=False, provider=provider, model=model, candidate_events=[], error=error, error_kind=error_kind)
