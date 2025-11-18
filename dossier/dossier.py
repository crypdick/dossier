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

# Track if structlog has been configured globally
_structlog_configured = False


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
        session_id: str,
        session_dir: Path,
        stdlib_logger_base_name: str,
        processors: list[Any] | None = None,
    ) -> None:
        """Internal initialization - use get_session() instead."""
        self.session_id = session_id
        self.session_dir = session_dir
        self._stdlib_logger_base_name = stdlib_logger_base_name
        self._processors = processors or []
        self._namespaced_loggers: dict[str, Any] = {}

    def _resolve_namespace(self, namespace: str | None) -> str:
        """Resolve namespace to a canonical string, defaulting to 'events'."""
        return "events" if not namespace else namespace

    def _get_namespaced_logger(self, namespace: str | None) -> Any | None:
        """Get a namespaced logger if it exists, return None otherwise."""
        resolved = self._resolve_namespace(namespace)
        return self._namespaced_loggers.get(resolved)

    def _set_namespaced_logger(self, namespace: str | None, logger: Any) -> None:
        """Set/update a namespaced logger in the cache."""
        resolved = self._resolve_namespace(namespace)
        self._namespaced_loggers[resolved] = logger

    def _get_or_create_namespaced_logger(self, namespace: str | None) -> Any:
        """Get or create a namespaced logger for routing logs to a separate file."""
        # Return cached logger if it exists
        cached = self._get_namespaced_logger(namespace)
        if cached is not None:
            return cached

        # Create new namespaced logger
        resolved = self._resolve_namespace(namespace)
        log_file = self.session_dir / f"{resolved}.jsonl"
        stdlib_logger_name = f"{self._stdlib_logger_base_name}.{resolved}"

        structlog_logger = _create_logger_infrastructure(
            log_file=log_file,
            stdlib_logger_name=stdlib_logger_name,
            processors=self._processors,
        )

        # Cache the logger using the setter
        self._set_namespaced_logger(namespace, structlog_logger)
        return structlog_logger

    def _route_log(
        self, method_name: str, event: str | Any | None, **kwargs: Any
    ) -> Any:
        """Route log to appropriate logger based on namespace kwarg."""
        namespace = kwargs.pop("namespace", None)
        logger = self._get_or_create_namespaced_logger(namespace)

        # Call the appropriate log method
        log_method = getattr(logger, method_name)
        return log_method(event, **kwargs)

    @infer_event
    def info(self, event: str | Any | None = None, **kwargs: Any) -> Any:
        """Log info-level event."""
        return self._route_log("info", event, **kwargs)

    @infer_event
    def error(self, event: str | Any | None = None, **kwargs: Any) -> Any:
        """Log error-level event."""
        return self._route_log("error", event, **kwargs)

    @infer_event
    def debug(self, event: str | Any | None = None, **kwargs: Any) -> Any:
        """Log debug-level event."""
        return self._route_log("debug", event, **kwargs)

    @infer_event
    def warning(self, event: str | Any | None = None, **kwargs: Any) -> Any:
        """Log warning-level event"""
        return self._route_log("warning", event, **kwargs)

    def bind(self, namespace: str | None = None, **kwargs: Any) -> "Dossier":
        """Add context to logger for subsequent log calls.

        Example:
            logger.bind(request_id="abc-123", user_id="user_456")
            logger.info("processing_request")
            # Includes: request_id="abc-123", user_id="user_456"

            # Bind to specific namespace:
            logger.bind(worker_id="w1", namespace="worker")
            logger.info("task", namespace="worker")  # Has worker_id="w1"
        """
        bound_logger = self._get_or_create_namespaced_logger(namespace).bind(**kwargs)

        self._set_namespaced_logger(namespace, bound_logger)
        return self

    def unbind(self, *keys: str, namespace: str | None = None) -> "Dossier":
        """Remove context keys from logger.

        Example:
            logger.bind(request_id="123", user_id="456")
            logger.info("test")  # Has both

            logger.unbind("request_id")
            logger.info("test2")  # Only has user_id

            # Unbind from specific namespace:
            logger.unbind("worker_id", namespace="worker")
        """
        # Get or create the logger for this namespace (defaults to "events" if None)
        unbound_logger = self._get_or_create_namespaced_logger(namespace).unbind(*keys)

        self._set_namespaced_logger(namespace, unbound_logger)
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


def _ensure_structlog_configured() -> None:
    """Configure structlog once globally if not already configured."""
    global _structlog_configured

    if _structlog_configured:
        return

    processor_chain: list[Any] = [
        unpack_dataclasses,
        unpack_pydantic_models,
        unpack_generic_objects,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        make_json_safe,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processor_chain,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _structlog_configured = True


def _create_logger_infrastructure(
    log_file: Path,
    stdlib_logger_name: str,
    processors: list[Any] | None = None,
) -> Any:
    """Create a logger for a specific namespace."""
    _ensure_structlog_configured()

    # Set up file handler
    handler = logging.FileHandler(log_file)
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Configure standard library logger
    stdlib_logger = logging.getLogger(stdlib_logger_name)
    stdlib_logger.handlers.clear()
    stdlib_logger.addHandler(handler)
    stdlib_logger.setLevel(logging.DEBUG)
    stdlib_logger.propagate = False

    # Get base structlog logger (uses global config)
    base_logger = structlog.get_logger(stdlib_logger_name)

    # If custom processors provided, wrap the logger with them
    if processors:
        return structlog.wrap_logger(
            base_logger,
            wrapper_class=structlog.stdlib.BoundLogger,
            processors=processors,
        )

    return base_logger


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

    **Namespaced Logging:**
    Use the `namespace` kwarg on logging methods to route logs to separate files:
    ```python
    logger = get_session(session_id="main")
    logger.info("event")  # logs to events.jsonl
    logger.info("event", namespace="worker")  # logs to worker.jsonl
    logger.info("event", namespace="api.requests")  # logs to api.requests.jsonl
    ```

    Args:
        log_dir: Directory to store log files
        session_id: Simple session identifier (e.g., "main", "worker"). If None, defaults
                   to "session".
        processors: Optional list of custom structlog processors
        force_new: If True, creates new timestamped log directory even if session_id exists
                  in cache. Useful for restarting sessions with same name.

    Returns:
        Started Dossier instance (either cached or newly created)

    Example:
        # Simple session ID, timestamped directory created automatically
        logger = get_session(session_id="main")
        # Logs to: logs/main_TIMESTAMP/events.jsonl

        # Subsequent calls return the same instance
        logger2 = get_session(session_id="main")
        assert logger is logger2

        # Namespaced logging - single logger, multiple files
        logger.info("event", namespace="worker")  # logs to main_TIMESTAMP/worker.jsonl

        # Force new session - creates new timestamped directory
        logger3 = get_session(session_id="main", force_new=True)
        # Logs to: logs/main_MEW_TIMESTAMP/events.jsonl
        # Now logger3 is cached under "main"


        # With context manager
        with get_session(session_id="task1") as logger:
            logger.info("log to temporary session")
    """
    # Convert to Path
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)

    # Default session ID if not provided
    if session_id is None:
        # If there's exactly one session in cache and not forcing new, return it (common use case)
        if not force_new and len(_logger_cache) == 1:
            return cast(Dossier, next(iter(_logger_cache.values())))
        # Otherwise default to "session"
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

    # Set up base stdlib logger name (namespaces will be added to this)
    stdlib_logger_base_name = f"session.{timestamped_dir_name}"

    # Create Dossier wrapper (loggers created lazily on first use)
    dossier = Dossier(
        session_id=session_id,
        session_dir=session_dir,
        stdlib_logger_base_name=stdlib_logger_base_name,
        processors=processors,
    )

    # Cache before returning (using user-facing session_id as key)
    _logger_cache[session_id] = dossier

    return dossier


def close_session(session_id: str) -> None:
    """Close session and all the namespaced loggers."""
    if session_id in _logger_cache:
        dossier = _logger_cache.pop(session_id)

        # Close all namespaced loggers (including "events")
        for namespace in dossier._namespaced_loggers:
            # Get the stdlib logger and close its handlers
            stdlib_logger_name = f"{dossier._stdlib_logger_base_name}.{namespace}"
            stdlib_logger = logging.getLogger(stdlib_logger_name)
            for handler in stdlib_logger.handlers[:]:
                handler.close()
                stdlib_logger.removeHandler(handler)


# Backward compatibility aliases
get_logger = get_session
close_logger = close_session
