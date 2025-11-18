"""Test namespaced logging functionality via namespace kwarg."""

import json

import pytest

from dossier import close_session, get_session
from dossier.dossier import _logger_cache


@pytest.fixture(autouse=True)
def clear_cache(tmp_path):
    """Clear logger cache before and after each test."""
    _logger_cache.clear()
    yield
    _logger_cache.clear()


def test_namespace_kwarg_creates_separate_file(tmp_path):
    """Test that namespace kwarg routes logs to a separate file."""
    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    # Log to different namespaces
    logger.info("parent_event")
    logger.info("worker_event", namespace="worker")

    # Check files exist
    main_log = session_dir / "events.jsonl"
    worker_log = session_dir / "worker.jsonl"

    assert main_log.exists()
    assert worker_log.exists()

    # Main log should only have main event
    with open(main_log) as f:
        lines = f.readlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event"] == "parent_event"

    # Worker log should only have worker event
    with open(worker_log) as f:
        lines = f.readlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["event"] == "worker_event"


def test_multiple_namespaces(tmp_path):
    """Test multiple namespaces under same session."""
    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    # Log to multiple namespaces
    logger.info("main_event")
    logger.info("worker_event", namespace="worker")
    logger.info("api_event", namespace="api")
    logger.info("metrics_event", namespace="metrics")

    # Check all files exist
    assert (session_dir / "events.jsonl").exists()
    assert (session_dir / "worker.jsonl").exists()
    assert (session_dir / "api.jsonl").exists()
    assert (session_dir / "metrics.jsonl").exists()

    # Each file should have correct content
    with open(session_dir / "worker.jsonl") as f:
        event = json.loads(f.read())
        assert event["event"] == "worker_event"


def test_nested_namespace_dots_in_filename(tmp_path):
    """Test that dots in namespace are preserved in filename."""
    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    # Log with dotted namespace
    logger.info("nested_event", namespace="api.requests")

    # File should preserve dots in filename
    nested_log = session_dir / "api.requests.jsonl"
    assert nested_log.exists()

    with open(nested_log) as f:
        event = json.loads(f.read())
        assert event["event"] == "nested_event"


def test_namespace_lazy_creation(tmp_path):
    """Test that namespaced loggers are created lazily on first use."""
    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    # No namespaced files should exist yet
    assert not (session_dir / "worker.jsonl").exists()

    # Log with namespace - file should now be created
    logger.info("event", namespace="worker")
    assert (session_dir / "worker.jsonl").exists()

    # Second log to same namespace should reuse the logger
    logger.info("event2", namespace="worker")

    with open(session_dir / "worker.jsonl") as f:
        lines = f.readlines()
        assert len(lines) == 2


def test_namespace_with_kwargs(tmp_path):
    """Test that namespace kwarg works with other kwargs."""
    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    # Log to main with context
    logger.info("main_event", app="myapp", version="1.0")

    # Log to namespaced with different context
    logger.info("worker_event", namespace="worker", worker_id="w1", task="processing")

    # Main log should have its context
    with open(session_dir / "events.jsonl") as f:
        event = json.loads(f.read())
        assert event["app"] == "myapp"
        assert event["version"] == "1.0"
        assert "worker_id" not in event

    # Namespaced log should have its own context
    with open(session_dir / "worker.jsonl") as f:
        event = json.loads(f.read())
        assert event["worker_id"] == "w1"
        assert event["task"] == "processing"
        assert "app" not in event  # Namespaces are independent


def test_close_session_closes_all_namespaces(tmp_path):
    """Test that closing session closes all namespaced handlers."""
    logger = get_session(log_dir=tmp_path, session_id="session")

    # Log to multiple namespaces
    logger.info("main", namespace="worker")
    logger.info("api", namespace="api")

    # Close session
    close_session("session")

    # Session should be removed from cache
    assert "session" not in _logger_cache


def test_namespace_with_different_log_levels(tmp_path):
    """Test that namespace works with different log levels."""
    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    # Different log levels with namespace
    logger.info("info_event", namespace="worker")
    logger.error("error_event", namespace="worker")
    logger.debug("debug_event", namespace="worker")
    logger.warning("warning_event", namespace="worker")

    # All should go to worker.jsonl
    with open(session_dir / "worker.jsonl") as f:
        lines = f.readlines()
        assert len(lines) == 4

        events = [json.loads(line) for line in lines]
        assert events[0]["level"] == "info"
        assert events[1]["level"] == "error"
        assert events[2]["level"] == "debug"
        assert events[3]["level"] == "warning"


def test_namespace_not_in_final_log(tmp_path):
    """Test that namespace kwarg is not included in the logged event."""
    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    logger.info("event", namespace="worker", extra_field="value")

    with open(session_dir / "worker.jsonl") as f:
        event = json.loads(f.read())
        # namespace kwarg should be stripped out
        assert "namespace" not in event
        # but other kwargs should be present
        assert event["extra_field"] == "value"


def test_namespace_with_object_unpacking(tmp_path):
    """Test that namespace works with object event inference."""
    from dataclasses import dataclass

    @dataclass
    class Task:
        task_id: str
        status: str

    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    task = Task(task_id="task-123", status="completed")
    logger.info(task, namespace="worker")

    with open(session_dir / "worker.jsonl") as f:
        event = json.loads(f.read())
        assert event["event"] == "Task"
        assert event["task_id"] == "task-123"
        assert event["status"] == "completed"


def test_session_id_access(tmp_path):
    """Test that session_id is accessible."""
    logger = get_session(log_dir=tmp_path, session_id="main")
    assert logger.get_session_id() == "main"


def test_context_manager_with_namespaces(tmp_path):
    """Test context manager works with namespaced logging."""
    with get_session(log_dir=tmp_path, session_id="session") as logger:
        logger.info("main_event")
        logger.info("worker_event", namespace="worker")

    # Both files should exist
    session_dir = logger.get_session_path()
    assert (session_dir / "events.jsonl").exists()
    assert (session_dir / "worker.jsonl").exists()


def test_namespace_with_custom_processors(tmp_path):
    """Test that namespaced loggers use the same processors."""

    def add_custom_field(logger, method_name, event_dict):
        event_dict["custom"] = "value"
        return event_dict

    logger = get_session(
        log_dir=tmp_path, session_id="session", processors=[add_custom_field]
    )
    session_dir = logger.get_session_path()

    # Log to main and namespace
    logger.info("main_event")
    logger.info("worker_event", namespace="worker")

    # Both should have custom processor applied
    with open(session_dir / "events.jsonl") as f:
        event = json.loads(f.read())
        assert event["custom"] == "value"

    with open(session_dir / "worker.jsonl") as f:
        event = json.loads(f.read())
        assert event["custom"] == "value"


def test_force_new_creates_new_session(tmp_path):
    """Test that force_new creates fresh session with empty namespaces."""
    import time

    logger1 = get_session(log_dir=tmp_path, session_id="session")
    logger1.info("event", namespace="worker")

    # Wait for timestamp difference
    time.sleep(1.1)

    # Force new session
    logger2 = get_session(log_dir=tmp_path, session_id="session", force_new=True)

    # Should be different instances with different paths
    assert logger1 is not logger2
    assert logger1.get_session_path() != logger2.get_session_path()


def test_caching_works_correctly(tmp_path):
    """Test that session caching still works."""
    logger1 = get_session(log_dir=tmp_path, session_id="session")
    logger2 = get_session(log_dir=tmp_path, session_id="session")

    # Should be same instance
    assert logger1 is logger2


def test_multiple_sessions_independent_namespaces(tmp_path):
    """Test that different sessions have independent namespaces."""
    logger1 = get_session(log_dir=tmp_path, session_id="session1")
    logger2 = get_session(log_dir=tmp_path, session_id="session2")

    logger1.info("event1", namespace="worker")
    logger2.info("event2", namespace="worker")

    # Should be in different directories
    dir1 = logger1.get_session_path()
    dir2 = logger2.get_session_path()

    assert dir1 != dir2
    assert (dir1 / "worker.jsonl").exists()
    assert (dir2 / "worker.jsonl").exists()


def test_empty_namespace_string(tmp_path):
    """Test that empty string namespace goes to main logger."""
    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    # Empty namespace should go to main logger
    logger.info("event", namespace="")

    # Should not create a .jsonl file (empty string = main logger)
    assert not (session_dir / ".jsonl").exists()

    # Should go to main events.jsonl
    with open(session_dir / "events.jsonl") as f:
        event = json.loads(f.read())
        assert event["event"] == "event"


def test_none_namespace_goes_to_main(tmp_path):
    """Test that None namespace goes to main logger."""
    logger = get_session(log_dir=tmp_path, session_id="session")
    session_dir = logger.get_session_path()

    logger.info("event", namespace=None)

    # Should go to main events.jsonl
    with open(session_dir / "events.jsonl") as f:
        event = json.loads(f.read())
        assert event["event"] == "event"
