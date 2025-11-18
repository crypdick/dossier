"""Integration tests for OpenAI SDK objects."""

import json
import tempfile
from pathlib import Path

import pytest
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionMessageToolCall,
)
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_message_tool_call import Function
from openai.types.completion_usage import CompletionUsage

from dossier import get_session


def read_jsonl_logs(session_dir: Path) -> list[dict]:
    """Read and parse all JSONL log entries."""
    log_file = session_dir / "events.jsonl"
    logs = []
    with open(log_file) as f:
        for line in f:
            logs.append(json.loads(line))
    return logs


def test_chat_completion_message_logging():
    """Test that ChatCompletionMessage objects are properly unpacked and logged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_chat_msg")

        # Create a ChatCompletionMessage (assistant response)
        msg = ChatCompletionMessage(
            role="assistant",
            content="Hello! How can I help you today?",
        )
        logger.info(msg)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have session_start and our message
        assert len(logs) == 1

        # Check the message log entry
        msg_log = logs[0]
        assert msg_log["event"] == "ChatCompletionMessage"
        assert msg_log["role"] == "assistant"
        assert msg_log["content"] == "Hello! How can I help you today?"
        assert "timestamp" in msg_log
        assert "level" in msg_log


def test_chat_completion_with_tool_call():
    """Test ChatCompletionMessage with tool calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_tool_call")

        # Create a message with a tool call
        tool_call = ChatCompletionMessageToolCall(
            id="call_abc123",
            function=Function(
                name="get_weather",
                arguments='{"location": "San Francisco", "unit": "fahrenheit"}',
            ),
            type="function",
        )

        msg = ChatCompletionMessage(
            role="assistant",
            content=None,
            tool_calls=[tool_call],
        )
        logger.info(msg)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the message log entry
        msg_log = logs[0]
        assert msg_log["event"] == "ChatCompletionMessage"
        assert msg_log["role"] == "assistant"
        assert msg_log["content"] is None
        assert "tool_calls" in msg_log
        assert len(msg_log["tool_calls"]) == 1
        assert msg_log["tool_calls"][0]["id"] == "call_abc123"
        assert msg_log["tool_calls"][0]["function"]["name"] == "get_weather"


def test_completion_usage_logging():
    """Test CompletionUsage objects are properly unpacked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_usage")

        # Create a CompletionUsage object
        usage = CompletionUsage(
            prompt_tokens=150,
            completion_tokens=75,
            total_tokens=225,
        )
        logger.info(usage)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the usage log entry
        usage_log = logs[0]
        assert usage_log["event"] == "CompletionUsage"
        assert usage_log["prompt_tokens"] == 150
        assert usage_log["completion_tokens"] == 75
        assert usage_log["total_tokens"] == 225


def test_chat_completion_full_response():
    """Test logging a full ChatCompletion response object."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_completion")

        # Create a full ChatCompletion object
        completion = ChatCompletion(
            id="chatcmpl-123",
            model="gpt-4",
            created=1677652288,
            object="chat.completion",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content="The weather in San Francisco is 68°F and foggy.",
                    ),
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=50,
                completion_tokens=12,
                total_tokens=62,
            ),
        )
        logger.info(completion)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the completion log entry
        comp_log = logs[0]
        assert comp_log["event"] == "ChatCompletion"
        assert comp_log["id"] == "chatcmpl-123"
        assert comp_log["model"] == "gpt-4"
        assert comp_log["object"] == "chat.completion"
        assert len(comp_log["choices"]) == 1
        assert (
            comp_log["choices"][0]["message"]["content"]
            == "The weather in San Francisco is 68°F and foggy."
        )
        assert comp_log["usage"]["total_tokens"] == 62


def test_openai_objects_with_bound_context():
    """Test that bound context is preserved with OpenAI objects."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_bound_openai")

        # Bind some context
        logger.bind(user_id="user_789", conversation_id="conv_abc")

        # Log a ChatCompletionMessage
        msg = ChatCompletionMessage(
            role="assistant",
            content="I'm here to help!",
        )
        logger.info(msg)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the message has bound context
        msg_log = logs[0]
        assert msg_log["user_id"] == "user_789"
        assert msg_log["conversation_id"] == "conv_abc"
        assert msg_log["content"] == "I'm here to help!"


def test_openai_conversation_flow():
    """Test logging a realistic OpenAI conversation flow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(
            log_dir=tmpdir,
            session_id="test_conversation",
        )
        logger.bind(model="gpt-4", user_id="user_123")

        # User message (we'd typically log this as a dict or custom object)
        logger.info("user_message", role="user", content="What's the weather in SF?")

        # API response
        completion = ChatCompletion(
            id="chatcmpl-456",
            model="gpt-4",
            created=1677652289,
            object="chat.completion",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content=None,
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id="call_weather_1",
                                function=Function(
                                    name="get_weather",
                                    arguments='{"city": "San Francisco"}',
                                ),
                                type="function",
                            )
                        ],
                    ),
                    finish_reason="tool_calls",
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=25,
                completion_tokens=15,
                total_tokens=40,
            ),
        )
        logger.info(completion)

        # Tool result
        logger.info(
            "tool_result",
            tool_call_id="call_weather_1",
            result={"temp": 68, "conditions": "foggy"},
        )

        # Final response
        final_completion = ChatCompletion(
            id="chatcmpl-789",
            model="gpt-4",
            created=1677652290,
            object="chat.completion",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content="It's 68°F and foggy in San Francisco.",
                    ),
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=45,
                completion_tokens=10,
                total_tokens=55,
            ),
        )
        logger.info(final_completion)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have 4 events
        assert len(logs) == 4

        # Check session_id in all logs
        for log in logs:
            assert log["session_id"] == "test_conversation"

        # Metadata bound after session_start, so check logs [1:]
        for log in logs[1:]:
            assert log["model"] == "gpt-4"
            assert log["user_id"] == "user_123"

    # Verify conversation flow
    assert logs[0]["event"] == "user_message"
    assert logs[1]["event"] == "ChatCompletion"
    assert logs[1]["choices"][0]["finish_reason"] == "tool_calls"
    assert logs[2]["event"] == "tool_result"
    assert logs[3]["event"] == "ChatCompletion"
    assert logs[3]["choices"][0]["finish_reason"] == "stop"


def test_openai_streaming_chunks():
    """Test logging OpenAI streaming chunk events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_streaming")

        # Simulate streaming chunks (simplified)
        chunks = ["Hello", " world", "!", " How", " can", " I", " help", "?"]

        for i, chunk in enumerate(chunks):
            logger.info(
                "stream_chunk", index=i, content=chunk, is_final=i == len(chunks) - 1
            )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have 8 chunks
        assert len(logs) == 8

    # Check all chunks are logged
    for i in range(0, 8):
        assert logs[i]["event"] == "stream_chunk"
        assert logs[i]["index"] == i
        assert logs[i]["content"] == chunks[i]


def test_openai_error_handling():
    """Test logging OpenAI API errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_error")

        # Log an API error
        logger.error(
            "openai_api_error",
            error_type="RateLimitError",
            message="Rate limit exceeded",
            status_code=429,
            retry_after=30,
        )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the error log entry
        error_log = logs[0]
        assert error_log["event"] == "openai_api_error"
        assert error_log["level"] == "error"
        assert error_log["error_type"] == "RateLimitError"
        assert error_log["status_code"] == 429


def test_mixed_openai_and_langchain():
    """Test that OpenAI and LangChain objects can be logged together."""
    from langchain_core.messages import HumanMessage

    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_mixed")

        # Log LangChain message
        lc_msg = HumanMessage(content="What's the weather?")
        logger.info(lc_msg)

        # Log OpenAI response
        openai_msg = ChatCompletionMessage(
            role="assistant",
            content="Let me check that for you.",
        )
        logger.info(openai_msg)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check both were logged correctly
        assert len(logs) == 2  # + 2 messages
        assert logs[0]["event"] == "HumanMessage"
        assert logs[1]["event"] == "ChatCompletionMessage"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
