"""Portable session logger for AI agent interactions."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from .formatters import format_data_for_text, make_json_safe
from .models import LogEntry, LogLevel, SessionMetadata

# Import settings and cost tracker for automatic management
try:
    from anki_card_refiner.cost_tracker import (  # type: ignore[import-not-found]
        cost_tracker,
    )
    from anki_card_refiner.settings import (  # type: ignore[import-not-found]
        get_settings,
    )

    _HAS_INTEGRATIONS = True
except ImportError:
    _HAS_INTEGRATIONS = False


class SessionLogger:
    """Logger for AI agent sessions with JSON and text output."""

    def __init__(
        self,
        log_dir: str | Path = "logs",
        session_prefix: str = "session",
        log_level: LogLevel = LogLevel.INFO,
        auto_flush: bool = True,
        pretty_json: bool = True,
    ):
        self.log_dir = Path(log_dir)
        self.session_prefix = session_prefix
        self.log_level = log_level
        self.auto_flush = auto_flush
        self.pretty_json = pretty_json

        self.session_id: str | None = None
        self.session_dir: Path | None = None
        self.session_metadata: SessionMetadata | None = None
        self.log_entries: list[LogEntry] = []

        self._json_file: TextIO | None = None
        self._text_file: TextIO | None = None

        self.log_dir.mkdir(parents=True, exist_ok=True)

    def start_session(
        self,
        model: str | None = None,
        mode: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Start a new logging session."""
        if self.session_id:
            self.end_session()

        # Auto-detect model from settings if not provided
        if model is None and _HAS_INTEGRATIONS:
            model = get_settings().openai_model

        # Start cost tracking if available
        if _HAS_INTEGRATIONS and model is not None:
            cost_tracker.start_call(model=model)

        # Generate session ID
        now = datetime.now()
        if session_id is None:
            session_id = f"{self.session_prefix}_{now.strftime('%Y%m%d_%H%M%S')}"

        self.session_id = session_id
        self.session_dir = self.log_dir / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Initialize metadata
        if model is None:
            raise ValueError("Model must be provided or available from settings")
        self.session_metadata = SessionMetadata(
            session_id=session_id,
            start_time=time.time(),
            start_time_iso=now.isoformat(),
            model=model,
            mode=mode,
        )

        # Open log files
        self._json_file = open(self.session_dir / "events.jsonl", "w")
        self._text_file = open(self.session_dir / "session.log", "w")

        self._log("INFO", "session_start", {"model": model, "mode": mode})
        return session_id

    def end_session(self) -> None:
        """End the current logging session and write metadata."""
        if not self.session_id:
            return

        # End cost tracking and get stats
        if _HAS_INTEGRATIONS:
            call_stats = cost_tracker.end_call()
            if call_stats:
                print(f"💰 {cost_tracker.format_call_summary(call_stats)}")
                print(cost_tracker.get_session_summary())

        # Update metadata
        if self.session_metadata is not None:
            end_time = time.time()
            self.session_metadata.end_time = end_time
            self.session_metadata.end_time_iso = datetime.now().isoformat()
            self.session_metadata.total_duration = (
                end_time - self.session_metadata.start_time
            )

            self._log(
                "INFO",
                "session_end",
                {
                    "duration_seconds": self.session_metadata.total_duration,
                    "total_entries": len(self.log_entries),
                },
            )

            # Write metadata file
            if self.session_dir:
                with open(self.session_dir / "metadata.json", "w") as f:
                    json.dump(
                        self.session_metadata.to_dict(),
                        f,
                        indent=2 if self.pretty_json else None,
                    )

        # Close file handles
        if self._json_file:
            self._json_file.close()
            self._json_file = None
        if self._text_file:
            self._text_file.close()
            self._text_file = None

        # Reset state
        self.session_id = None
        self.session_dir = None
        self.log_entries = []

    def log_user_message(
        self, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Log a user message."""
        data: dict[str, Any] = {"content": content}
        if metadata:
            data["metadata"] = metadata
        self._log("INFO", "user_message", data)

    def log_system_message(
        self, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Log a system message."""
        data: dict[str, Any] = {"content": content}
        if metadata:
            data["metadata"] = metadata
        self._log("INFO", "system_message", data)

    def log_agent_response(
        self,
        content: str,
        is_complete: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an agent response."""
        data = {"content": content, "is_complete": is_complete}
        if metadata:
            data["metadata"] = metadata
        self._log("INFO", "agent_response", data)

    def log_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a tool call."""
        data = {"tool_name": tool_name, "arguments": arguments, "call_id": call_id}
        if metadata:
            data["metadata"] = metadata
        self._log("INFO", "tool_call", data)

    def log_tool_result(
        self,
        tool_name: str,
        result: Any,
        call_id: str | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a tool execution result."""
        data = {
            "tool_name": tool_name,
            "result": make_json_safe(result),
            "call_id": call_id,
            "error": error,
        }
        if metadata:
            data["metadata"] = metadata
        self._log("ERROR" if error else "INFO", "tool_result", data)

    def log_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str | None = None,
        cost: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log token usage."""
        data: dict[str, Any] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "model": model
            or (self.session_metadata.model if self.session_metadata else None),
            "cost_usd": cost,
        }
        if metadata:
            data["metadata"] = metadata
        self._log("INFO", "token_usage", data)

    def log_error(
        self,
        error_type: str,
        error_message: str,
        traceback: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an error."""
        data: dict[str, Any] = {
            "error_type": error_type,
            "error_message": error_message,
            "traceback": traceback,
        }
        if metadata:
            data["metadata"] = metadata
        self._log("ERROR", "error", data)

    def log_api_request(
        self,
        endpoint: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a raw API request."""
        data = {"endpoint": endpoint, "payload": payload, "headers": headers}
        if metadata:
            data["metadata"] = metadata
        self._log("DEBUG", "api_request", data)

    def log_api_response(
        self,
        endpoint: str,
        response: dict[str, Any],
        status_code: int | None = None,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a raw API response."""
        data = {
            "endpoint": endpoint,
            "response": response,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }
        if metadata:
            data["metadata"] = metadata
        self._log(
            "ERROR" if status_code and status_code >= 400 else "DEBUG",
            "api_response",
            data,
        )

    def log_event(
        self, event_type: str, data: dict[str, Any], level: str = "INFO"
    ) -> None:
        """Log a custom event."""
        self._log(level, event_type, data)

    def log_stream_event(self, event: dict[str, Any], model: str | None = None) -> None:
        """Log an event from the LangChain agent stream."""
        if model is None:
            if self.session_metadata is None or self.session_metadata.model is None:
                raise ValueError(
                    "Model must be provided or available from session metadata"
                )
            model = self.session_metadata.model

        kind = event["event"]

        if kind == "on_chat_model_stream":
            # Handle streaming chunks with token usage
            data = event["data"]
            chunk = data.get("chunk")  # chunk is optional in stream events

            if chunk and chunk.usage_metadata:
                usage = chunk.usage_metadata
                # usage_metadata can be dict or object with attributes
                input_tok = (
                    usage["input_tokens"]
                    if isinstance(usage, dict)
                    else usage.input_tokens
                )
                output_tok = (
                    usage["output_tokens"]
                    if isinstance(usage, dict)
                    else usage.output_tokens
                )

                if input_tok and output_tok:
                    self.log_token_usage(
                        input_tokens=input_tok,
                        output_tokens=output_tok,
                        model=model,
                    )
                    if _HAS_INTEGRATIONS:
                        cost_tracker.update_usage(
                            input_tokens=input_tok, output_tokens=output_tok
                        )

        elif kind == "on_tool_start":
            self.log_tool_call(
                tool_name=event["name"],
                arguments=event["data"]["input"],
                call_id=event["run_id"],
            )

        elif kind == "on_tool_end":
            self.log_tool_result(
                tool_name=event["name"],
                result=event["data"]["output"],
                call_id=event["run_id"],
            )

        elif kind == "on_chain_end":
            data = event["data"]
            output = data.get("output")  # output is optional in chain events

            if output and "messages" in output:
                final_msg = output["messages"][-1]

                if final_msg.usage_metadata:
                    usage = final_msg.usage_metadata
                    # usage_metadata can be dict or object with attributes
                    input_tok = (
                        usage["input_tokens"]
                        if isinstance(usage, dict)
                        else usage.input_tokens
                    )
                    output_tok = (
                        usage["output_tokens"]
                        if isinstance(usage, dict)
                        else usage.output_tokens
                    )

                    if input_tok and output_tok:
                        self.log_token_usage(
                            input_tokens=input_tok,
                            output_tokens=output_tok,
                            model=model,
                        )
                        if _HAS_INTEGRATIONS:
                            cost_tracker.update_usage(
                                input_tokens=input_tok, output_tokens=output_tok
                            )

                if final_msg.content:
                    self.log_agent_response(
                        final_msg.content,
                        is_complete=True,
                        metadata={"source": "chain_end"},
                    )

    def _log(self, level: str, event_type: str, data: dict[str, Any]) -> None:
        """Internal method to write a log entry."""
        if not self.session_id:
            return

        safe_data = make_json_safe(data)
        now = time.time()
        entry = LogEntry(
            timestamp=now,
            timestamp_iso=datetime.fromtimestamp(now).isoformat(),
            level=level,
            event_type=event_type,
            data=safe_data,
        )

        self.log_entries.append(entry)

        # Write to JSON log (JSONL format)
        if self._json_file:
            self._json_file.write(json.dumps(entry.to_dict()) + "\n")
            if self.auto_flush:
                self._json_file.flush()

        # Write to text log
        if self._text_file:
            timestamp_str = datetime.fromtimestamp(now).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3]
            text_line = f"[{timestamp_str}] {level:7s} {event_type:20s} | {format_data_for_text(data)}\n"
            self._text_file.write(text_line)
            if self.auto_flush:
                self._text_file.flush()

    def get_session_path(self) -> Path | None:
        """Get the path to the current session directory."""
        return self.session_dir

    def get_session_id(self) -> str | None:
        """Get the current session ID."""
        return self.session_id

    def __enter__(self) -> "SessionLogger":
        return self

    def __exit__(
        self, exc_type: object | None, exc_val: object | None, exc_tb: object | None
    ) -> None:
        self.end_session()


def create_logger(
    log_dir: str | Path = "logs",
    session_prefix: str = "session",
    model: str = "unknown",
    mode: str | None = None,
    **kwargs: Any,
) -> SessionLogger:
    """Create and start a new session logger in one call."""
    logger = SessionLogger(log_dir=log_dir, session_prefix=session_prefix, **kwargs)
    logger.start_session(model=model, mode=mode)
    return logger
