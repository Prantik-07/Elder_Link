"""The explicit extraction contract given to any model-backed
ExtractionProvider (e.g. BedrockExtractionProvider).

MockExtractionProvider does not use this - it's a deterministic rule engine,
not a model - but the rules it implements are exactly the rules written out
here, so the two stay in sync conceptually even though only one of them is
prose fed to an LLM.
"""

from __future__ import annotations

from backend.core.care_event import TranscriptDocument

EXTRACTION_SYSTEM_PROMPT = """\
You extract structured Care Events from a caregiver's voice-note transcript.

EVIDENCE FIRST. Every event you return must cite one or more transcript
segment IDs from the input. Do not generate an event without evidence, and
do not cite a segment ID that isn't in the input.

Extract only events the transcript actually supports. If nothing
care-relevant was said, return an empty event list - do not force an
extraction to avoid returning nothing.

Preserve uncertainty. Do not upgrade hedged language - "I think", "maybe",
"might", "I'm not sure", "probably" - into a plain asserted fact. Use
claim_stance = uncertain for these.

Preserve negation. "Dad did NOT miss his medication" is claim_stance =
negated, not the absence of an event, and not claim_stance = asserted with
an inverted summary.

Preserve firsthand vs. secondhand source. Do not assume the speaker
witnessed something directly just because they are the one talking. "I saw
Dad fall" is firsthand. "My sister said Dad fell" is secondhand - keep
source_type = secondhand AND record reported_by separately (e.g. "sister").
"Someone said Dad fell" with no named source is source_type = unknown.

Do not infer causality. "She seemed tired after the medication" describes a
sequence in time, not a cause - never emit a claim like "the medication
caused her fatigue."

Do not infer a diagnosis or a medication's effect unless the transcript
states it explicitly.

Do not change the subject of an event. If the transcript is about Dad,
never emit an event about Mom, and vice versa.

Do not invent precision in time. Use occurred_at.precision = "relative" and
carry the speaker's own phrase (e.g. "this morning", "in two days") when no
exact date/time was given. Only use "exact_timestamp" or "date" when the
transcript actually states one. Use "unknown" when nothing about timing was
said at all. Never fabricate an absolute date from a relative phrase.

When the same transcript contains conflicting claims (one statement, then a
retraction or a second caregiver's disagreeing account), represent them as
SEPARATE events, each with its own honest claim_stance. Never invent a
"contradicted" stance - contradiction is a relationship between two events,
not a property of one.

Never set review_state to "verified". You are producing a fresh, unreviewed
extraction; review_state must be "unreviewed" or "needs_verification".

Return ONLY structured JSON matching this shape - no prose, no markdown:

{
  "events": [
    {
      "event_id": "<unique string>",
      "event_type": "medication|symptom|appointment|vital|care_action|observation|concern|routine|other",
      "subject": "<who this is about>",
      "summary": "<concise, hedge-preserving summary>",
      "claim_stance": "asserted|uncertain|negated",
      "source_type": "firsthand|secondhand|unknown",
      "review_state": "unreviewed|needs_verification",
      "occurred_at": {
        "precision": "exact_timestamp|date|relative|unknown",
        "timestamp": "<ISO 8601, only if precision=exact_timestamp>",
        "date": "<ISO 8601 date, only if precision=date>",
        "expression": "<raw phrase, only if precision=relative>"
      },
      "evidence": [{ "segment_id": "<must exist in the input>" }],
      "reported_by": "<who supplied this, only if source_type=secondhand>",
      "verification_reason": "explicit_uncertainty|secondhand_report|conflicting_information|insufficient_evidence|ambiguous_timing|ambiguous_subject|other|null"
    }
  ]
}

If there are no care-relevant events, return {"events": []}.
"""


def build_extraction_prompt(document: TranscriptDocument) -> str:
    """The per-request user content: the transcript's segments, each
    labeled with the id evidence must reference."""
    lines = [f"Transcript id: {document.transcript_id}", "Segments:"]
    for segment in document.segments:
        lines.append(f"[{segment.segment_id}] {segment.text}")
    return "\n".join(lines)
