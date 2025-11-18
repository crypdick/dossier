"""Tests for session_logger module"""

import json

import pytest

from dossier.session_logger import SessionLogger, create_logger


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary directory for logs"""
    return tmp_path / "test_logs"


@pytest.fixture
def logger(temp_log_dir):
    """Create a logger instance for testing"""
    logger = SessionLogger(log_dir=temp_log_dir, session_prefix="test")
    logger.start_session(model="gpt-5", mode="test")
    yield logger
    if logger.session_id:
        logger.end_session()


def test_session_creation(temp_log_dir):
    """Test that a session is created with proper files"""
    logger = SessionLogger(log_dir=temp_log_dir)
    session_id = logger.start_session(model="gpt-5", mode="agent")

    assert logger.session_id == session_id
    assert logger.session_dir.exists()
    assert (logger.session_dir / "events.jsonl").exists()
    assert (logger.session_dir / "session.log").exists()

    # Save session_dir before ending session
    session_dir = logger.session_dir
    logger.end_session()

    # Check metadata file was created
    assert (session_dir / "metadata.json").exists()


def test_log_user_message(logger):
    """Test logging a user message"""
    logger.log_user_message("Hello, agent!", metadata={"mode": "agent"})

    # Check the log entry was added
    assert len(logger.log_entries) > 1  # session_start + user_message
    last_entry = logger.log_entries[-1]
    assert last_entry.event_type == "user_message"
    assert last_entry.data["content"] == "Hello, agent!"
    assert last_entry.data["metadata"]["mode"] == "agent"


def test_log_system_message(logger):
    """Test logging a system message"""
    logger.log_system_message("System initialized", metadata={"type": "init"})

    last_entry = logger.log_entries[-1]
    assert last_entry.event_type == "system_message"
    assert last_entry.data["content"] == "System initialized"


def test_log_tool_call_with_complex_arguments(logger):
    """Test logging tool calls with complex arguments"""
    complex_args = {
        "text": "Some long text",
        "nested": {"key": "value"},
        "list": [1, 2, 3],
        "code": "plt.plot([1, 2, 3])\nplt.title('Test')",
    }

    logger.log_tool_call(
        tool_name="create_figure", arguments=complex_args, call_id="call_123"
    )

    last_entry = logger.log_entries[-1]
    assert last_entry.event_type == "tool_call"
    assert last_entry.data["tool_name"] == "create_figure"
    assert last_entry.data["arguments"] == complex_args
    assert last_entry.data["call_id"] == "call_123"


def test_log_tool_result_with_non_json_serializable_objects(logger):
    """Test that tool results with non-JSON-serializable objects are handled gracefully

    This reproduces the bug where LangChain ToolMessage objects aren't JSON serializable.
    """
    try:
        from langchain_core.messages import ToolMessage

        # Create a real LangChain ToolMessage
        tool_message = ToolMessage(
            content="Tool executed successfully", tool_call_id="call_123"
        )

        # This should not raise an exception
        logger.log_tool_result(
            tool_name="test_tool", result=tool_message, call_id="call_123"
        )

        last_entry = logger.log_entries[-1]
        assert last_entry.event_type == "tool_result"
        assert last_entry.data["tool_name"] == "test_tool"
        # Result should be converted to string (not raise TypeError)
        assert isinstance(last_entry.data["result"], str)
        assert "Tool executed successfully" in last_entry.data["result"]

    except ImportError:
        # If langchain_core not available, use a mock
        class MockToolMessage:
            """Mock LangChain ToolMessage"""

            def __init__(self, content):
                self.content = content
                self.type = "tool"

            def __str__(self):
                return self.content

        mock_result = MockToolMessage("Tool executed successfully")

        # This should not raise an exception
        logger.log_tool_result(
            tool_name="test_tool", result=mock_result, call_id="call_123"
        )

        last_entry = logger.log_entries[-1]
        assert last_entry.event_type == "tool_result"
        assert last_entry.data["tool_name"] == "test_tool"
        # Result should be converted to string
        assert isinstance(last_entry.data["result"], str)
        assert last_entry.data["result"] == "Tool executed successfully"


def test_log_tool_result_with_dict(logger):
    """Test tool results that are already serializable"""
    result = {"status": "success", "message": "Done"}

    logger.log_tool_result(tool_name="test_tool", result=result, call_id="call_456")

    last_entry = logger.log_entries[-1]
    assert last_entry.data["result"] == result


def test_log_agent_response(logger):
    """Test logging agent responses"""
    logger.log_agent_response(
        "I can help with that!", is_complete=True, metadata={"source": "streaming"}
    )

    last_entry = logger.log_entries[-1]
    assert last_entry.event_type == "agent_response"
    assert last_entry.data["content"] == "I can help with that!"
    assert last_entry.data["is_complete"] is True


def test_log_token_usage(logger):
    """Test logging token usage"""
    logger.log_token_usage(
        input_tokens=100, output_tokens=50, model="gpt-5", cost=0.0025
    )

    last_entry = logger.log_entries[-1]
    assert last_entry.event_type == "token_usage"
    assert last_entry.data["input_tokens"] == 100
    assert last_entry.data["output_tokens"] == 50
    assert last_entry.data["total_tokens"] == 150
    assert last_entry.data["cost_usd"] == 0.0025


def test_log_error(logger):
    """Test logging errors"""
    logger.log_error(
        error_type="ValueError",
        error_message="Invalid input",
        traceback="Traceback...",
        metadata={"context": "processing"},
    )

    last_entry = logger.log_entries[-1]
    assert last_entry.event_type == "error"
    assert last_entry.level == "ERROR"
    assert last_entry.data["error_type"] == "ValueError"


def test_jsonl_format(logger, temp_log_dir):
    """Test that events.jsonl contains valid JSON on each line"""
    logger.log_user_message("Test message")

    # Save session_dir before ending session
    session_dir = logger.session_dir
    logger.end_session()

    jsonl_path = session_dir / "events.jsonl"
    with open(jsonl_path) as f:
        for line in f:
            # Each line should be valid JSON
            data = json.loads(line)
            assert "timestamp" in data
            assert "event_type" in data
            assert "level" in data


def test_context_manager(temp_log_dir):
    """Test using SessionLogger as a context manager"""
    with SessionLogger(log_dir=temp_log_dir) as logger:
        logger.start_session(model="gpt-5")
        logger.log_user_message("Test")
        session_dir = logger.session_dir

    # Session should be ended
    assert (session_dir / "metadata.json").exists()


def test_convenience_function(temp_log_dir):
    """Test the create_logger convenience function"""
    logger = create_logger(log_dir=temp_log_dir, model="gpt-5", mode="agent")

    assert logger.session_id is not None
    assert logger.session_metadata.model == "gpt-5"
    assert logger.session_metadata.mode == "agent"

    logger.end_session()


def test_log_api_request_and_response(logger):
    """Test logging API requests and responses"""
    # Log request
    logger.log_api_request(
        endpoint="/v1/chat/completions",
        payload={"model": "gpt-5", "messages": [{"role": "user", "content": "Hi"}]},
        headers={"Authorization": "Bearer ***"},
    )

    # Log response
    logger.log_api_response(
        endpoint="/v1/chat/completions",
        response={"choices": [{"message": {"content": "Hello"}}]},
        status_code=200,
        duration_ms=150.5,
    )

    assert len(logger.log_entries) >= 3  # session_start + request + response

    # Check request
    request_entry = logger.log_entries[-2]
    assert request_entry.event_type == "api_request"
    assert request_entry.data["endpoint"] == "/v1/chat/completions"

    # Check response
    response_entry = logger.log_entries[-1]
    assert response_entry.event_type == "api_response"
    assert response_entry.data["status_code"] == 200
