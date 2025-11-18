"""Test unbind functionality"""

import json

from dossier import get_logger


def test_unbind_single_key(tmp_path):
    """Test unbinding a single context key"""
    logger = get_logger(log_dir=tmp_path / "logs", model="gpt-4")

    # Add context
    logger.bind(request_id="req_123", user_id="user_456")
    logger.info("event1")

    # Remove one key
    logger.unbind("request_id")
    logger.info("event2")

    # Verify
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event1 = json.loads(lines[-2])
        event2 = json.loads(lines[-1])

        # Event1 should have both
        assert event1["request_id"] == "req_123"
        assert event1["user_id"] == "user_456"

        # Event2 should only have user_id
        assert "request_id" not in event2
        assert event2["user_id"] == "user_456"


def test_unbind_multiple_keys(tmp_path):
    """Test unbinding multiple keys at once"""
    logger = get_logger(log_dir=tmp_path / "logs", model="gpt-4")

    # Add context
    logger.bind(request_id="req_123", user_id="user_456", trace_id="trace_789")
    logger.info("event1")

    # Remove multiple keys
    logger.unbind("request_id", "trace_id")
    logger.info("event2")

    # Verify
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event1 = json.loads(lines[-2])
        event2 = json.loads(lines[-1])

        # Event1 should have all three
        assert event1["request_id"] == "req_123"
        assert event1["user_id"] == "user_456"
        assert event1["trace_id"] == "trace_789"

        # Event2 should only have user_id
        assert "request_id" not in event2
        assert "trace_id" not in event2
        assert event2["user_id"] == "user_456"


def test_unbind_chaining(tmp_path):
    """Test chaining unbind with other methods"""
    logger = get_logger(log_dir=tmp_path / "logs", model="gpt-4")

    # Chain bind, unbind, and log
    logger.bind(a="1", b="2", c="3").unbind("b").info("test")

    # Verify
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_event = json.loads(lines[-1])

        assert last_event["a"] == "1"
        assert "b" not in last_event
        assert last_event["c"] == "3"
