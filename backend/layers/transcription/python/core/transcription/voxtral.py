import json
import os
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .types import TranscriptionResult
from .service import TranscriptionProvider


class VoxtralProvider(TranscriptionProvider):
    SUPPORTED_FORMATS = {"wav", "mp3", "flac", "ogg", "aiff"}

    def __init__(
        self,
        model_id: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self._model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "mistral.voxtral-mini-3b-2507")
        self._region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("bedrock-runtime", region_name=self._region)

    @property
    def provider_name(self) -> str:
        return "voxtral"

    @property
    def model_id(self) -> str:
        return self._model_id

    def transcribe(
        self,
        audio_bytes: bytes,
        audio_format: str,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        if audio_format.lower() not in self.SUPPORTED_FORMATS:
            return TranscriptionResult.failure_result(
                model=self._model_id,
                provider=self.provider_name,
                error=f"Unsupported audio format: {audio_format}. Supported: {', '.join(self.SUPPORTED_FORMATS)}",
            )

        try:
            response = self._client.converse(
                modelId=self._model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "audio": {
                                    "format": audio_format.lower(),
                                    "source": {"bytes": audio_bytes},
                                }
                            },
                            {
                                "text": "Transcribe this audio exactly. Preserve the spoken language and wording. Return only the transcript."
                            },
                        ],
                    }
                ],
                inferenceConfig={"maxTokens": 1000},
            )

            transcript = response["output"]["message"]["content"][0]["text"]

            return TranscriptionResult.success_result(
                text=transcript.strip(),
                model=self._model_id,
                provider=self.provider_name,
                language=language,
            )

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "AccessDeniedException" and "verification" in error_message.lower():
                return TranscriptionResult.failure_result(
                    model=self._model_id,
                    provider=self.provider_name,
                    error=(
                        "AWS account verification pending. "
                        "Voxtral provider is correctly configured but live inference "
                        "is temporarily unavailable. Use --provider mock for development."
                    ),
                )

            return TranscriptionResult.failure_result(
                model=self._model_id,
                provider=self.provider_name,
                error=f"Bedrock ClientError [{error_code}]: {error_message}",
            )

        except BotoCoreError as e:
            return TranscriptionResult.failure_result(
                model=self._model_id,
                provider=self.provider_name,
                error=f"BotoCoreError: {str(e)}",
            )

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            return TranscriptionResult.failure_result(
                model=self._model_id,
                provider=self.provider_name,
                error=f"Unexpected response format: {str(e)}",
            )

        except Exception as e:
            return TranscriptionResult.failure_result(
                model=self._model_id,
                provider=self.provider_name,
                error=f"Unexpected error: {str(e)}",
            )