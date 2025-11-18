"""Integration tests for LangChain message types."""

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from dossier.dossier import Dossier
from tests.conftest import read_jsonl_logs


def test_human_message_logging(test_logger: Dossier):
    """Test that HumanMessage objects are properly unpacked and logged."""
    # Create and log a HumanMessage
    msg = HumanMessage(content="What's the weather like today?")
    test_logger.info(msg)

    # Read logs
    logs = read_jsonl_logs(test_logger.get_session_path())

    # Should have session_start and our message
    assert len(logs) == 1

    # Check the HumanMessage log entry
    msg_log = logs[0]
    assert msg_log["event"] == "HumanMessage"
    assert msg_log["content"] == "What's the weather like today?"
    assert msg_log["type"] == "human"
    assert "timestamp" in msg_log
    assert "level" in msg_log


def test_ai_message_logging(test_logger: Dossier):
    """Test that AIMessage objects are properly unpacked and logged."""
    # Create and log an AIMessage
    msg = AIMessage(content="The weather is sunny with a high of 75°F")
    test_logger.info(msg)

    # Read logs
    logs = read_jsonl_logs(test_logger.get_session_path())

    # Check the AIMessage log entry
    msg_log = logs[0]
    assert msg_log["event"] == "AIMessage"
    assert msg_log["content"] == "The weather is sunny with a high of 75°F"
    assert msg_log["type"] == "ai"


def test_system_message_logging(test_logger: Dossier):
    """Test that SystemMessage objects are properly unpacked and logged."""
    # Create and log a SystemMessage
    msg = SystemMessage(content="You are a helpful assistant")
    test_logger.info(msg)

    # Read logs
    logs = read_jsonl_logs(test_logger.get_session_path())

    # Check the SystemMessage log entry
    msg_log = logs[0]
    assert msg_log["event"] == "SystemMessage"
    assert msg_log["content"] == "You are a helpful assistant"
    assert msg_log["type"] == "system"


def test_tool_message_logging(test_logger: Dossier):
    """Test that ToolMessage objects are properly unpacked and logged."""
    # Create and log a ToolMessage
    msg = ToolMessage(
        content='{"temperature": 75, "conditions": "sunny"}',
        tool_call_id="call_abc123",
    )
    test_logger.info(msg)

    # Read logs
    logs = read_jsonl_logs(test_logger.get_session_path())

    # Check the ToolMessage log entry
    msg_log = logs[0]
    assert msg_log["event"] == "ToolMessage"
    assert msg_log["content"] == '{"temperature": 75, "conditions": "sunny"}'
    assert msg_log["tool_call_id"] == "call_abc123"
    assert msg_log["type"] == "tool"


def test_message_with_additional_kwargs(test_logger: Dossier):
    """Test messages with additional_kwargs are properly unpacked."""
    # Create AIMessage with additional kwargs (e.g., function call)
    msg = AIMessage(
        content="",
        additional_kwargs={
            "function_call": {"name": "get_weather", "arguments": '{"city": "SF"}'}
        },
    )
    test_logger.info(msg)

    # Read logs
    logs = read_jsonl_logs(test_logger.get_session_path())

    # Check the AIMessage log entry
    msg_log = logs[0]
    assert msg_log["event"] == "AIMessage"
    assert "additional_kwargs" in msg_log
    assert "function_call" in msg_log["additional_kwargs"]
    assert msg_log["additional_kwargs"]["function_call"]["name"] == "get_weather"


def test_message_sequence_logging(test_logger: Dossier):
    """Test logging a realistic conversation sequence."""
    # Bind metadata for the conversation
    test_logger.bind(model="gpt-4", user_id="user_123")

    # Log a conversation
    messages = [
        SystemMessage(content="You are a helpful weather assistant"),
        HumanMessage(content="What's the weather in San Francisco?"),
        AIMessage(content="Let me check that for you."),
        ToolMessage(
            content='{"temp": 68, "conditions": "foggy"}',
            tool_call_id="call_1",
        ),
        AIMessage(content="It's 68°F and foggy in San Francisco."),
    ]

    for msg in messages:
        test_logger.info(msg)

    # Read logs
    logs = read_jsonl_logs(test_logger.get_session_path())
    session_id = test_logger.get_session_id()

    # Should have 5 messages
    assert len(logs) == 5

    # Check session_id is in all logs
    for log in logs:
        assert log["session_id"] == session_id

    # Metadata bound after session_start, so check logs [1:]
    for log in logs[1:]:
        assert log["model"] == "gpt-4"
        assert log["user_id"] == "user_123"

    # Verify conversation order
    assert logs[0]["event"] == "SystemMessage"
    assert logs[1]["event"] == "HumanMessage"
    assert logs[2]["event"] == "AIMessage"
    assert logs[3]["event"] == "ToolMessage"
    assert logs[4]["event"] == "AIMessage"


def test_message_with_bound_context(test_logger: Dossier):
    """Test that bound context is preserved with message logging."""
    # Bind some context
    test_logger.bind(request_id="req_123", user_id="user_456")

    # Log a message
    msg = HumanMessage(content="Hello")
    test_logger.info(msg)

    # Read logs
    logs = read_jsonl_logs(test_logger.get_session_path())

    # Check the message has bound context
    msg_log = logs[0]
    assert msg_log["request_id"] == "req_123"
    assert msg_log["user_id"] == "user_456"
    assert msg_log["content"] == "Hello"


def test_nested_message_in_list(test_logger: Dossier):
    """Test logging messages nested in lists or other structures."""
    # Log an event with messages as part of the data
    messages = [
        HumanMessage(content="Question 1"),
        AIMessage(content="Answer 1"),
    ]

    test_logger.info("batch_process", messages=messages, count=len(messages))

    # Read logs
    logs = read_jsonl_logs(test_logger.get_session_path())

    # Check the log entry
    log_entry = logs[0]
    assert log_entry["event"] == "batch_process"
    assert log_entry["count"] == 2
    assert "messages" in log_entry
    assert len(log_entry["messages"]) == 2
    # Messages should be converted to dicts
    assert log_entry["messages"][0]["content"] == "Question 1"
    assert log_entry["messages"][1]["content"] == "Answer 1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
