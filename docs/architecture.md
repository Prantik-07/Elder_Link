# ElderLink Architecture

## System Overview

### Full Intended Pipeline (Future)

```
Browser → S3 → Lambda → Amazon Bedrock Voxtral → Transcript → Bedrock Extraction → Validation → DynamoDB → API Gateway → Frontend
```

### Currently Deployed (Day 1)

```
S3 (audio/) → EventBridge → Lambda → TranscriptionProvider (Mock/Voxtral) → S3 (transcripts/)
```

## Service Roles

| Service | Role |
|---------|------|
| **S3** | Durable, private, encrypted storage for caregiver voice note audio files. Uploads are presigned; no public access. Single bucket with `audio/` and `transcripts/` prefixes. |
| **EventBridge** | Routes S3 `Object Created` events (filtered to `audio/` prefix) to Lambda. |
| **Lambda** | Stateless processor: downloads audio, invokes transcription provider, writes transcript JSON to `transcripts/`. |
| **Amazon Bedrock Voxtral** | Speech-to-text transcription using `mistral.voxtral-mini-3b-2507`. **Currently blocked by AWS account verification.** |
| **MockTranscriptionProvider** | Deterministic provider returning fixed Hindi/English transcript for infrastructure testing. **Currently active in deployed stack.** |
| **Amazon Bedrock Extraction** | (Future) LLM-based structured extraction. Transforms raw transcript into typed Care Events. |
| **Validation** | (Future) Deterministic safety checks: required fields, enum values, dose ranges, urgency flags, no-diagnosis guardrails. |
| **DynamoDB** | (Future) Single-table design for Care Events. |
| **API Gateway** | (Future) HTTPS frontend access. |
| **Frontend** | (Future) Read-only React/Next.js app. |

**Live Bedrock inference is currently pending AWS account verification.**

## Data Flow (Deployed)

1. Caregiver uploads voice note to `s3://<bucket>/audio/<note-id>.wav` (via presigned URL)
2. S3 emits `Object Created` event → EventBridge (EventBridge notifications enabled on bucket)
3. EventBridge rule `elderlink-s3-audio-created` matches `audio/` prefix → invokes Lambda `elderlink-process-audio`
4. Lambda: `GetObject` audio from S3 → determines format from extension
5. Lambda: calls configured `TranscriptionProvider.transcribe(audio_bytes, format)`
6. Provider returns `TranscriptionResult` (success/failure with transcript/error)
7. Lambda: `PutObject` transcript JSON to `s3://<bucket>/transcripts/<note-id>.json`

### Transcript JSON Schema

```json
{
  "note_id": "string",
  "source_audio_key": "string",
  "provider": "mock|voxtral",
  "model": "string",
  "status": "completed|failed",
  "transcript": "string",
  "processed_at": "ISO8601 UTC timestamp",
  "error": "string|null"
}
```

## Provider Selection

| Environment Variable | Value | Provider |
|---------------------|-------|----------|
| `TRANSCRIPTION_PROVIDER` | `mock` | `MockTranscriptionProvider` (default, works without Bedrock) |
| `TRANSCRIPTION_PROVIDER` | `voxtral` | `VoxtralProvider` (requires Bedrock access) |

Default in deployed stack: `mock`

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
- Amazon Transcribe (replaced by Bedrock Voxtral for simpler pipeline)

## Region Selection

Single region: **us-east-1** — supports all required services (S3, Lambda, EventBridge, Bedrock, DynamoDB) with lowest latency for US-based hackathon demo.

## Cost Controls

- S3: Lifecycle rule → delete audio after 30 days
- Bedrock Voxtral: Pay-per-inference, only on upload
- Bedrock Extraction: Haiku model (~$0.25/1M input tokens), minimal usage
- DynamoDB: On-demand, < 100 reads/writes/day during hackathon
- Lambda: 128 MB, 60s timeout, < 1M invocations/month free tier
- API Gateway: 1M requests/month free tier

No persistent compute. No provisioned throughput. No NAT Gateways.

## Transcription Abstraction

The transcription layer is isolated behind a `TranscriptionProvider` interface:

- **VoxtralProvider**: Production implementation using `boto3` + Bedrock Runtime `converse` API
- **MockTranscriptionProvider**: Deterministic local development provider

This allows the rest of the application to be developed and tested without live AWS access.

## IAM Least Privilege (Deployed)

Lambda role `elderlink-audio-pipeline-ProcessAudioRole-*` has only:

- `s3:GetObject` on `arn:aws:s3:::<bucket>/audio/*`
- `s3:GetObject` + `s3:PutObject` on `arn:aws:s3:::<bucket>/transcripts/*` (GetObject is needed for the idempotency `HeadObject` check described below)
- `bedrock:InvokeModel` on `arn:aws:bedrock:us-east-1::foundation-model/mistral.voxtral-mini-3b-2507`
- `AWSLambdaBasicExecutionRole` (CloudWatch Logs)

No DynamoDB, no S3 wildcard, no AdministratorAccess.

## Day 1 Hardening Notes

A post-implementation audit of the initial Day 1 build found and fixed two correctness bugs before finalizing:

1. **Duplicate EventBridge trigger.** `infra/template.yaml` originally wired the S3→Lambda trigger two ways at once: an explicit `AWS::Events::Rule` (`elderlink-s3-audio-created`) *and* a SAM `Events:` block on the function, which auto-generates its own rule + permission with an identical pattern. Both were live in the deployed stack simultaneously, so every upload invoked the Lambda twice (confirmed via CloudWatch: 2 invocations, 2 log streams, for 1 S3 PutObject). Fix: removed the SAM `Events:` block; the explicit rule is now the only trigger.
2. **Invalid Voxtral audio format.** `VoxtralProvider.SUPPORTED_FORMATS` included `"aiff"`, which is not part of Bedrock Converse's `AudioFormat` enum (verified against the installed `botocore` service model) and would have failed against the real API. `"m4a"` — which *is* valid — was accepted by the Lambda handler's extension allowlist but missing from the provider's format set. Fix: dropped `aiff`, added `m4a`, so the handler and provider now agree on exactly the formats Bedrock actually supports.

As a defense-in-depth measure (not a fix for a specific observed bug), the Lambda now also checks whether a transcript already exists for a given `note_id` before doing any transcription work, since S3/EventBridge delivery is at-least-once by design (see README "Known Limitations").

## Deployed Resources

| Resource | Name/ARN |
|----------|----------|
| S3 Bucket | `elderlink-audio-pipeline-audiobucket-d4embqdcnuoi` |
| Lambda Function | `elderlink-process-audio` |
| Lambda Layer | `arn:aws:lambda:us-east-1:856447616271:layer:elderlink-transcription-core:2` |
| EventBridge Rule | `elderlink-s3-audio-created` |
| IAM Role | `elderlink-audio-pipeline-ProcessAudioRole-*` |
| CloudFormation Stack | `elderlink-audio-pipeline` |

## Deployment Commands

```bash
# Regenerate the layer content from the canonical source (backend/core/transcription/)
./infra/build_layer.sh

# Package
cd infra
aws cloudformation package --template-file template.yaml --s3-bucket elderlink-deploy-artifacts --output-template-file packaged.yaml

# Deploy
aws cloudformation deploy --template-file packaged.yaml --stack-name elderlink-audio-pipeline --capabilities CAPABILITY_IAM --region us-east-1

# Get outputs
aws cloudformation describe-stacks --stack-name elderlink-audio-pipeline --region us-east-1 --query 'Stacks[0].Outputs'
```

`infra/packaged.yaml` is build output (references a specific S3 deploy bucket + object hashes) and is gitignored, not committed.

## End-to-End Test (Mock Mode)

```bash
# Upload test audio
aws s3 cp elderlink-test.wav s3://elderlink-audio-pipeline-audiobucket-d4embqdcnuoi/audio/test-note.wav

# Wait ~15 seconds

# Verify transcript
aws s3 cp s3://elderlink-audio-pipeline-audiobucket-d4embqdcnuoi/transcripts/test-note.json -
```

Expected output:
```json
{
  "note_id": "test-note",
  "source_audio_key": "audio/test-note.wav",
  "provider": "mock",
  "model": "mock-transcriber-v1",
  "status": "completed",
  "transcript": "Papa ne subah wali medicine le li thi, lekin lunch bahut kam khaya aur shaam ko ghutne mein phir dard tha.",
  "processed_at": "2026-09-17T12:50:46.496801Z",
  "error": null
}
```