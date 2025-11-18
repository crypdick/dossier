"""Data models for session logging"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class LogLevel(Enum):
    """Log levels for filtering output"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class LogEntry:
    """A single log entry with metadata"""

    timestamp: float
    timestamp_iso: str
    level: str
    event_type: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization (without session_id - it's redundant with directory)"""
        return asdict(self)


@dataclass
class SessionMetadata:
    """Metadata about a logging session"""

    session_id: str
    start_time: float
    start_time_iso: str
    model: str
    mode: str | None = None
    end_time: float | None = None
    end_time_iso: str | None = None
    total_duration: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
