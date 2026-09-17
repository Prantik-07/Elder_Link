import pytest
import sys
import os

# Clear any mocked core.transcription module to ensure we test the real implementation
if "core.transcription" in sys.modules:
    del sys.modules["core.transcription"]
if "core" in sys.modules:
    del sys.modules["core"]

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.transcription import (
    TranscriptionResult,
    MockTranscriptionProvider,
    VoxtralProvider,
    MOCK_TRANSCRIPT,
)


class TestTranscriptionResult:
    def test_success_result_creation(self):
        result = TranscriptionResult.success_result(
            text="Test transcript",
            model="test-model",
            provider="test-provider",
            language="en-US",
            duration_seconds=10.5,
        )

        assert result.text == "Test transcript"
        assert result.model == "test-model"
        assert result.provider == "test-provider"
        assert result.language == "en-US"
        assert result.duration_seconds == 10.5
        assert result.success is True
        assert result.error is None

    def test_failure_result_creation(self):
        result = TranscriptionResult.failure_result(
            model="test-model",
            provider="test-provider",
            error="Something went wrong",
        )

        assert result.text == ""
        assert result.model == "test-model"
        assert result.provider == "test-provider"
        assert result.success is False
        assert result.error == "Something went wrong"


class TestMockTranscriptionProvider:
    def test_mock_provider_returns_expected_transcript(self):
        provider = MockTranscriptionProvider()
        result = provider.transcribe(b"fake audio", "wav")

        assert result.success is True
        assert result.text == MOCK_TRANSCRIPT
        assert result.provider == "mock"
        assert result.model == "mock-transcriber-v1"
        assert result.language == "hi-IN"

    def test_mock_provider_custom_transcript(self):
        custom = "Custom transcript for testing"
        provider = MockTranscriptionProvider(fixed_transcript=custom)
        result = provider.transcribe(b"fake audio", "wav")

        assert result.text == custom

    def test_mock_provider_handles_empty_audio(self):
        provider = MockTranscriptionProvider()
        result = provider.transcribe(b"", "wav")

        assert result.success is False
        assert "Empty audio bytes" in result.error

    def test_mock_provider_returns_duration(self):
        provider = MockTranscriptionProvider()
        audio_data = b"x" * 16000
        result = provider.transcribe(audio_data, "wav")

        assert result.duration_seconds is not None
        assert result.duration_seconds == pytest.approx(1.0, rel=0.1)


class TestTranscriptionProviderInterface:
    def test_providers_implement_interface(self):
        mock_provider = MockTranscriptionProvider()

        assert hasattr(mock_provider, "provider_name")
        assert hasattr(mock_provider, "model_id")
        assert hasattr(mock_provider, "transcribe")
        assert callable(mock_provider.transcribe)

        assert mock_provider.provider_name == "mock"
        assert mock_provider.model_id == "mock-transcriber-v1"

    def test_service_can_use_different_providers(self):
        providers = [
            MockTranscriptionProvider(),
            MockTranscriptionProvider(fixed_transcript="Different transcript"),
        ]

        results = []
        for provider in providers:
            result = provider.transcribe(b"audio", "wav")
            results.append(result)

        assert len(results) == 2
        assert results[0].text == MOCK_TRANSCRIPT
        assert results[1].text == "Different transcript"
        assert all(r.success for r in results)


class TestUnsupportedAudioFormat:
    def test_voxtral_provider_rejects_unsupported_format(self):
        provider = VoxtralProvider()
        result = provider.transcribe(b"audio", "xyz")

        assert result.success is False
        assert "Unsupported audio format" in result.error
        assert "xyz" in result.error


class TestErrorHandling:
    def test_transcription_result_can_be_checked_for_success(self):
        success = TranscriptionResult.success_result("ok", "m", "p")
        failure = TranscriptionResult.failure_result("m", "p", "err")

        assert success.success is True
        assert failure.success is False

        if success.success:
            assert success.text == "ok"
        if not failure.success:
            assert failure.error == "err"