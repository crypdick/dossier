"""Pytest fixtures for all tests."""

import json
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from dossier import get_session
from dossier.dossier import Dossier


@pytest.fixture
def test_logger() -> Generator[Dossier]:
    """
    Provide a fresh logger with randomized session ID and temp directory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        session_id = f"test_{uuid.uuid4().hex[:8]}"
        logger = get_session(log_dir=tmpdir, session_id=session_id)
        yield logger


def read_jsonl_logs(session_dir: Path) -> list[dict[str, Any]]:
    """
    Read and parse all JSONL log entries from a session directory.
    """
    log_file = session_dir / "events.jsonl"
    logs = []
    with open(log_file) as f:
        for line in f:
            logs.append(json.loads(line))
    return logs
