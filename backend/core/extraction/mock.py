"""Deterministic, keyword/regex-based mock extraction.

This is NOT real NLU and does not pretend to be - it's a small, honest rule
engine that implements the letter of the extraction contract (prompt.py)
well enough to develop and test the pipeline shape without network access
or Bedrock availability, the same role MockTranscriptionProvider plays for
Day 1's transcription step.

Note what this module deliberately does NOT decide: review_state,
verification_reason, and (as of Phase 4.1) event_id. review_state/
verification_reason are always emitted as unreviewed/None regardless of
what the text actually says, and event_id is just a positional placeholder
("candidate-0", "candidate-1", ...) - all three are untrusted
self-assessment from this "provider"'s point of view like everything else
it produces, and pipeline.py is the only thing that ever sets their real
values (via review_policy.py and identity.py respectively). This keeps the
"extraction output is untrusted" boundary honest even for the one provider
whose "model" is fully inspectable.

Known limitations (by design, not oversight - see the Phase 3/4 reports for
the full list):
  - operates per-segment, so a claim whose meaning only emerges by reading
    two segments together (evidence spanning multiple segments) is not
    reconstructed.
  - hedge/negation detection is keyword-based, so genuinely ambiguous
    phrasing with no explicit hedge word (e.g. "wasn't really feeling like
    himself") will not be flagged as uncertain.
  - no pronoun/coreference resolution - a subject referred to only as "he"
    later in a sentence isn't tied back to a name mentioned earlier.
These are exactly the kinds of gaps the Phase 1 evaluator exists to surface
- a real model-backed provider (BedrockExtractionProvider) is expected to
do meaningfully better on all three.
"""

from __future__ import annotations

import re

from backend.core.care_event import EventType, TranscriptDocument, TranscriptSegment

from .service import ExtractionProvider
from .types import ExtractionResult

# Checked in order; the first category whose keyword appears wins. Ordered
# so a narrow, specific cue (e.g. "tired") beats a broader one (e.g.
# "medication") when both happen to appear in the same sentence - see the
# module-level tests for the sentence that motivates this ordering
# ("She seemed tired after the medication" must classify as observation,
# not medication, even though both keywords are present).
_EVENT_TYPE_KEYWORDS: list[tuple[EventType, list[str]]] = [
    (EventType.OBSERVATION, ["tired", "feeling", "nausea", "energy", "appetite"]),
    (EventType.CONCERN, ["fell", "fall", "injury", "hurt", "wandering"]),
    (EventType.MEDICATION, ["medicine", "medication", "pill", "pills", "dose"]),
    (EventType.VITAL, ["blood pressure", "glucose", "temperature"]),
    (EventType.APPOINTMENT, ["appointment", "doctor", "cardiologist", "checkup"]),
]

# Checked before UNCERTAINTY: an explicit negation cue is a clean negation,
# not a hedge. Deliberately does NOT include a bare "\bnot\b" - that would
# also fire on "I'm not sure", which must be UNCERTAIN instead.
_NEGATION_RE = re.compile(r"\b(did not|didn't|does not|doesn't|never)\b", re.IGNORECASE)

# A deliberately broader set of hedge cues than just "I think" - see Phase 4
# section 8: the system must not require that exact phrase. Still purely
# lexical, not semantic understanding - genuinely ambiguous phrasing with
# none of these cues (e.g. "wasn't really feeling like himself") is still
# missed; see the module docstring.
_UNCERTAINTY_RE = re.compile(
    r"\b(i think|i believe|it seems( like)?|may have|might have|might|maybe|not sure|probably|unclear|wondering whether)\b",
    re.IGNORECASE,
)

_SECONDHAND_RE = re.compile(r"\bmy (\w+) (?:said|told me|thinks|says)\b", re.IGNORECASE)

_SUBJECT_TOKENS = ["Dad", "Mom", "Mum", "Grandpa", "Grandma", "She", "He"]

# Ordered most-specific first so e.g. "next Tuesday at 10am" is captured
# whole rather than only its "Tuesday" tail.
_TEMPORAL_PATTERNS = [
    re.compile(
        r"\bnext (monday|tuesday|wednesday|thursday|friday|saturday|sunday) at \d{1,2}(:\d{2})?\s*(am|pm)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bthis (morning|afternoon|evening)\b", re.IGNORECASE),
    re.compile(r"\byesterday(?: evening| morning)?\b", re.IGNORECASE),
    re.compile(r"\bin two days\b", re.IGNORECASE),
    re.compile(r"\baround \d{1,2}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", re.IGNORECASE),
    re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE),
    re.compile(r"\b(today|tomorrow|morning|afternoon|evening)\b", re.IGNORECASE),
]


def _detect_event_type(lower_text: str) -> EventType | None:
    for event_type, keywords in _EVENT_TYPE_KEYWORDS:
        if any(kw in lower_text for kw in keywords):
            return event_type
    return None


def _detect_subject(text: str) -> str | None:
    for token in _SUBJECT_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", text):
            return token
    return None


def _detect_temporal(text: str) -> dict:
    for pattern in _TEMPORAL_PATTERNS:
        match = pattern.search(text)
        if match:
            return {"precision": "relative", "expression": match.group(0)}
    return {"precision": "unknown"}


def _extract_segment_candidate(segment: TranscriptSegment, transcript_id: str, index: int) -> dict | None:
    text = segment.text
    lower = text.lower()

    if text.rstrip().endswith("-"):
        return None  # cut-off mid-word: insufficient evidence to extract anything
    if "wondering whether" in lower or text.rstrip().endswith("?"):
        return None  # a question/hypothetical, not a completed claim

    event_type = _detect_event_type(lower)
    if event_type is None:
        return None

    if _NEGATION_RE.search(text):
        claim_stance = "negated"
    elif _UNCERTAINTY_RE.search(text):
        claim_stance = "uncertain"
    else:
        claim_stance = "asserted"

    secondhand_match = _SECONDHAND_RE.search(text)
    if secondhand_match:
        source_type = "secondhand"
        reported_by = secondhand_match.group(1).lower()
    else:
        source_type = "firsthand"
        reported_by = None

    subject = _detect_subject(text) or "unspecified"

    return {
        # A parse-time placeholder only - pipeline.py always recomputes the
        # real, order-independent event_id via identity.assign_event_ids
        # and discards whatever this provider proposed (see mock.py's
        # module docstring: review_state/verification_reason get the same
        # treatment for the same reason).
        "event_id": f"candidate-{index}",
        "event_type": event_type.value,
        "subject": subject,
        "summary": text.strip().rstrip("."),
        "claim_stance": claim_stance,
        "source_type": source_type,
        # Always the minimal, honest starting state - see module docstring.
        # review_policy.derive_review_state, not this provider, decides the
        # real review_state/verification_reason.
        "review_state": "unreviewed",
        "occurred_at": _detect_temporal(text),
        "evidence": [{"segment_id": segment.segment_id}],
        "reported_by": reported_by,
        "verification_reason": None,
    }


class MockExtractionProvider(ExtractionProvider):
    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_id(self) -> str:
        return "mock-extractor-v1"

    def extract(self, document: TranscriptDocument) -> ExtractionResult:
        candidates = []
        for index, segment in enumerate(document.segments):
            candidate = _extract_segment_candidate(segment, document.transcript_id, index)
            if candidate is not None:
                candidates.append(candidate)
        return ExtractionResult.success_result(candidates, provider=self.provider_name, model=self.model_id)
