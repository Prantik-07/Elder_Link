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
├── frontend/          # React/Next.js frontend (TBD)
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
# Package
cd infra
aws cloudformation package --template-file template.yaml --s3-bucket elderlink-deploy-artifacts --output-template-file packaged.yaml

# Deploy
aws cloudformation deploy --template-file packaged.yaml --stack-name elderlink-audio-pipeline --capabilities CAPABILITY_IAM --region us-east-1

# Get outputs
aws cloudformation describe-stacks --stack-name elderlink-audio-pipeline --region us-east-1 --query 'Stacks[0].Outputs'
```

## Testing the Deployed Pipeline

```bash
# Upload test audio
aws s3 cp elderlink-test.wav s3://<bucket-name>/audio/test-note.wav

# Wait ~10-15 seconds for processing

# Check transcript
aws s3 cp s3://<bucket-name>/transcripts/test-note.json -
```

## Hackathon

4-day build. Scope discipline is critical. Each day has a single focused deliverable:

- **Day 1** — Foundation, transcription abstraction (Voxtral + Mock), AWS pipeline deployed with mock provider
- **Day 2** — Bedrock extraction pipeline, DynamoDB schema, switch to Voxtral when verified
- **Day 3** — API, Timeline/What Changed frontend
- **Day 4** — Care Handoff view, demo hardening, evaluation

---

*Built for hackathon — not a production medical device.*