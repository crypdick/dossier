"""Formatting utilities for session logging"""

import json
from typing import Any


def make_json_safe(obj: Any) -> Any:
    """
    Convert an object to a JSON-serializable format.

    For logging purposes, complex objects are converted to strings
    for readability rather than preserving their structure.

    Args:
        obj: Any Python object

    Returns:
        JSON-serializable version of the object
    """
    # Handle None
    if obj is None:
        return None

    # Handle basic JSON types
    if isinstance(obj, (bool, int, float, str)):
        return obj

    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]

    # Handle plain dictionaries (not custom classes)
    if isinstance(obj, dict) and type(obj) is dict:
        return {key: make_json_safe(value) for key, value in obj.items()}

    # For any other object (including custom classes, even if they have __dict__),
    # convert to string for readability in logs
    # This catches LangChain messages, dataclasses, etc.
    return str(obj)


def format_data_for_text(data: dict[str, Any]) -> str:
    """Format data dictionary for human-readable text log."""
    # Handle common patterns
    if "content" in data:
        content = data["content"]
        # Don't truncate - show full content (it's a log file, storage is cheap)
        return f"content='{content}'"

    if "tool_name" in data:
        tool_name = data["tool_name"]
        args_str = ""
        if "arguments" in data:
            # Show full arguments (no truncation)
            args = data["arguments"]
            if isinstance(args, dict):
                # Show all args with full values
                args_items = []
                for k, v in args.items():
                    v_str = str(v)
                    args_items.append(f"{k}={v_str}")
                args_str = " args={" + ", ".join(args_items) + "}"
                args_str += "}"
        call_id = data.get("call_id", "")
        call_id_str = f" id={call_id}" if call_id else ""
        return f"tool={tool_name}{call_id_str}{args_str}"

    if "result" in data:
        result = data.get("result", "")
        result_str = str(result)
        # Don't truncate results - show everything
        return f"result='{result_str}'"

    if "error_message" in data:
        return f"error='{data['error_message']}'"

    # Default: show full JSON (no truncation)
    return json.dumps(data)
