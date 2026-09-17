# ElderLink

ElderLink turns caregiver voice notes into structured, persistent care context for easier caregiver handoffs.

## Problem

Caregivers communicate critical care information through informal voice notes (WhatsApp, voice memos, phone calls). This information is fragmented, ephemeral, and lost during handoffs — leading to missed medications, duplicated tasks, and care gaps.

## Solution

ElderLink captures voice notes caregivers already send, transcribes them using Amazon Bedrock Voxtral, extracts structured Care Events using AI, validates them for safety, and stores them in a persistent timeline. Caregivers get a reliable "what changed" view at every handoff.

## Core Workflow

1. **Voice Note** — Caregiver records a voice note (existing behavior)
2. **Upload** — Audio stored in S3 (`audio/<note-id>.wav`)
3. **EventBridge** — S3 Object Created event routed to Lambda
4. **Transcribe** — Lambda invokes Bedrock Voxtral (or Mock) for transcription
5. **Store** — Transcript JSON written to S3 (`transcripts/<note-id>.json`)
6. **Extract** — (Future) Bedrock structures transcript into Care Events
7. **Validate** — (Future) Safety logic checks for critical issues
8. **Persist** — (Future) Validated events written to DynamoDB
9. **Surface** — (Future) Timeline, What Changed, and Care Handoff views via API

## Current Deployed Pipeline (Day 1)

```
S3 (audio/) → EventBridge → Lambda → TranscriptionProvider → S3 (transcripts/)
```

| Component | Technology | Status |
|-----------|------------|--------|
| Audio Storage | S3 (private, encrypted, versioned) | ✅ Deployed |
| Event Routing | EventBridge rule (`elderlink-s3-audio-created`) | ✅ Deployed |
| Processing | Lambda (`elderlink-process-audio`, 60s timeout) | ✅ Deployed |
| Transcription | MockTranscriptionProvider (default) | ✅ Working |
| Transcription | VoxtralProvider (`mistral.voxtral-mini-3b-2507`) | ⏳ Pending AWS verification |
| Transcript Output | S3 (`transcripts/<note-id>.json`) | ✅ Working |

**Live Bedrock Voxtral inference is currently pending AWS account verification.**

We are not adding AWS services merely to increase the service count.

## Provider Selection

The pipeline supports two transcription providers via `TRANSCRIPTION_PROVIDER` environment variable:

| Value | Provider | Use Case |
|-------|----------|----------|
| `mock` | `MockTranscriptionProvider` | Default for deployed stack; deterministic local testing |
| `voxtral` | `VoxtralProvider` | Production; requires AWS Bedrock access |

**Default: `mock`** — The deployed stack uses the mock provider because AWS account verification is pending. When verification clears, switch to `voxtral` by updating the Lambda environment variable.

Supported audio formats (must match Bedrock Converse's `AudioFormat` enum): `wav`, `mp3`, `flac`, `ogg`, `m4a`.

## Known Limitations (Day 1)

- **At-least-once delivery**: S3/EventBridge can redeliver the same `Object Created` event. The Lambda guards against this with a cheap `HeadObject` check on the target transcript key before doing any work — if a transcript already exists for that `note_id`, the invocation is a no-op. This is not a distributed lock; a rare race between two concurrent redeliveries could still both pass the check before either writes. Full idempotency (e.g. conditional writes) is out of scope for Day 1.
- **Live Voxtral inference is blocked**: the AWS account is still pending verification for Bedrock model access, so only the `mock` provider has been exercised end-to-end in the deployed stack.

## AWS Services

- **S3** — Audio blob storage (private, encrypted, versioned)
- **Lambda** — Stateless processing functions
- **EventBridge** — Event routing from S3 to Lambda
- **Amazon Bedrock** — Voxtral speech-to-text + LLM-based structured extraction (future)
- **DynamoDB** — Care Event persistence (future)
- **API Gateway** — HTTPS frontend access (future)

## Safety Boundary

ElderLink is **healthcare-adjacent coordination software**. It does **not**:

- Diagnose conditions
- Prescribe medications
- Recommend treatment changes
- Make clinical decisions
- Replace professional medical judgment

It structures information caregivers already communicate. All extracted events are attributed to the caregiver's voice note — ElderLink does not generate medical content.

## Local Development

```bash
# Copy environment template
cp .env.example .env

# Fill in your values (AWS region, bucket name, etc.)

# Test transcription locally with mock provider
python backend/scripts/test_transcription.py --provider mock

# When AWS verification clears, test with Voxtral
# python backend/scripts/test_transcription.py --provider voxtral --audio-file <file.wav>
```

## Project Structure

```
elderlink/
├── README.md
├── .gitignore
├── .env.example
├── frontend/          # React + Vite caregiver UI (Care / Timeline / Handoff), mock CareEvent data
├── backend/
│   ├── core/
│   │   └── transcription/  # Transcription abstraction (Voxtral + Mock)
│   ├── lambdas/
│   │   └── process_audio/  # Lambda handler for audio processing
│   ├── scripts/            # Local test scripts
│   └── tests/              # Unit tests
├── infra/             # CloudFormation (SAM) templates
├── evaluation/        # Prompt eval, accuracy benchmarks (TBD)
├── demo/              # Demo scripts, sample data (TBD)
└── docs/              # Architecture, decisions, runbooks
```

## Deployment

```bash
# Regenerate the Lambda layer content from the canonical source
# (backend/core/transcription/ is the single source of truth; the layer
# directory is generated, not hand-maintained)
./infra/build_layer.sh

# Package (packaged.yaml is a build artifact - not committed, regenerate as needed)
cd infra
aws cloudformation package --template-file template.yaml --s3-bucket elderlink-deploy-artifacts --output-template-file packaged.yaml

# Deploy
aws cloudformation deploy --template-file packaged.yaml --stack-name elderlink-audio-pipeline --capabilities CAPABILITY_IAM --region us-east-1

# Get outputs
aws cloudformation describe-stacks --stack-name elderlink-audio-pipeline --region us-east-1 --query 'Stacks[0].Outputs'
```

boto3/botocore are provided by the Lambda's managed Python 3.11 runtime and are not bundled into the function package.

## Testing the Deployed Pipeline

```bash
# Upload test audio
aws s3 cp elderlink-test.wav s3://<bucket-name>/audio/test-note.wav

# Wait ~10-15 seconds for processing

# Check transcript
aws s3 cp s3://<bucket-name>/transcripts/test-note.json -
```

## Frontend

The caregiver-facing UI (`frontend/`) is a standalone React + Vite app with three views - **Care** (what changed since your last handoff), **Timeline** (longitudinal record), and **Handoff** (what the next caregiver needs to know). It runs entirely on mock `CareEvent` data (`frontend/src/data/mockEvents.ts`) and is not wired to the AWS pipeline above - the backend's real output is a transcript JSON, not yet a structured Care Event, so there is nothing live to connect to until the Day 2 extraction step exists.

```bash
cd frontend
npm install
npm run dev
```

## Hackathon

4-day build. Scope discipline is critical. Each day has a single focused deliverable:

- **Day 1** — Foundation, transcription abstraction (Voxtral + Mock), AWS pipeline deployed with mock provider
- **Day 2** — Bedrock extraction pipeline, DynamoDB schema, switch to Voxtral when verified
- **Day 3** — API, Timeline/What Changed frontend
- **Day 4** — Care Handoff view, demo hardening, evaluation

---

*Built for hackathon — not a production medical device.*