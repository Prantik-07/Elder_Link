# ElderLink

ElderLink turns caregiver voice notes into structured, persistent care context for easier caregiver handoffs.

## Problem

Caregivers communicate critical care information through informal voice notes (WhatsApp, voice memos, phone calls). This information is fragmented, ephemeral, and lost during handoffs — leading to missed medications, duplicated tasks, and care gaps.

## Solution

ElderLink captures voice notes caregivers already send, transcribes them, extracts structured Care Events using AI, validates them for safety, and stores them in a persistent timeline. Caregivers get a reliable "what changed" view at every handoff.

## Core Workflow

1. **Voice Note** — Caregiver records a voice note (existing behavior)
2. **Upload** — Audio stored in S3
3. **Transcribe** — Amazon Transcribe converts audio to text
4. **Extract** — Amazon Bedrock structures the transcript into Care Events
5. **Validate** — Safety logic checks for critical issues (medication conflicts, urgency flags)
6. **Persist** — Validated events written to DynamoDB
7. **Surface** — Timeline, What Changed, and Care Handoff views via API

## MVP Scope (4-Day Hackathon)

- Voice note upload → S3
- Automatic transcription via Transcribe
- Bedrock-powered structured extraction (medications, vitals, tasks, observations, alerts)
- Safety validation (no diagnosis, no treatment recommendations)
- DynamoDB persistence
- Read-only timeline API
- Simple frontend for viewing handoff summary

## Architecture

```
Browser → S3 → Amazon Transcribe → EventBridge → Lambda → Amazon Bedrock → Validation → DynamoDB → API Gateway → Frontend
```

Each service has a single, well-defined role:

| Service | Role |
|---------|------|
| S3 | Durable, private storage for audio uploads |
| Transcribe | Speech-to-text conversion |
| EventBridge | Decouples transcription completion from downstream processing |
| Lambda | Orchestrates extraction, validation, and persistence |
| Bedrock | Structured information extraction from transcripts |
| DynamoDB | Low-latency, scalable storage for Care Events |
| API Gateway | Secure HTTP frontend access |

We are not adding AWS services merely to increase the service count.

## AWS Services

- **S3** — Audio blob storage (private, encrypted)
- **Lambda** — Stateless processing functions
- **API Gateway** — HTTPS frontend access
- **EventBridge** — Event routing between Transcribe and Lambda
- **DynamoDB** — Care Event persistence
- **Amazon Transcribe** — Speech-to-text
- **Amazon Bedrock** — LLM-based structured extraction

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
# Then run backend/frontend dev commands (TBD)
```

## Project Structure

```
elderlink/
├── README.md
├── .gitignore
├── .env.example
├── frontend/          # React/Next.js frontend (TBD)
├── backend/           # Lambda functions, API logic (TBD)
├── infra/             # IaC (CloudFormation/CDK/Terraform) (TBD)
├── evaluation/        # Prompt eval, accuracy benchmarks (TBD)
├── demo/              # Demo scripts, sample data (TBD)
└── docs/              # Architecture, decisions, runbooks
```

## Hackathon

4-day build. Scope discipline is critical. Each day has a single focused deliverable:

- **Day 1** — Foundation, S3, Transcribe trigger, Bedrock access verified
- **Day 2** — Extraction pipeline, validation, DynamoDB schema
- **Day 3** — API, Timeline/What Changed frontend
- **Day 4** — Care Handoff view, demo hardening, evaluation

---

*Built for hackathon — not a production medical device.*