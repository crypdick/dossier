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
    ) -> None:
        """Internal initialization - use get_logger() instead."""
        self._logger = logger
        self.session_id = session_id
        self.session_dir = session_dir
        self._file_handler = file_handler

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


def get_logger(
    log_dir: str | Path = "logs",
    session_prefix: str = "session_",
    session_id: str | None = None,
    processors: list[Any] | None = None,
    force_new: bool = False,
) -> Dossier:
    """
    Get or create a dossier logger. Returns existing logger if session_id already exists.

    Similar to logging.getLogger(name), this function caches logger instances by session_id.
    Subsequent calls with the same session_id return the cached instance.

    Args:
        log_dir: Directory to store log files
        session_prefix: Prefix for session directory names
        session_id: Optional session ID (auto-generated if None). Used as cache key.
        processors: Optional list of custom structlog processors
        force_new: If True, creates new logger even if session_id exists in cache

    Returns:
        Started Dossier instance (either cached or newly created)

    Example:
        # Basic usage - first call creates it
        logger = get_logger(session_id="main")
        logger.bind(model="gpt-4", user_id="user_123")
        logger.info("user_message", content="Hello")

        # Subsequent calls return the same instance
        logger2 = get_logger(session_id="main")
        assert logger is logger2  # True!

        # Force a new logger even with same session_id
        logger3 = get_logger(session_id="main", force_new=True)
        assert logger is not logger3  # True

        # With custom processors
        def add_hostname(logger, method_name, event_dict):
            import socket
            event_dict["hostname"] = socket.gethostname()
            return event_dict

        logger = get_logger(
            session_id="production",
            log_dir="logs",
            processors=[add_hostname],
        )

        # With context manager
        with get_logger(session_id="task1") as logger:
            logger.bind(model="gpt-4")
            logger.info("test_event")
    """
    # Convert to Path
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    # Generate session ID if not provided
    now = datetime.now()
    if session_id is None:
        session_id = f"{session_prefix}{now.strftime('%Y%m%d_%H%M%S')}"

    # Return cached logger if exists (unless force_new)
    if not force_new and session_id in _logger_cache:
        return cast(Dossier, _logger_cache[session_id])

    session_dir = log_dir_path / session_id
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

    # Configure standard library logger
    stdlib_logger_name = f"session.{session_id}"
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
    )

    # Cache before returning
    _logger_cache[session_id] = dossier

    return dossier


def close_logger(session_id: str) -> None:
    """
    Close and remove logger from cache.

    This properly closes file handlers and removes the logger from the cache.
    Useful for cleanup or when you want to start fresh with the same session_id.

    Args:
        session_id: The session ID of the logger to close

    Example:
        logger = get_logger(session_id="main")
        logger.info("test_event")

        # Clean up when done
        close_logger("main")

        # Now get_logger will create a fresh instance
        logger2 = get_logger(session_id="main")
        assert logger is not logger2  # True
    """
    if session_id in _logger_cache:
        logger = _logger_cache.pop(session_id)
        # Close file handler
        logger._file_handler.close()

        # Clean up stdlib logger handlers
        stdlib_logger_name = f"session.{session_id}"
        stdlib_logger = logging.getLogger(stdlib_logger_name)
        for handler in stdlib_logger.handlers[:]:
            handler.close()
            stdlib_logger.removeHandler(handler)
