"""Test logger registry/cache functionality."""

import logging

import pytest

from dossier import close_session, get_session
from dossier.dossier import _logger_cache


@pytest.fixture(autouse=True)
def clear_cache(tmp_path):
    """Clear logger cache before and after each test."""
    _logger_cache.clear()
    yield
    _logger_cache.clear()


def test_get_session_caches_by_session_id(tmp_path):
    """Test that get_session returns the same instance for the same session_id."""
    # First call creates a new logger
    logger1 = get_session(log_dir=tmp_path, session_id="test_session")

    # Second call returns the cached instance
    logger2 = get_session(log_dir=tmp_path, session_id="test_session")

    # Should be the exact same object
    assert logger1 is logger2
    assert id(logger1) == id(logger2)


def test_different_session_ids_create_different_loggers(tmp_path):
    """Test that different session_ids create different logger instances."""
    logger1 = get_session(log_dir=tmp_path, session_id="session1")
    logger2 = get_session(log_dir=tmp_path, session_id="session2")

    # Should be different objects
    assert logger1 is not logger2
    assert logger1.session_id != logger2.session_id


def test_force_new_bypasses_cache(tmp_path):
    """Test that force_new=True creates a new logger even if session_id exists."""
    logger1 = get_session(log_dir=tmp_path, session_id="test_session")

    # force_new should create a new instance
    logger2 = get_session(log_dir=tmp_path, session_id="test_session", force_new=True)

    # Should be different objects
    assert logger1 is not logger2
    assert logger1.session_id == logger2.session_id


def test_force_new_updates_cache(tmp_path):
    """Test that force_new=True updates the cache with the new logger."""
    logger1 = get_session(log_dir=tmp_path, session_id="test_session")

    # force_new creates a new instance and updates cache
    logger2 = get_session(log_dir=tmp_path, session_id="test_session", force_new=True)

    # Third call should return logger2 (the new one)
    logger3 = get_session(log_dir=tmp_path, session_id="test_session")

    assert logger1 is not logger2
    assert logger2 is logger3
    assert logger1 is not logger3


def test_default_session_id(tmp_path):
    """Test that session_id defaults to 'session' when not provided."""
    # When session_id is None, it defaults to "session"
    logger1 = get_session(log_dir=tmp_path)
    assert logger1.session_id == "session"

    # Subsequent calls return the same cached logger
    logger2 = get_session(log_dir=tmp_path)
    assert logger1 is logger2
    assert logger2.session_id == "session"

    # To get a new session without specifying ID, use force_new
    logger3 = get_session(log_dir=tmp_path, force_new=True)
    assert logger1 is not logger3
    assert logger3.session_id == "session"  # Same ID, different instance


def test_cached_logger_retains_bound_context(tmp_path):
    """Test that cached loggers retain their bound context."""
    logger1 = get_session(log_dir=tmp_path, session_id="test_session")
    logger1.bind(user_id="user123", model="gpt-4")

    # Get cached logger
    logger2 = get_session(log_dir=tmp_path, session_id="test_session")

    # Should be same instance with same context
    assert logger1 is logger2

    # Log with the cached logger - should include bound context
    logger2.info("test_event")

    # Verify log file has the bound context (in timestamped directory)
    log_file = logger1.get_session_path() / "events.jsonl"
    assert log_file.exists()

    import json

    with open(log_file) as f:
        lines = f.readlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["user_id"] == "user123"
        assert event["model"] == "gpt-4"
        assert event["event"] == "test_event"


def test_close_session_removes_from_cache(tmp_path):
    """Test that close_session removes the logger from the cache."""
    logger1 = get_session(log_dir=tmp_path, session_id="test_session")

    # Close the logger
    close_session("test_session")

    # Should be removed from cache
    assert "test_session" not in _logger_cache

    # New call should create a new instance
    logger2 = get_session(log_dir=tmp_path, session_id="test_session")

    assert logger1 is not logger2


def test_close_session_closes_file_handlers(tmp_path):
    """Test that close_session properly closes file handlers."""
    logger = get_session(log_dir=tmp_path, session_id="test_session")

    # Log something to create the "events" namespace
    logger.info("test_event")

    # Get the file handler for the "events" namespace from stdlib logger
    stdlib_logger_name = f"{logger._stdlib_logger_base_name}.events"
    stdlib_logger = logging.getLogger(stdlib_logger_name)
    file_handler = stdlib_logger.handlers[0]

    # Verify handler is open before close
    assert file_handler.stream is not None
    assert not file_handler.stream.closed

    # Close the logger
    close_session("test_session")

    # File handler should be closed (stream is set to None after close)
    assert file_handler.stream is None or file_handler.stream.closed


def test_close_session_cleans_up_stdlib_logger(tmp_path):
    """Test that close_session cleans up stdlib logger handlers."""
    logger = get_session(log_dir=tmp_path, session_id="test_session")

    # Log something to create the "events" namespace
    logger.info("test_event")

    # Get the stdlib logger for the "events" namespace
    stdlib_logger_name = f"{logger._stdlib_logger_base_name}.events"
    stdlib_logger = logging.getLogger(stdlib_logger_name)

    # Should have handlers
    assert len(stdlib_logger.handlers) > 0

    # Close the logger
    close_session("test_session")

    # Handlers should be removed
    assert len(stdlib_logger.handlers) == 0


def test_close_session_nonexistent_session(tmp_path):
    """Test that close_session handles non-existent session gracefully."""
    # Should not raise an error
    close_session("nonexistent_session")

    # Cache should still be empty
    assert "nonexistent_session" not in _logger_cache


def test_close_session_and_recreate(tmp_path):
    """Test that we can close a logger and recreate it with same session_id."""
    import json
    import time

    # Create logger and log something
    logger1 = get_session(log_dir=tmp_path, session_id="test_session")
    logger1.info("first_event")
    log_file1 = logger1.get_session_path() / "events.jsonl"

    # Close it
    close_session("test_session")

    # Wait to ensure different timestamp
    time.sleep(1.1)

    # Create new logger with same session_id (creates new timestamped directory)
    logger2 = get_session(log_dir=tmp_path, session_id="test_session")

    # Should be a different instance
    assert logger1 is not logger2

    # Log with new logger
    logger2.info("second_event")
    log_file2 = logger2.get_session_path() / "events.jsonl"

    # Should have different log files (different timestamped directories)
    assert log_file1 != log_file2

    # First log file should have first event only
    with open(log_file1) as f:
        lines = f.readlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["event"] == "first_event"

    # Second log file should have second event only
    with open(log_file2) as f:
        lines = f.readlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["event"] == "second_event"


def test_cache_survives_bind_and_unbind(tmp_path):
    """Test that bind and unbind don't affect cache identity."""
    logger1 = get_session(log_dir=tmp_path, session_id="test_session")

    # Bind some context
    result = logger1.bind(user_id="user123")

    # bind returns self for chaining
    assert result is logger1

    # Getting logger again should still return the same instance
    logger2 = get_session(log_dir=tmp_path, session_id="test_session")
    assert logger1 is logger2

    # Unbind
    result = logger1.unbind("user_id")
    assert result is logger1

    # Still same instance
    logger3 = get_session(log_dir=tmp_path, session_id="test_session")
    assert logger1 is logger3


def test_multiple_loggers_cached_independently(tmp_path):
    """Test that multiple loggers are cached independently."""
    logger1 = get_session(log_dir=tmp_path, session_id="session1")
    logger2 = get_session(log_dir=tmp_path, session_id="session2")
    logger3 = get_session(log_dir=tmp_path, session_id="session3")

    # All should be in cache
    assert "session1" in _logger_cache
    assert "session2" in _logger_cache
    assert "session3" in _logger_cache

    # Retrieving should return same instances
    assert logger1 is get_session(log_dir=tmp_path, session_id="session1")
    assert logger2 is get_session(log_dir=tmp_path, session_id="session2")
    assert logger3 is get_session(log_dir=tmp_path, session_id="session3")


def test_close_one_logger_doesnt_affect_others(tmp_path):
    """Test that closing one logger doesn't affect other cached loggers."""
    logger1 = get_session(log_dir=tmp_path, session_id="session1")
    get_session(log_dir=tmp_path, session_id="session2")
    logger3 = get_session(log_dir=tmp_path, session_id="session3")

    # Close logger2
    close_session("session2")

    # logger1 and logger3 should still be in cache
    assert "session1" in _logger_cache
    assert "session2" not in _logger_cache
    assert "session3" in _logger_cache

    # Retrieving should still work for 1 and 3
    assert logger1 is get_session(log_dir=tmp_path, session_id="session1")
    assert logger3 is get_session(log_dir=tmp_path, session_id="session3")


def test_registry_pattern_usage(tmp_path):
    """Test the stdlib-like registry pattern in action."""
    import json

    # First call anywhere in app
    logger = get_session(log_dir=tmp_path, session_id="main")
    logger.bind(app_version="1.0.0")
    logger.info("app_started")

    # Later, in different part of code - no need for globals!
    logger2 = get_session(session_id="main")  # Returns cached instance
    assert logger is logger2

    # Still has the bound context
    logger2.info("processing_request")

    # Verify both events have the bound context (in timestamped directory)
    log_file = logger.get_session_path() / "events.jsonl"

    with open(log_file) as f:
        lines = f.readlines()
        assert len(lines) == 2
        event1 = json.loads(lines[0])
        event2 = json.loads(lines[1])

        assert event1["app_version"] == "1.0.0"
        assert event1["event"] == "app_started"

        assert event2["app_version"] == "1.0.0"
        assert event2["event"] == "processing_request"


def test_processors_parameter_with_cache(tmp_path):
    """Test that processors parameter is only used on first call."""
    import json

    def custom_processor(logger, method_name, event_dict):
        event_dict["custom_flag"] = True
        return event_dict

    # First call with processors
    logger1 = get_session(
        log_dir=tmp_path, session_id="test_session", processors=[custom_processor]
    )
    logger1.info("test1")

    # Second call without processors (should return cached logger)
    logger2 = get_session(log_dir=tmp_path, session_id="test_session")
    logger2.info("test2")

    # Should be same instance
    assert logger1 is logger2

    # Both logs should have custom_flag (because it's the same logger)
    log_file = logger1.get_session_path() / "events.jsonl"

    with open(log_file) as f:
        lines = f.readlines()
        event1 = json.loads(lines[0])
        event2 = json.loads(lines[1])

        assert event1["custom_flag"] is True
        assert event2["custom_flag"] is True


def test_context_manager_with_cache(tmp_path):
    """Test that context manager works with cached loggers."""
    # First use with context manager
    with get_session(log_dir=tmp_path, session_id="test_session") as logger1:
        logger1.info("event1")
        log_path = logger1.get_session_path()

    # Second use - should get cached logger
    with get_session(log_dir=tmp_path, session_id="test_session") as logger2:
        logger2.info("event2")

    # Should be same instance
    assert logger1 is logger2

    # Both events should be logged
    log_file = log_path / "events.jsonl"

    with open(log_file) as f:
        lines = f.readlines()
        assert len(lines) == 2


def test_cache_key_is_session_id_only(tmp_path, tmp_path_factory):
    """Test that cache key is based only on session_id, not other parameters."""
    tmp_path2 = tmp_path_factory.mktemp("logs2")

    # Create logger with specific log_dir
    logger1 = get_session(log_dir=tmp_path, session_id="test_session")
    session_path1 = logger1.get_session_path()

    # Get logger with different log_dir but same session_id
    logger2 = get_session(log_dir=tmp_path2, session_id="test_session")

    # Should return cached logger (log_dir is ignored on cache hit)
    assert logger1 is logger2

    # Should still use original log_dir (timestamped directory under tmp_path)
    assert logger1.get_session_path() == session_path1
    assert logger2.get_session_path() == session_path1
    assert str(session_path1).startswith(str(tmp_path / "test_session_"))
