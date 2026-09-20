"""Canonical Day 2 transcript representation, and an adapter from Day 1's
flat transcript JSON.

This gives a Care Event's evidence something stable to point at: a document
made of segments with ids, independent of which provider produced the
transcript or how it was segmented. Day 1's S3/Lambda pipeline is untouched
- the adapter only interprets its output.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TranscriptSegment:
    segment_id: str
    text: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class TranscriptDocument:
    transcript_id: str
    full_text: str
    segments: list[TranscriptSegment] = field(default_factory=list)

    @property
    def segment_ids(self) -> set[str]:
        return {s.segment_id for s in self.segments}

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptDocument":
        required = ("transcript_id", "full_text", "segments")
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"TranscriptDocument missing required fields: {missing}")

        segments = [
            TranscriptSegment(
                segment_id=s["segment_id"],
                text=s["text"],
                start_time=s.get("start_time"),
                end_time=s.get("end_time"),
            )
            for s in data["segments"]
        ]
        ids = [s.segment_id for s in segments]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(
                f"Duplicate segment_id(s) in transcript '{data['transcript_id']}': {dupes}"
            )

        return cls(transcript_id=data["transcript_id"], full_text=data["full_text"], segments=segments)


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def stable_segment_id(transcript_id: str, index: int, text: str) -> str:
    """Deterministic id from the transcript id, position, and a short
    content hash - re-running the adapter on the same Day 1 transcript
    always produces the same segment ids, which the evidence contract
    depends on."""
    digest = hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:8]
    return f"{transcript_id}-seg{index}-{digest}"


def from_day1_transcript(note_id: str, transcript_text: str) -> TranscriptDocument:
    """Adapter from Day 1's flat transcript JSON (a single `transcript`
    string, no native segmentation or timestamps) to the canonical
    TranscriptDocument.

    Segmentation is a best-effort sentence split, since that's all a plain
    string affords. start_time/end_time stay null until a transcription
    provider supplies real ones - the CareEvent evidence interface doesn't
    need to change when that happens.
    """
    text = transcript_text.strip()
    if not text:
        return TranscriptDocument(transcript_id=note_id, full_text="", segments=[])

    raw_sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    segments = [
        TranscriptSegment(segment_id=stable_segment_id(note_id, i, s), text=s)
        for i, s in enumerate(raw_sentences)
    ]
    return TranscriptDocument(transcript_id=note_id, full_text=text, segments=segments)


def from_stored_transcript(
    note_id: str, transcript_text: str, segments: Optional[list] = None
) -> TranscriptDocument:
    """Build the canonical document from a stored transcript JSON. When the
    provider supplied real utterance segments (Deepgram), use them with their
    real timings (null stays null); otherwise, or if they are malformed, fall
    back to the Day 1 sentence-split adapter unchanged."""
    if isinstance(segments, list) and segments:
        try:
            built = []
            for i, s in enumerate(segments):
                text = str(s["text"]).strip()
                if not text:
                    continue
                built.append(
                    TranscriptSegment(
                        segment_id=stable_segment_id(note_id, len(built), text),
                        text=text,
                        start_time=s.get("start_time"),
                        end_time=s.get("end_time"),
                    )
                )
            if built:
                return TranscriptDocument(
                    transcript_id=note_id,
                    full_text=transcript_text.strip(),
                    segments=built,
                )
        except (KeyError, TypeError, AttributeError):
            pass
    return from_day1_transcript(note_id, transcript_text)
