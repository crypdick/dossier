from beartype.claw import beartype_this_package

# Enable beartype runtime type-checking for all modules in this package
beartype_this_package()

# Export session_logger module
from dossier.session_logger import (  # noqa: E402
    LogEntry,
    LogLevel,
    SessionLogger,
    SessionMetadata,
    create_logger,
)

__all__ = [
    "SessionLogger",
    "create_logger",
    "LogEntry",
    "LogLevel",
    "SessionMetadata",
]
