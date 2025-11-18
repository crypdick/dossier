"""Custom structlog processors for session logging."""

from dataclasses import asdict, is_dataclass
from typing import Any


def make_json_safe_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    Ensure all values in event_dict are JSON-serializable.

    This processor recursively converts non-serializable objects to strings,
    handling common cases like:
    - LangChain messages
    - Custom dataclasses (already unpacked by ObjectUnpackingProcessor)
    - Any complex objects

    Args:
        logger: The wrapped logger instance (unused)
        method_name: The log method name (unused)
        event_dict: Dictionary containing the log event

    Returns:
        Modified event_dict with all values JSON-safe
    """

    def make_safe(value: Any) -> Any:
        """Recursively make a value JSON-safe."""
        # Handle None
        if value is None:
            return None

        # Handle basic JSON types
        if isinstance(value, (bool, int, float, str)):
            return value

        # Handle lists and tuples
        if isinstance(value, (list, tuple)):
            return [make_safe(item) for item in value]

        # Handle plain dictionaries (not custom classes)
        if isinstance(value, dict) and type(value) is dict:
            return {key: make_safe(val) for key, val in value.items()}

        # For any other object (including custom classes),
        # convert to string for readability in logs
        return str(value)

    # Process all values in the event dict
    for key, value in list(event_dict.items()):
        event_dict[key] = make_safe(value)

    return event_dict


def object_unpacking_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    Unpack objects in the event_dict into flat key-value pairs.

    This processor handles objects that were passed as values:
    - Dataclasses → unpacked via asdict()
    - Pydantic models → unpacked via model_dump()
    - Objects with __dict__ → unpacked
    - Collections and primitives → passed through

    This allows you to pass rich objects as log parameters and have
    them automatically flattened.

    Example:
        @dataclass
        class UserMessage:
            content: str
            role: str

        msg = UserMessage(content="Hello", role="user")
        logger.info("user_message", message=msg)

        # Results in: {
        #   "event": "user_message",
        #   "message_content": "Hello",
        #   "message_role": "user"
        # }

    Args:
        logger: The wrapped logger instance (unused)
        method_name: The log method name (unused)
        event_dict: Dictionary containing the log event

    Returns:
        Modified event_dict with objects unpacked
    """

    def flatten_object(obj: Any) -> dict[str, Any]:
        """Flatten an object into a dictionary."""
        # Handle dataclasses
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)

        # Handle Pydantic models
        if hasattr(obj, "model_dump"):
            result: dict[str, Any] = obj.model_dump()
            return result

        # Handle plain dicts
        if isinstance(obj, dict):
            return obj

        # Handle objects with __dict__
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}

        # Can't flatten - return as-is (will be handled by make_json_safe later)
        return {"value": obj}

    # Process each value in the event dict
    new_dict = {}
    for key, value in event_dict.items():
        # Special handling for _obj key (object passed directly to logger)
        if key == "_obj":
            # Unpack directly without prefix
            if isinstance(value, (str, int, float, bool, type(None), list, dict)):
                # Primitive - this shouldn't happen but handle it
                new_dict["_obj"] = value
            else:
                flattened = flatten_object(value)
                new_dict.update(flattened)
            continue

        # Skip primitives and collections
        if isinstance(value, (str, int, float, bool, type(None), list, dict)):
            new_dict[key] = value
        else:
            # Try to flatten the object
            flattened = flatten_object(value)
            # If flattening resulted in single 'value' key, unwrap it
            if len(flattened) == 1 and "value" in flattened:
                new_dict[key] = flattened["value"]
            else:
                # Multiple keys: add prefix to avoid collisions
                for k, v in flattened.items():
                    new_dict[f"{key}_{k}"] = v

    return new_dict
