"""Deterministic normalization rules for building CareEvents from noisy
upstream text (e.g. raw extractor output).

These are NOT applied automatically inside CareEvent.from_dict - that
constructor stays strict so golden/test data round-trips exactly and
unknown values are rejected loudly rather than silently coerced. A future
extractor should call these explicitly before constructing a CareEvent from
raw model output.

Rules, and why each stops where it does:

- whitespace: collapse internal whitespace runs to a single space, strip
  leading/trailing whitespace. Applied to `subject` and `summary`. Never
  applied to transcript segment text (TranscriptDocument owns that) or to
  anything that would change wording.

- event types: lowercase + trim the raw token before matching against the
  EventType vocabulary. An unrecognized token is still rejected by
  EventType(...), never silently coerced to OTHER - that would hide
  extractor bugs instead of surfacing them.

- subject naming: whitespace-only normalization. Casing and nicknames
  ("Dad", "mom", "Grandpa Joe") are preserved as given - they carry
  caregiver-specific meaning that shouldn't be forced into a canonical
  form. Case-insensitive comparison, where needed, happens at the call
  site (e.g. the evaluator), not by mutating stored data.

- timestamps/dates: must already be valid ISO 8601 - never guessed,
  completed, or shifted to a different timezone. If a provider gives a
  naive time, it is stored as given; ElderLink does not invent an offset.

- evidence references: segment ids are compared as exact, case-sensitive
  strings. They are machine-generated tokens, not user-facing text, so
  normalizing them (e.g. lowercasing) risks silently matching the wrong
  segment.

- missing optional fields: represented as None, never as "" or a guessed
  default. `CareEvent.from_dict` uses dict.get(...) (defaulting to None)
  rather than dict.get(..., "") specifically to preserve this.
"""

from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    """Collapse internal whitespace runs and strip both ends."""
    return _WS_RE.sub(" ", text.strip())


def normalize_event_type_token(raw: str) -> str:
    """Lowercase+trim a raw event-type string before matching it against
    the EventType vocabulary."""
    return raw.strip().lower()


def normalize_subject(raw: str) -> str:
    """Whitespace-only normalization; casing/nicknames are preserved."""
    return normalize_whitespace(raw)
