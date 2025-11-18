"""Tests for session_logger module"""

import json
from dataclasses import dataclass

import pytest

from dossier import get_logger


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary directory for logs"""
    return tmp_path / "test_logs"


@pytest.fixture
def logger(temp_log_dir):
    """Create a logger instance for testing"""
    logger = get_logger(
        log_dir=temp_log_dir, session_prefix="test_", model="gpt-5", mode="test"
    )
    yield logger
    # Cleanup: close file handler
    if logger._file_handler:
        logger._file_handler.close()


def test_session_creation(temp_log_dir):
    """Test that a session is created with proper files"""
    logger = get_logger(log_dir=temp_log_dir, model="gpt-5", mode="agent")

    assert logger.session_id is not None
    assert logger.session_dir.exists()
    assert (logger.session_dir / "events.jsonl").exists()

    # Cleanup
    logger._file_handler.close()

    # Verify events.jsonl has session_start
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        first_event = json.loads(lines[0])
        assert first_event["event"] == "session_start"


def test_log_user_message(logger):
    """Test logging a user message using new API"""
    logger.info("user_message", content="Hello, agent!", metadata={"mode": "agent"})

    # Verify by reading the log file
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        # Should have session_start + our message
        assert len(lines) >= 2
        last_line = json.loads(lines[-1])
        assert last_line["event"] == "user_message"
        assert last_line["content"] == "Hello, agent!"


def test_log_system_message(logger):
    """Test logging a system message using new API"""
    logger.info(
        "system_message", content="System initialized", metadata={"type": "init"}
    )

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])
        assert last_line["event"] == "system_message"
        assert last_line["content"] == "System initialized"


def test_log_tool_call_with_complex_arguments(logger):
    """Test logging tool calls with complex arguments"""
    complex_args = {
        "text": "Some long text",
        "nested": {"key": "value"},
        "list": [1, 2, 3],
        "code": "plt.plot([1, 2, 3])\nplt.title('Test')",
    }

    logger.info(
        "tool_call",
        tool_name="create_figure",
        arguments=complex_args,
        call_id="call_123",
    )

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])
        assert last_line["event"] == "tool_call"
        assert last_line["tool_name"] == "create_figure"
        assert last_line["arguments"] == complex_args
        assert last_line["call_id"] == "call_123"


def test_log_tool_result_with_non_json_serializable_objects(logger):
    """Test that tool results with non-JSON-serializable objects are handled gracefully

    This reproduces the bug where LangChain ToolMessage objects aren't JSON serializable.
    """

    # Use a mock object that isn't JSON serializable
    class MockToolMessage:
        """Mock LangChain ToolMessage"""

        def __init__(self, content):
            self.content = content
            self.type = "tool"

        def __str__(self):
            return self.content

    mock_result = MockToolMessage("Tool executed successfully")

    # This should not raise an exception
    logger.info(
        "tool_result", tool_name="test_tool", result=mock_result, call_id="call_123"
    )

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])
        assert last_line["event"] == "tool_result"
        assert last_line["tool_name"] == "test_tool"
        # Object gets unpacked with prefix: result_content, result_type
        assert "result_content" in last_line
        assert last_line["result_content"] == "Tool executed successfully"
        assert last_line["result_type"] == "tool"


def test_log_tool_result_with_dict(logger):
    """Test tool results that are already serializable"""
    result = {"status": "success", "message": "Done"}

    logger.info("tool_result", tool_name="test_tool", result=result, call_id="call_456")

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])
        assert last_line["result"] == result


def test_log_agent_response(logger):
    """Test logging agent responses"""
    logger.info(
        "agent_response",
        content="I can help with that!",
        is_complete=True,
        metadata={"source": "streaming"},
    )

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])
        assert last_line["event"] == "agent_response"
        assert last_line["content"] == "I can help with that!"
        assert last_line["is_complete"] is True


def test_log_token_usage(logger):
    """Test logging token usage"""
    logger.info(
        "token_usage",
        input_tokens=100,
        output_tokens=50,
        model="gpt-5",
        cost_usd=0.0025,
    )

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])
        assert last_line["event"] == "token_usage"
        assert last_line["input_tokens"] == 100
        assert last_line["output_tokens"] == 50
        assert last_line["cost_usd"] == 0.0025


def test_log_error(logger):
    """Test logging errors"""
    logger.error(
        "error",
        error_type="ValueError",
        error_message="Invalid input",
        traceback="Traceback...",
        metadata={"context": "processing"},
    )

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])
        assert last_line["event"] == "error"
        assert last_line["level"] == "error"
        assert last_line["error_type"] == "ValueError"


def test_jsonl_format(logger, temp_log_dir):
    """Test that events.jsonl contains valid JSON on each line"""
    logger.info("test_message", content="Test message")

    jsonl_path = logger.session_dir / "events.jsonl"
    with open(jsonl_path) as f:
        for line in f:
            # Each line should be valid JSON
            data = json.loads(line)
            assert "timestamp" in data
            assert "event" in data
            assert "level" in data


def test_context_manager(temp_log_dir):
    """Test using get_logger with context manager"""
    with get_logger(log_dir=temp_log_dir, model="gpt-5") as logger:
        logger.info("test_event", content="Test")
        session_dir = logger.session_dir

    # Verify log was created
    assert (session_dir / "events.jsonl").exists()


def test_convenience_function(temp_log_dir):
    """Test the get_logger convenience function"""
    logger = get_logger(log_dir=temp_log_dir, model="gpt-5", mode="agent")

    assert logger.session_id is not None

    # Verify metadata is in the logs
    with open(logger.session_dir / "events.jsonl") as f:
        first_line = json.loads(f.readline())
        assert first_line["model"] == "gpt-5"
        assert first_line["mode"] == "agent"

    # Cleanup
    logger._file_handler.close()


def test_log_api_request_and_response(logger):
    """Test logging API requests and responses"""
    # Log request
    logger.debug(
        "api_request",
        endpoint="/v1/chat/completions",
        payload={"model": "gpt-5", "messages": [{"role": "user", "content": "Hi"}]},
        headers={"Authorization": "Bearer ***"},
    )

    # Log response
    logger.debug(
        "api_response",
        endpoint="/v1/chat/completions",
        response={"choices": [{"message": {"content": "Hello"}}]},
        status_code=200,
        duration_ms=150.5,
    )

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        # Should have session_start + request + response
        assert len(lines) >= 3


def test_auto_event_type_detection(logger):
    """Test that event types can be inferred from object class names"""

    @dataclass
    class ToolResult:
        result: str
        success: bool

    @dataclass
    class UserMessage:
        content: str
        role: str = "user"

    # Test auto-detection with dataclasses
    tool_result = ToolResult(result="Done", success=True)
    logger.info(tool_result)  # Event type should be "tool_result"

    user_msg = UserMessage(content="Hello")
    logger.info(user_msg)  # Event type should be "user_message"

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        # Get last two lines
        tool_result_line = json.loads(lines[-2])
        user_msg_line = json.loads(lines[-1])

        assert tool_result_line["event"] == "ToolResult"
        assert tool_result_line["result"] == "Done"
        assert tool_result_line["success"] is True

        assert user_msg_line["event"] == "UserMessage"
        assert user_msg_line["content"] == "Hello"
        assert user_msg_line["role"] == "user"


def test_bind_context(logger):
    """Test binding context to logger"""
    # Bind mutates the logger in place
    result = logger.bind(request_id="req_123", user_id="user_456")

    # bind() returns self for chaining
    assert result is logger

    # Log with bound context
    logger.info("processing_request", status="started")

    # Add more context (chaining)
    logger.bind(trace_id="trace_789")
    logger.info("continued_processing", status="done")

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        # Get last two lines
        first_log = json.loads(lines[-2])
        second_log = json.loads(lines[-1])

        # First log has request context
        assert first_log["request_id"] == "req_123"
        assert first_log["user_id"] == "user_456"
        assert "trace_id" not in first_log  # Trace added after

        # Second log has both contexts
        assert second_log["request_id"] == "req_123"
        assert second_log["user_id"] == "user_456"
        assert second_log["trace_id"] == "trace_789"


def test_generic_session_metadata(temp_log_dir):
    """Test that session can accept arbitrary metadata"""
    logger = get_logger(
        log_dir=temp_log_dir,
        model="gpt-4-turbo",
        mode="agent",
        user_id="user_123",
        experiment="temperature_comparison",
        deployment_env="production",
        custom_field="custom_value",
    )

    # All metadata should be bound to every log
    logger.info("test_event", message="Hello")

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])

        # Verify all session metadata is present
        assert last_line["model"] == "gpt-4-turbo"
        assert last_line["mode"] == "agent"
        assert last_line["user_id"] == "user_123"
        assert last_line["experiment"] == "temperature_comparison"
        assert last_line["deployment_env"] == "production"
        assert last_line["custom_field"] == "custom_value"

    # Cleanup
    logger._file_handler.close()


def test_custom_processor_function(temp_log_dir):
    """Test that custom processor functions can be registered"""

    # Simple function processor
    def add_hostname(logger, method_name, event_dict):
        event_dict["hostname"] = "test-host"
        return event_dict

    logger = get_logger(log_dir=temp_log_dir, processors=[add_hostname], model="gpt-4")
    logger.info("test_event", data="value")

    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        last_line = json.loads(lines[-1])
        # Custom field should be present
        assert last_line["hostname"] == "test-host"

    # Cleanup
    logger._file_handler.close()


def test_custom_processor_stateful_class(temp_log_dir):
    """Test that stateful processor classes can be registered"""

    # Stateful processor class (like CostTracker)
    class TokenCounter:
        def __init__(self):
            self.total_tokens = 0
            self.call_count = 0

        def __call__(self, logger, method_name, event_dict):
            # Track token usage
            if "input_tokens" in event_dict and "output_tokens" in event_dict:
                total = event_dict["input_tokens"] + event_dict["output_tokens"]
                self.total_tokens += total
                self.call_count += 1
                # Add cumulative info to event
                event_dict["cumulative_tokens"] = self.total_tokens
                event_dict["token_call_count"] = self.call_count
            return event_dict

    counter = TokenCounter()
    logger = get_logger(log_dir=temp_log_dir, processors=[counter], model="gpt-4")

    # Log some token usage
    logger.info("token_usage", input_tokens=100, output_tokens=50)
    logger.info("token_usage", input_tokens=200, output_tokens=100)
    logger.info("other_event", data="no tokens")

    # Check state was maintained
    assert counter.total_tokens == 450  # 150 + 300
    assert counter.call_count == 2

    # Check cumulative data in logs
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        # Find token_usage lines (skip session_start)
        token_lines = [
            json.loads(line)
            for line in lines
            if "token_usage" in json.loads(line).get("event", "")
        ]

        assert len(token_lines) == 2
        assert token_lines[0]["cumulative_tokens"] == 150
        assert token_lines[0]["token_call_count"] == 1
        assert token_lines[1]["cumulative_tokens"] == 450
        assert token_lines[1]["token_call_count"] == 2

    # Cleanup
    logger._file_handler.close()
