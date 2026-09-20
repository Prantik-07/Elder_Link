# Hackathon live-demo transcripts

These are pre-written "voice note" transcripts to push through the REAL
deployed pipeline (S3 -> EventBridge -> ExtractEvents Lambda -> DynamoDB ->
GetTimeline API -> frontend) during the live demo, since real Bedrock
transcription/extraction is not available on this AWS account (confirmed
via direct API test - every model invocation returns
`ValidationException: Operation not allowed`).

Extraction runs on MockExtractionProvider (a deterministic keyword-based
rule engine - see backend/core/extraction/mock.py), so transcript wording
must hit its keyword list to actually produce events. Each file below has
already been chosen/tested to do so.

## How to run one live during the pitch

```bash
BUCKET=elderlink-audio-pipeline-audiobucket-d4embqdcnuoi
aws s3 cp demo/note-2-hero.json s3://$BUCKET/transcripts/note-2-hero.json
```

Wait ~3-5 seconds (extraction Lambda runs), then click the refresh icon
in the header. The new event(s) appear at the top of Care Overview,
Timeline, and Handoff - all reading from the same real API.

## Suggested order

1. `note-1-opening.json` - simple, clean, one medication event. Good for
   "here's what a normal update looks like."
2. `note-2-hero.json` - the centerpiece. ONE voice note, FOUR claims. All
   four show the SAME "Needs verification" badge at a glance - by design,
   extraction never auto-resolves anything - but clicking into each one
   shows a DIFFERENT specific reason (see EvidencePanel's "Why
   verification is required" box / the API's `verificationReason` field):
     - "Dad took his medication this morning." -> asserted, firsthand ->
       needs_verification, no specific reason (a normal update, still
       unreviewed - "unreviewed" is never treated as "confirmed")
     - "My sister said Dad fell yesterday evening." -> secondhand ->
       reason: "secondhand report"
     - "Dad did not miss his appointment on Friday." -> a NEGATED claim -
       captured as real information in its own right, not silence
     - "I think Dad might have low energy today." -> reason: "explicit
       uncertainty"
   The pitch line: "One recording, four claims - the badge tells you at a
   glance that none of these are confirmed yet, and clicking in tells you
   exactly why each one needs a human to look." (Note: the frontend's
   separate "Uncertain" status only ever appears after a caregiver
   explicitly clicks "Keep Uncertain" on a card - that's a human review
   decision, never something extraction assigns automatically. If you want
   to show that live, click into the hedged claim and press "Keep
   Uncertain" - just know that action is local-only for now, per Phase 7's
   documented limitations, and won't survive a page refresh.)
3. `note-3-followup.json` - a verified-feeling appointment note, to close
   the story on the Handoff page.

All land under the shared demo recipient `demo-dad`, so they all show up
together in one longitudinal timeline - the whole point of Phase 7's
identity fallback.
