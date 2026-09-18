"""Bedrock-backed extraction.

This mirrors backend.core.transcription.voxtral.VoxtralProvider's honesty
pattern: the integration is real (a genuine bedrock-runtime Converse call
with the extraction contract from prompt.py), but Bedrock model access for
this AWS account is still pending verification, the same blocker Day 1's
Voxtral transcription provider is under. This provider has not been
exercised against a live model and this module makes no claim that it has.

MockExtractionProvider remains the only extraction path actually verified
to work end-to-end. Use --provider mock for all development and testing
until Bedrock access is confirmed.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from backend.core.care_event import TranscriptDocument

from .prompt import EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt
from .service import ExtractionProvider
from .types import ExtractionErrorKind, ExtractionResult


class BedrockExtractionProvider(ExtractionProvider):
    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None):
        self._model_id = model_id or os.getenv("BEDROCK_EXTRACTION_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        self._region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=self._region,
            config=Config(connect_timeout=10, read_timeout=60, retries={"max_attempts": 2}),
        )

    @property
    def provider_name(self) -> str:
        return "bedrock"

    @property
    def model_id(self) -> str:
        return self._model_id

    def extract(self, document: TranscriptDocument) -> ExtractionResult:
        if not document.segments:
            return ExtractionResult.success_result([], provider=self.provider_name, model=self._model_id)

        try:
            response = self._client.converse(
                modelId=self._model_id,
                system=[{"text": EXTRACTION_SYSTEM_PROMPT}],
                messages=[{"role": "user", "content": [{"text": build_extraction_prompt(document)}]}],
                inferenceConfig={"maxTokens": 2000},
            )

            raw_text = response["output"]["message"]["content"][0]["text"]

            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError as e:
                return ExtractionResult.failure_result(
                    provider=self.provider_name,
                    model=self._model_id,
                    error=f"Model did not return valid JSON: {e}",
                    error_kind=ExtractionErrorKind.INVALID_JSON,
                )

            events = parsed.get("events")
            if not isinstance(events, list):
                return ExtractionResult.failure_result(
                    provider=self.provider_name,
                    model=self._model_id,
                    error="Model response JSON did not contain an 'events' list",
                    error_kind=ExtractionErrorKind.INVALID_JSON,
                )

            return ExtractionResult.success_result(events, provider=self.provider_name, model=self._model_id)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "AccessDeniedException" and "verification" in error_message.lower():
                return ExtractionResult.failure_result(
                    provider=self.provider_name,
                    model=self._model_id,
                    error=(
                        "AWS account verification pending. "
                        "Bedrock extraction provider is correctly configured but live "
                        "inference is temporarily unavailable. Use --provider mock for development."
                    ),
                    error_kind=ExtractionErrorKind.NOT_AVAILABLE,
                )

            return ExtractionResult.failure_result(
                provider=self.provider_name,
                model=self._model_id,
                error=f"Bedrock ClientError [{error_code}]: {error_message}",
                error_kind=ExtractionErrorKind.PROVIDER_FAILURE,
            )

        except BotoCoreError as e:
            return ExtractionResult.failure_result(
                provider=self.provider_name,
                model=self._model_id,
                error=f"BotoCoreError: {e}",
                error_kind=ExtractionErrorKind.PROVIDER_FAILURE,
            )

        except (KeyError, IndexError) as e:
            return ExtractionResult.failure_result(
                provider=self.provider_name,
                model=self._model_id,
                error=f"Unexpected response format: {e}",
                error_kind=ExtractionErrorKind.PROVIDER_FAILURE,
            )
