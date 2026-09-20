#!/usr/bin/env python3
"""
Local transcription test script.

Usage:
    python backend/scripts/test_transcription.py --provider mock
    python backend/scripts/test_transcription.py --provider voxtral --audio-file elderlink-test.wav
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.transcription import (
    DeepgramTranscriptionProvider,
    GroqTranscriptionProvider,
    MockTranscriptionProvider,
    OpenAITranscriptionProvider,
    TranscriptionResult,
    VoxtralProvider,
)


def get_audio_bytes(audio_file: str) -> bytes:
    with open(audio_file, "rb") as f:
        return f.read()


def get_audio_format(audio_file: str) -> str:
    return audio_file.split(".")[-1].lower()


def print_result(result: TranscriptionResult) -> None:
    print(f"\n{'=' * 60}")
    print(f"Provider: {result.provider}")
    print(f"Model: {result.model}")
    print(f"Success: {result.success}")
    if result.language:
        print(f"Language: {result.language}")
    if result.duration_seconds:
        print(f"Duration: {result.duration_seconds:.2f}s")
    if result.error:
        print(f"Error: {result.error}")
    print(f"{'=' * 60}")
    if result.success:
        print(f"\nTranscript:\n{result.text}\n")


def main():
    parser = argparse.ArgumentParser(description="Test transcription providers")
    parser.add_argument(
        "--provider",
        choices=["mock", "voxtral", "deepgram", "openai", "groq"],
        required=True,
        help="Transcription provider to use",
    )
    parser.add_argument(
        "--audio-file",
        default="elderlink-test.wav",
        help="Path to audio file (required for voxtral, optional for mock)",
    )
    parser.add_argument(
        "--transcript",
        help="Custom transcript for mock provider",
    )

    args = parser.parse_args()

    if args.provider == "mock":
        provider = MockTranscriptionProvider(fixed_transcript=args.transcript)
        audio_bytes = b"mock-audio-data" if not os.path.exists(args.audio_file) else get_audio_bytes(args.audio_file)
        audio_format = get_audio_format(args.audio_file) if os.path.exists(args.audio_file) else "wav"

    elif args.provider == "voxtral":
        if not os.path.exists(args.audio_file):
            print(f"Error: Audio file not found: {args.audio_file}", file=sys.stderr)
            sys.exit(1)
        provider = VoxtralProvider()
        audio_bytes = get_audio_bytes(args.audio_file)
        audio_format = get_audio_format(args.audio_file)

    elif args.provider == "deepgram":
        # Key comes from the DEEPGRAM_API_KEY environment variable only.
        if not os.path.exists(args.audio_file):
            print(f"Error: Audio file not found: {args.audio_file}", file=sys.stderr)
            sys.exit(1)
        provider = DeepgramTranscriptionProvider()
        audio_bytes = get_audio_bytes(args.audio_file)
        audio_format = get_audio_format(args.audio_file)

    elif args.provider == "openai":
        # Key comes from the OPENAI_API_KEY environment variable only.
        if not os.path.exists(args.audio_file):
            print(f"Error: Audio file not found: {args.audio_file}", file=sys.stderr)
            sys.exit(1)
        provider = OpenAITranscriptionProvider()
        audio_bytes = get_audio_bytes(args.audio_file)
        audio_format = get_audio_format(args.audio_file)

    elif args.provider == "groq":
        # Key comes from the GROQ_API_KEY environment variable only.
        if not os.path.exists(args.audio_file):
            print(f"Error: Audio file not found: {args.audio_file}", file=sys.stderr)
            sys.exit(1)
        provider = GroqTranscriptionProvider()
        audio_bytes = get_audio_bytes(args.audio_file)
        audio_format = get_audio_format(args.audio_file)

    else:
        print(f"Unknown provider: {args.provider}", file=sys.stderr)
        sys.exit(1)

    print(f"Testing {provider.provider_name} provider ({provider.model_id})...")
    result = provider.transcribe(audio_bytes, audio_format)
    print_result(result)

    if not result.success and "verification" in (result.error or "").lower():
        print("\nNote: AWS account verification is pending. This is expected.")
        print("The provider is correctly configured. Use --provider mock for development.\n")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()