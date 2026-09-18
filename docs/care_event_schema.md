# The Care Event Schema

**Status:** Phase 2 (Day 2), updated in Phase 4. This is the canonical,
frozen contract for extraction. It lives in code at `backend/core/care_event/`
— this document explains the *why*; the code is the source of truth for the
*what*. See "Phase 4: evidence + verification hardening" at the bottom for
what changed after extraction (`backend/core/extraction/`) was built.

There is exactly one `CareEvent` definition in this codebase. The evaluation
harness imports it rather than declaring its own (see `evaluation/models.py`).
Any future extractor or backend API should do the same. Adapters to other
representations — the frontend's `CareEventStatus`, Day 1's flat transcript
JSON — are expected and fine; a second competing `CareEvent` dataclass is not.

## What a Care Event is

A `CareEvent` is one claim, extracted from a caregiver's voice note, about
something that may be relevant to an elder's care: a medication taken or
missed, a symptom, an appointment, a fall, a routine detail. It is not a
verified fact about the world — it is a structured record of *what was
said*, with enough context to judge how much to trust it.

Every `CareEvent` must cite at least one piece of evidence (a transcript
segment) that supports it. An event with no valid evidence cannot become
trusted persistent context — see "What evidence means" below.

## Why three separate fields instead of one status

Earlier drafts of this schema used a single field to mean "how much should
we trust this." That collapsed three genuinely independent questions into
one value, which made some real caregiver statements impossible to
represent correctly. The schema now asks each question separately:

| Field | Question it answers |
|---|---|
| `claim_stance` | What is being claimed — that something happened, that it might have, or that it did **not** happen? |
| `source_type` | Did the note's speaker witness this directly, or are they relaying someone else's account? |
| `review_state` | Has anyone actually checked this against reality yet? |

They vary independently. A secondhand report can be confidently asserted
*or* hedged; a firsthand account can be certain *or* uncertain; nothing
about how a claim is worded says anything about whether it's been reviewed.

### What `claim_stance` means

```
asserted   - stated as having happened / being true, without hedging.
uncertain  - hedged: "I think", "may have", vague or ambiguous phrasing.
negated    - stated as NOT having happened / not being true.
```

`negated` is a real, positive claim in its own right — "he did **not** miss
his medication" is information worth keeping, not the absence of an event.
Skipping it and producing zero events for a negative statement would throw
away a caregiver's explicit reassurance.

**"Contradicted" is deliberately not a value here.** Contradiction is a
*relationship between two claims* (one caregiver says X, another says not-X,
or the same caregiver retracts themselves mid-note) — it is not a property
of a single claim. When a transcript contains conflicting statements, that
is represented as **two separate `CareEvent`s**, each with its own honest
`claim_stance`, not as one event carrying a made-up "contradicted" stance.
See Example 3 below.

### What `source_type` means

```
firsthand  - the note's own speaker witnessed this directly.
secondhand - the speaker is relaying someone else's account.
unknown    - can't be determined from the transcript.
```

Orthogonal to `claim_stance`. `reported_by` (a free-text field, e.g.
`"sister"`) carries *who* said it, kept separate from `source_type` (*was
it witnessed directly*) so the two can be judged and compared independently
— losing the name of the reporter is a smaller problem than losing the fact
that something is secondhand at all.

### What `review_state` means

```
unreviewed         - nothing has checked this against reality yet.
verified           - a real review step confirmed it.
needs_verification - flagged as needing that check.
```

**Extraction must never produce `review_state = verified`.** A transcript
being clear, or an event having strong supporting evidence, proves what was
*reported* — not that the underlying real-world event is objectively true.
`verified` is reserved for an actual human/clinical review step that this
schema doesn't perform itself. An extractor that sets `verified` on its own
output has confused "I transcribed this cleanly" with "I confirmed this
happened," which is exactly the failure mode this schema exists to prevent.

### What evidence means

```
evidence: [{ segment_id, start_time?, end_time? }]
```

Each `Evidence` entry points at a segment of the canonical
`TranscriptDocument` (see below) that supports the claim. Rules:

1. A `CareEvent` must have at least one evidence entry — zero evidence means
   the event cannot become trusted persistent context, no matter how
   plausible its summary reads.
2. Every evidence segment must actually exist in the transcript it claims to
   come from.
3. The segment's **text is not duplicated** into the `Evidence` object. The
   `TranscriptDocument`'s segment text is the one authoritative source;
   storing a second copy of it on the event would let the two drift out of
   sync over time. Look the text up by `segment_id` via `evidence_text()`
   when you need to display or re-check it.

### Why these are separate

Collapsing any two of these into one field loses real information a
caregiver actually gave you. Concretely:

> "My sister thinks Dad may have missed his medication."

This is `claim_stance = uncertain` **and** `source_type = secondhand` at the
same time — the sister is relaying her *own* hedge. A schema that can only
express one axis would have to either drop the hedge (dangerous: treats a
guess as a fact) or drop the attribution (also dangerous: treats a
secondhand rumor as something the caregiver witnessed). Keeping them
separate lets both survive.

## Examples

**1. Plain fact, firsthand.**
> "Dad took his blood pressure medicine at 8am."

```
event_type: medication, subject: Dad
claim_stance: asserted, source_type: firsthand, review_state: unreviewed
occurred_at: { precision: relative, expression: "8am" }
evidence: [{ segment_id: s1 }]
```

**2. Uncertain and secondhand, together.**
> "My sister thinks Dad may have missed his medication this morning."

```
event_type: medication, subject: Dad, reported_by: sister
claim_stance: uncertain, source_type: secondhand
review_state: needs_verification, verification_reason: secondhand_report
occurred_at: { precision: relative, expression: "this morning" }
```

**3. Conflicting information — two events, not one "contradicted" stance.**
> "Dad took his medicine at 8am. Actually wait, I'm not sure he did take it."

```
Event 1: claim_stance: asserted,  summary: "Dad took his medicine at 8am",
         evidence: [s1]
Event 2: claim_stance: uncertain, summary: "Speaker is no longer sure Dad
         took his medicine, retracting the earlier claim",
         review_state: needs_verification,
         verification_reason: conflicting_information, evidence: [s2]
```

The conflict *between* Event 1 and Event 2 is what a caregiver reading the
timeline needs to notice — that relationship lives in there being two
events on the same subject/type with disagreeing stances, not inside either
event individually.

## Event type taxonomy

A small, controlled vocabulary — reviewed against all 16 Phase 1 golden
cases, none of which needed a type outside this list:

| Type | Use for | Not for |
|---|---|---|
| `medication` | A medication taken, given, skipped, or discussed (dose, schedule, refill). | A general symptom the medication relates to — use `symptom`/`observation`. |
| `symptom` | A specific, named physical or mental symptom (pain, nausea, dizziness, cough). | A vague status impression with no named symptom — use `observation`. |
| `appointment` | A scheduled or discussed healthcare visit. | A recurring routine (see `routine`). |
| `vital` | A measured/reported vital sign or reading (blood pressure, weight, glucose). | A subjective sense of how someone seems — use `observation`. |
| `care_action` | A concrete caregiving action performed (bathing, meal prep, mobility help, wound care) that isn't itself a medication or vital. | Administering medication — use `medication`. |
| `observation` | A general behavioral/status impression (mood, energy, appetite, sleep) without a named symptom. | A specific diagnosable symptom — use `symptom`. |
| `concern` | A safety-relevant worry or incident (fall, confusion, wandering, injury) that may need escalation. | Routine status updates — use `observation`. |
| `routine` | Information about a regular schedule/pattern, not one specific occurrence. | A single dated event — use the type it actually is. |
| `other` | Care-relevant content that genuinely doesn't fit any type above. | A convenient default when unsure — pick the closest real category instead; `other` should be rare, and when used, `verification_reason` or the summary should say why. |

## Temporal model

Care notes say things like "today," "this morning," "in two days" far more
often than they give a real timestamp. Forcing every event into an ISO
timestamp would fabricate precision nobody actually has. Instead,
`occurred_at` is a required, structured `TemporalInfo` with an explicit
precision level:

```
exact_timestamp - a specific date+time is known.       (timestamp set)
date            - a specific calendar date is known,    (date set)
                  time of day isn't.
relative        - an approximate/relative phrase,       (expression set)
                  not resolved to a date.
unknown         - nothing usable was said about timing   (nothing set)
                  at all.
```

Only the one field matching `precision` may be set; the others must be
`None` (enforced in `validation.py`). `occurred_at` is never itself `None`
— "we don't know when" is the explicit state `{ precision: unknown }`,
not an ambiguous missing value.

## Validation

`validate_care_event(event, document)` returns a list of error strings
(empty = valid). It rejects:

- an empty/whitespace-only `event_id`
- an empty `subject` or `summary`
- an empty evidence list
- an evidence entry whose `segment_id` doesn't exist in the transcript
- a `TemporalInfo` whose populated field(s) don't match its `precision`

Unknown enum values (`event_type`, `claim_stance`, `source_type`,
`review_state`, `verification_reason`) are rejected earlier, at
construction — `CareEvent.from_dict` calls `EnumType(value)`, which raises
`ValueError` for anything outside the controlled vocabulary.

It deliberately does **not** reject any `claim_stance`/`source_type`
combination (all six are legitimate, including `negated + secondhand`: "my
sister said Dad did NOT miss his medication"), and does not require
`reported_by` whenever `source_type` is secondhand (a caregiver may
legitimately not know exactly who told them). Rejecting either would throw
away valid real-world uncertainty instead of representing it.

## Normalization

Applied explicitly by callers building a `CareEvent` from raw text (never
silently inside `CareEvent.from_dict`, which stays strict so test/golden
data round-trips exactly) — see `normalization.py`:

- **Whitespace**: collapse internal runs to a single space, trim ends.
  Applied to `subject` and `summary` only.
- **Event types**: lowercase + trim the raw token before matching against
  the vocabulary. An unrecognized token is still rejected, never silently
  coerced to `other`.
- **Subject naming**: whitespace-only. Casing and nicknames ("Dad", "mom",
  "Grandpa Joe") are preserved — they carry caregiver-specific meaning.
- **Timestamps/dates**: must already be valid ISO 8601, never guessed,
  completed, or shifted to a different timezone.
- **Evidence references**: `segment_id`s are compared as exact,
  case-sensitive strings — they're machine-generated tokens, not user text.
- **Missing optional fields**: represented as `None`, never `""` or a
  guessed default.

## Frontend compatibility

The frontend's `CareEventStatus` (`verified` / `needs_verification` /
`uncertain`, in `frontend/src/data/types.ts`) is a **presentation**
concept, not the backend's truth model, and this schema does not try to
replace it. The frontend was not touched in Phase 2. A future integration
layer can derive a `CareEventStatus` from the canonical fields (roughly:
`review_state == verified` → `verified`; `claim_stance == uncertain` or
`review_state == needs_verification` → `uncertain`/`needs_verification`),
but that mapping is a one-directional adapter, not a reason to fold
`review_state`/`claim_stance` back into one field on the backend.

## Phase 4: evidence + verification hardening

Phase 4 formalized the boundary between untrusted extraction output and
trusted `CareEvent`s. Full rationale lives in the modules named below;
this is a short index, not a duplicate of it.

**`verification_reason` is now structured**, not a bare code:
`VerificationReason{code: VerificationReasonCode, detail: Optional[str]}`.
`code` is the only thing any code should branch on; `detail` is a
human-readable elaboration for a reviewer and is explicitly never treated
as evidence of anything — an LLM's explanation of *why* it thinks something
is uncertain is not proof the underlying claim is true or false.
`validate_care_event` now rejects any event with
`review_state = needs_verification` and no `verification_reason` — see
`backend/core/care_event/validation.py`.

**The extraction review policy** (`backend/core/extraction/review_policy.py`,
`derive_review_state`) is the *sole* authority for `review_state` and
`verification_reason` on anything that comes out of the extraction
pipeline — a candidate's own proposed values for these two fields are
always discarded and recomputed, never trusted, even if they happened to
be correct. Policy, first match wins: `claim_stance == uncertain` →
`needs_verification`/`explicit_uncertainty`; `source_type == secondhand` →
`needs_verification`/`secondhand_report`; conflicts with a sibling event →
`needs_verification`/`conflicting_information`; evidence too thin (see the
module for the exact heuristic) → `needs_verification`/
`insufficient_evidence`; otherwise → `unreviewed`/none. **"Unreviewed" is
not "true"** — it only means no rule above fired and no human has reviewed
it yet, never that the claim is confirmed. `review_state = verified` is
never produced by this policy, or by anything in the extraction pipeline —
`backend/core/extraction/pipeline.py` rejects any candidate that dares
propose it outright, before the policy even runs.

**The frontend mapping** (`backend/core/care_event/frontend_adapter.py`,
`to_frontend_status`) is the one-directional, documented adapter from the
three canonical fields to the frontend's existing `CareEventStatus`. It
never exposes `verified` unless `review_state` is actually `VERIFIED` (which
extraction can never produce), and treats a plain unreviewed
asserted/firsthand event as `needs_verification` rather than something that
reads as more settled than the backend actually knows.

**Deterministic event identity** (`backend/core/extraction/identity.py`,
`deterministic_event_id`) makes repeated extraction of the same transcript
idempotent at the logical event level *before* any persistence layer
exists: `id = hash(extraction_version : transcript_id : within_transcript_index)`,
never a random UUID. Same transcript, same extraction version, same index
→ same id, every time, from any provider.

**Conflicting claims stay separate events** — `claim_stance = contradicted`
still does not exist (see the `ClaimStance` section above). What Phase 4
added is a lightweight, same-batch heuristic
(`backend/core/extraction/conflicts.py`, `find_conflicting_event_ids`) that
flags two sibling events as conflicting when they share `event_type` and
`subject` but disagree in `claim_stance` — used only to route both into
`needs_verification` via the review policy above, not to merge, resolve, or
pick a winner between them. Longitudinal conflict resolution (comparing
against a *prior* extraction, not just siblings in one batch) remains
future work.
