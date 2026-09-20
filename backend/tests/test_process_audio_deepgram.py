import json
import os
import sys
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.transcription.deepgram import DeepgramTranscriptionProvider  # noqa: E402
from backend.core.care_event import from_stored_transcript  # noqa: E402
from backend.lambdas.process_audio.handler import lambda_handler  # noqa: E402

URLOPEN = "core.transcription.deepgram.urllib.request.urlopen"
KEY = "dg-secret-key-123"
ENV = {"AUDIO_BUCKET_NAME": "b", "MAX_AUDIO_SIZE_BYTES": "10485760"}


def event(key="audio/note-1.webm"):
    return {"detail": {"bucket": {"name": "b"}, "object": {"key": key}}}


def s3_mock():
    s3 = MagicMock()
    s3.head_object.side_effect = [
        {"ContentLength": 10},
        ClientError({"Error": {"Code": "404", "Message": "nf"}}, "HeadObject"),
    ]
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"webm-bytes")}
    return s3


def dg_response(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda *a: False
    return resp


PAYLOAD = {
    "metadata": {"duration": 2.0},
    "results": {
        "channels": [{"alternatives": [{"transcript": "My sister is ill today."}]}],
        "utterances": [{"transcript": "My sister is ill today.", "start": 0.2, "end": 1.8}],
    },
}


def run(s3, side_effect=None, return_value=None):
    provider = DeepgramTranscriptionProvider(api_key=KEY)
    with patch("backend.lambdas.process_audio.handler.boto3.client", return_value=s3), \
         patch("backend.lambdas.process_audio.handler.get_provider", return_value=provider), \
         patch.dict(os.environ, ENV), \
         patch(URLOPEN, side_effect=side_effect, return_value=return_value) as urlopen:
        return lambda_handler(event(), None), urlopen


def test_webm_audio_through_deepgram_writes_real_transcript():
    s3 = s3_mock()
    result, urlopen = run(s3, return_value=dg_response(PAYLOAD))

    req = urlopen.call_args[0][0]
    assert req.get_header("Content-type") == "audio/webm"
    assert req.data == b"webm-bytes"

    written = json.loads(s3.put_object.call_args[1]["Body"])
    assert s3.put_object.call_args[1]["Key"] == "transcripts/note-1.json"
    assert written["status"] == "completed"
    assert written["provider"] == "deepgram" and written["model"] == "nova-3"
    assert written["transcript"] == "My sister is ill today."
    assert written["segments"] == [
        {"text": "My sister is ill today.", "start_time": 0.2, "end_time": 1.8}
    ]
    assert KEY not in json.dumps(written) and KEY not in result["body"]

    # Downstream adapter keeps real timings and deterministic ids.
    doc = from_stored_transcript("note-1", written["transcript"], written["segments"])
    assert len(doc.segments) == 1 and doc.segments[0].start_time == 0.2
    assert doc.segments[0].segment_id.startswith("note-1-seg0-")
    again = from_stored_transcript("note-1", written["transcript"], written["segments"])
    assert again.segments[0].segment_id == doc.segments[0].segment_id


def test_deepgram_failure_writes_failed_status_and_no_fake_transcript(capsys):
    s3 = s3_mock()
    result, _ = run(s3, side_effect=urllib.error.HTTPError("u", 401, "x", {}, None))

    written = json.loads(s3.put_object.call_args[1]["Body"])
    assert written["status"] == "failed"
    assert written["transcript"] == ""
    assert "segments" not in written
    assert "HTTP 401" in written["error"]
    assert "sister" not in json.dumps(written) and "Papa ne" not in json.dumps(written)
    out = capsys.readouterr().out
    assert "Transcription FAILED" in out and KEY not in out


def test_stored_transcript_without_or_with_bad_segments_falls_back():
    for bad in (None, [], [{"nope": 1}], "junk"):
        doc = from_stored_transcript("n", "One. Two.", bad)
        assert [s.text for s in doc.segments] == ["One.", "Two."]
        assert all(s.start_time is None for s in doc.segments)
