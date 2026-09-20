import json
import os
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from backend.lambdas.notify_flag.handler import lambda_handler, notify_recipient

TOPIC = "arn:aws:sns:us-east-1:123456789012:elderlink-flag-notifications"
ENV = {"FLAG_NOTIFICATIONS_TOPIC_ARN": TOPIC, "ELDERLINK_AWS_REGION": "us-east-1"}

BODY = {
    "patient_name": "Dad",
    "flagged_by": "Shivaansh",
    "event_title": "Possible missed morning medication",
    "recipients": [{"name": "Priya", "email": "priya@example.com"}],
}

CONFIRMED = [{"Protocol": "email", "Endpoint": "priya@example.com", "SubscriptionArn": "arn:sub"}]
PENDING = [{"Protocol": "email", "Endpoint": "priya@example.com", "SubscriptionArn": "PendingConfirmation"}]


def _event(body):
    return {"body": json.dumps(body)}


def _sns(subscriptions):
    client = MagicMock()
    client.get_paginator.return_value.paginate.return_value = [{"Subscriptions": subscriptions}]
    return client


def _run(body, sns):
    with patch.dict(os.environ, ENV), patch(
        "backend.lambdas.notify_flag.handler.boto3.client", return_value=sns
    ):
        return lambda_handler(_event(body), None)


class TestNotifyRecipient:
    def test_unknown_address_is_subscribed_with_recipient_filter(self):
        sns = _sns([])
        status = notify_recipient(sns, TOPIC, "Priya@Example.com", "s", "m")
        assert status == "confirmation_sent"
        kwargs = sns.subscribe.call_args.kwargs
        assert kwargs["Protocol"] == "email"
        assert json.loads(kwargs["Attributes"]["FilterPolicy"]) == {"recipient": ["priya@example.com"]}
        sns.publish.assert_not_called()

    def test_pending_confirmation_does_not_publish(self):
        sns = _sns(PENDING)
        assert notify_recipient(sns, TOPIC, "priya@example.com", "s", "m") == "pending_confirmation"
        sns.publish.assert_not_called()
        sns.subscribe.assert_not_called()

    def test_confirmed_subscriber_gets_a_targeted_publish(self):
        sns = _sns(CONFIRMED)
        assert notify_recipient(sns, TOPIC, "priya@example.com", "s", "m") == "notified"
        attrs = sns.publish.call_args.kwargs["MessageAttributes"]
        assert attrs["recipient"]["StringValue"] == "priya@example.com"


class TestHandler:
    def test_invalid_json_is_400(self):
        assert lambda_handler({"body": "{"}, None)["statusCode"] == 400

    def test_missing_fields_is_400(self):
        with patch.dict(os.environ, ENV):
            assert lambda_handler(_event({**BODY, "event_title": ""}), None)["statusCode"] == 400

    def test_empty_or_invalid_recipients_is_400(self):
        with patch.dict(os.environ, ENV):
            assert lambda_handler(_event({**BODY, "recipients": []}), None)["statusCode"] == 400
            bad = {**BODY, "recipients": [{"name": "X", "email": "not-an-email"}]}
            assert lambda_handler(_event(bad), None)["statusCode"] == 400

    def test_too_many_recipients_is_400(self):
        many = [{"name": "A", "email": f"a{i}@example.com"} for i in range(11)]
        with patch.dict(os.environ, ENV):
            assert lambda_handler(_event({**BODY, "recipients": many}), None)["statusCode"] == 400

    def test_missing_topic_config_is_500(self):
        with patch.dict(os.environ, {}, clear=True):
            assert lambda_handler(_event(BODY), None)["statusCode"] == 500

    def test_success_reports_per_recipient_status(self):
        resp = _run(BODY, _sns(CONFIRMED))
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"])["results"][0]["status"] == "notified"

    def test_sns_failure_for_one_recipient_is_reported_not_raised(self):
        sns = _sns([])
        sns.subscribe.side_effect = ClientError({"Error": {"Code": "Boom", "Message": "x"}}, "Subscribe")
        resp = _run(BODY, sns)
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"])["results"][0]["status"] == "failed"

    def test_subject_is_ascii_and_bounded(self):
        sns = _sns(CONFIRMED)
        _run({**BODY, "patient_name": "Mää" + "x" * 70}, sns)
        subject = sns.publish.call_args.kwargs["Subject"]
        assert subject.isascii() and len(subject) <= 100
