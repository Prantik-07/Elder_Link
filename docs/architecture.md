# ElderLink Architecture

## System Overview

```
Browser → S3 → Amazon Transcribe → EventBridge → Lambda → Amazon Bedrock → Validation → DynamoDB → API Gateway → Frontend
```

## Service Roles

| Service | Role |
|---------|------|
| **S3** | Durable, private, encrypted storage for caregiver voice note audio files. Uploads are presigned; no public access. |
| **Amazon Transcribe** | Converts uploaded audio to timestamped transcripts. Triggered via S3 event → EventBridge → Transcribe job. |
| **EventBridge** | Decouples Transcribe completion from downstream processing. Routes `Transcribe Job State Change` events to Lambda. |
| **Lambda** | Stateless orchestrator: fetches transcript, calls Bedrock for structured extraction, runs safety validation, writes Care Events to DynamoDB. |
| **Amazon Bedrock** | LLM-based structured extraction. Transforms raw transcript into typed Care Events (medications, vitals, tasks, observations, alerts). |
| **Validation** | Deterministic safety checks: required fields, enum values, dose ranges, urgency flags, no-diagnosis guardrails. |
| **DynamoDB** | Single-table design for Care Events. Partition key: `care_recipient_id`, sort key: `event_timestamp`. Low-latency reads for handoff views. |
| **API Gateway** | HTTPS frontend access. REST endpoints for timeline, what-changed, and handoff summary. Auth via API key / Cognito (TBD). |
| **Frontend** | Read-only React/Next.js app. Timeline view, What Changed diff, Care Handoff printable summary. |

## Data Flow

1. Caregiver records voice note in frontend → presigned S3 PUT
2. S3 `ObjectCreated` → EventBridge → `StartTranscriptionJob`
3. Transcribe completes → `Transcribe Job State Change` → EventBridge → Lambda
4. Lambda: `GetTranscriptionJob` → download transcript JSON
5. Lambda: invoke Bedrock with transcript + extraction prompt → structured JSON
6. Lambda: validate extraction output → reject/flag unsafe content
7. Lambda: `PutItem` Care Events to DynamoDB
8. Frontend: `GET /timeline`, `GET /handoff` → API Gateway → Lambda → DynamoDB → JSON

## Safety Guardrails

- **No diagnosis**: Extraction prompt explicitly forbids diagnostic language
- **No treatment recommendations**: Output schema excludes treatment fields
- **Attribution**: Every event carries `source: "caregiver_voice_note"` and `transcript_span`
- **Human-in-the-loop**: Flagged events require caregiver confirmation before handoff inclusion

## Non-Goals (This Phase)

We are not adding AWS services merely to increase the service count. The following are explicitly out of scope for MVP:

- Step Functions (orchestration handled by Lambda)
- OpenSearch / RAG (no semantic search needed for handoff)
- SNS / SES / WhatsApp (notifications are stretch)
- Cognito (auth deferred to post-hackathon)
- CloudFront (API Gateway edge-optimized is sufficient)

## Region Selection

Single region: **us-east-1** — supports all required services (S3, Lambda, API Gateway, EventBridge, DynamoDB, Transcribe, Bedrock) with lowest latency for US-based hackathon demo.

## Cost Controls

- S3: Lifecycle rule → delete audio after 30 days
- Transcribe: Pay-per-minute, only on upload
- Bedrock: Haiku model (~$0.25/1M input tokens), minimal usage
- DynamoDB: On-demand, < 100 reads/writes/day during hackathon
- Lambda: 128 MB, < 1M invocations/month free tier
- API Gateway: 1M requests/month free tier

No persistent compute. No provisioned throughput. No NAT Gateways.