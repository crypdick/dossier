import functools
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import structlog

from dossier.processors import (
    make_json_safe,
    unpack_dataclasses,
    unpack_generic_objects,
    unpack_pydantic_models,
)

# Module-level cache for logger instances (similar to logging.getLogger)
_logger_cache: dict[str, Any] = {}


def _infer_event_type_from_object(obj: Any) -> str | None:
    """Infer event type from object class name."""
    if isinstance(obj, (str, int, float, bool, type(None), list, tuple, dict)):
        return None
    return type(obj).__name__


def infer_event(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator that handles event type inference from objects.

    If the first arg (event) is an object (not a string):
    - Infers event type from class name
    - Adds object to kwargs as "_obj" for unpacking processor
    - Calls the underlying method with inferred event type
    """

    @functools.wraps(func)
    def wrapper(self: "Dossier", event: str | Any | None = None, **kwargs: Any) -> Any:
        # Handle event type inference
        if event is not None and not isinstance(event, str):
            # Event is an object - infer type
            inferred = _infer_event_type_from_object(event)
            if inferred is None:
                raise ValueError(
                    "Must provide event type string or object with inferrable type"
                )
            kwargs["_obj"] = event
            event = inferred
        elif event is None:
            raise ValueError("Must provide event string or object")

        # Call the original method
        return func(self, event, **kwargs)

    return wrapper


class Dossier:
    """
    Session-based structured logger with smart object unpacking and flexible metadata.

    Wraps structlog for session management and automatic object unpacking.
    """

    def __init__(
        self,
        logger: Any,  # structlog bound logger (stdlib or generic)
        session_id: str,
        session_dir: Path,
        file_handler: logging.FileHandler,
        stdlib_logger_name: str,
    ) -> None:
        """Internal initialization - use get_session() instead."""
        self._logger = logger
        self.session_id = session_id
        self.session_dir = session_dir
        self._file_handler = file_handler
        self._stdlib_logger_name = stdlib_logger_name

    @infer_event
    def info(self, event: str | Any | None = None, **kwargs: Any) -> Any:
        """Log info-level event with auto-unpacking and event type inference."""
        return self._logger.info(event, **kwargs)

    @infer_event
    def error(self, event: str | Any | None = None, **kwargs: Any) -> Any:
        """Log error-level event with auto-unpacking and event type inference."""
        return self._logger.error(event, **kwargs)

    @infer_event
    def debug(self, event: str | Any | None = None, **kwargs: Any) -> Any:
        """Log debug-level event with auto-unpacking and event type inference."""
        return self._logger.debug(event, **kwargs)

    @infer_event
    def warning(self, event: str | Any | None = None, **kwargs: Any) -> Any:
        """Log warning-level event with auto-unpacking and event type inference."""
        return self._logger.warning(event, **kwargs)

    def bind(self, **kwargs: Any) -> "Dossier":
        """
        Add context to logger for subsequent log calls.

        Note: this modifies this logger instance and returns self for chaining.

        Example:
            logger.bind(request_id="abc-123", user_id="user_456")
            logger.info("processing_request")
            # Includes: request_id="abc-123", user_id="user_456"

            # Or chain it:
            logger.bind(request_id="123").bind(user_id="456").info("test")
        """
        self._logger = self._logger.bind(**kwargs)
        return self

    def unbind(self, *keys: str) -> "Dossier":
        """
        Remove context keys from logger.

        Note: this modifies this logger instance and returns self for chaining.

        Example:
            logger.bind(request_id="123", user_id="456")
            logger.info("test")  # Has both

            logger.unbind("request_id")
            logger.info("test2")  # Only has user_id

            # Or chain it:
            logger.unbind("request_id", "user_id").info("test3")
        """
        self._logger = self._logger.unbind(*keys)
        return self

    def get_session_path(self) -> Path:
        """Get the path to the current session directory."""
        return self.session_dir

    def get_session_id(self) -> str:
        """Get the current session ID."""
        return self.session_id

    def __enter__(self) -> "Dossier":
        return self

    def __exit__(
        self, exc_type: object | None, exc_val: object | None, exc_tb: object | None
    ) -> None:
        pass  # Needed for context manager


def get_session(
    log_dir: str | Path = "logs",
    session_id: str | None = None,
    processors: list[Any] | None = None,
    force_new: bool = False,
) -> Dossier:
    """
    Get or create a dossier logging session. Returns existing session if session_id already exists.

    Similar to logging.getLogger(name), this function caches session instances by session_id.
    Subsequent calls with the same session_id return the cached instance.

    The session_id is user-facing and simple (e.g., "main", "production"), while the actual
    log directory is timestamped (e.g., "main_20251118_120000/"). This allows easy session
    retrieval while maintaining chronological organization of log files.

    Args:
        log_dir: Directory to store log files
        session_id: Simple session identifier (e.g., "main", "worker"). If None, defaults
                   to "session". Used as cache key.
        processors: Optional list of custom structlog processors
        force_new: If True, creates new timestamped log directory even if session_id exists
                  in cache. Useful for restarting sessions with same name.

    Returns:
        Started Dossier instance (either cached or newly created)

    Example:
        # Simple session ID, timestamped directory created automatically
        logger = get_session(session_id="main")
        # Creates: logs/main_20251118_120000/events.jsonl

        # Subsequent calls return the same instance
        logger2 = get_session(session_id="main")
        assert logger is logger2  # True! No timestamp needed.

        # Force new session - creates new timestamped directory
        logger3 = get_session(session_id="main", force_new=True)
        # Creates: logs/main_20251118_130000/events.jsonl
        # Now logger3 is cached under "main"

        logger4 = get_session(session_id="main")
        assert logger3 is logger4  # Returns the newer instance

        # With context manager
        with get_session(session_id="task1") as logger:
            logger.bind(model="gpt-4")
            logger.info("test_event")
    """
    # Convert to Path
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    # Default session ID if not provided
    if session_id is None:
        session_id = "session"

    # Return cached logger if exists (unless force_new)
    if not force_new and session_id in _logger_cache:
        return cast(Dossier, _logger_cache[session_id])

    # Create timestamped directory name (session_id + underscore + timestamp)
    now = datetime.now()
    timestamp_suffix = now.strftime("%Y%m%d_%H%M%S")
    timestamped_dir_name = f"{session_id}_{timestamp_suffix}"
    session_dir = log_dir_path / timestamped_dir_name
    session_dir.mkdir(parents=True, exist_ok=True)

    # Prepare session metadata with timestamp
    metadata = {
        "session_id": session_id,
        "start_time": now.isoformat(),
    }

    # Set up file handler for JSON output
    log_file = session_dir / "events.jsonl"
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Configure standard library logger (use timestamped name to avoid conflicts)
    stdlib_logger_name = f"session.{timestamped_dir_name}"
    stdlib_logger = logging.getLogger(stdlib_logger_name)
    stdlib_logger.handlers.clear()
    stdlib_logger.addHandler(handler)
    stdlib_logger.setLevel(logging.DEBUG)
    stdlib_logger.propagate = False

    # Build processor chain
    custom_procs = processors or []
    processor_chain = [
        *custom_procs,  # User's custom processors go first
        unpack_dataclasses,
        unpack_pydantic_models,
        unpack_generic_objects,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        make_json_safe,
        structlog.processors.JSONRenderer(),
    ]

    # Configure structlog
    structlog.configure(
        processors=processor_chain,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,  # Allow reconfiguration per session
    )

    # Get logger and bind session metadata
    structlog_logger = structlog.get_logger(stdlib_logger_name).bind(**metadata)

    # Create Dossier wrapper
    dossier = Dossier(
        logger=structlog_logger,
        session_id=session_id,
        session_dir=session_dir,
        file_handler=handler,
        stdlib_logger_name=stdlib_logger_name,
    )

    # Cache before returning (using user-facing session_id as key)
    _logger_cache[session_id] = dossier

    return dossier


def close_session(session_id: str) -> None:
    """
    Close and remove session from cache.

    This properly closes file handlers and removes the session from the cache.
    Useful for cleanup or when you want to start fresh with the same session_id.

    Args:
        session_id: The session ID of the session to close

    Example:
        logger = get_session(session_id="main")
        logger.info("test_event")

        # Clean up when done
        close_session("main")

        # Now get_session will create a fresh instance
        logger2 = get_session(session_id="main")
        assert logger is not logger2  # True
    """
    if session_id in _logger_cache:
        logger = _logger_cache.pop(session_id)
        # Close file handler
        logger._file_handler.close()

        # Clean up stdlib logger handlers (use the stored stdlib logger name)
        stdlib_logger = logging.getLogger(logger._stdlib_logger_name)
        for handler in stdlib_logger.handlers[:]:
            handler.close()
            stdlib_logger.removeHandler(handler)


# Backward compatibility aliases
get_logger = get_session
close_logger = close_session
