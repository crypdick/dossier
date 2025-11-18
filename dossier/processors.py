"""Custom structlog processors for session logging."""

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any


def _recursive_transform(value: Any, transform_func: Callable[[Any], Any]) -> Any:
    """Recursively apply transform_func to nested structures."""
    transformed = transform_func(value)
    if transformed is not value:
        return transformed

    if isinstance(value, list):
        return [_recursive_transform(item, transform_func) for item in value]
    if isinstance(value, tuple):
        return tuple(_recursive_transform(item, transform_func) for item in value)
    if isinstance(value, dict) and type(value) is dict:
        return {k: _recursive_transform(v, transform_func) for k, v in value.items()}

    return value


def make_json_safe(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Convert non-JSON-serializable values to strings."""

    def transform(value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, (list, dict, tuple)):
            return value  # Let _recursive_transform handle recursion
        return str(value)  # Convert everything else to string

    for key, value in list(event_dict.items()):
        event_dict[key] = _recursive_transform(value, transform)

    return event_dict


def _process_event_dict(
    event_dict: dict[str, Any], transform_func: Callable[[Any], Any]
) -> dict[str, Any]:
    """Apply transform_func to event_dict values, handling _obj key and flattening."""
    new_dict = {}

    for key, value in event_dict.items():
        if key == "_obj":
            transformed_value = _recursive_transform(value, transform_func)
            if isinstance(transformed_value, dict):
                new_dict.update(transformed_value)
            else:
                new_dict[key] = transformed_value
            continue

        direct_transform = transform_func(value)
        if direct_transform is not value and isinstance(direct_transform, dict):
            for k, v in direct_transform.items():
                new_dict[f"{key}_{k}"] = v
        else:
            new_dict[key] = _recursive_transform(value, transform_func)

    return new_dict


def unpack_dataclasses(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Unpack dataclasses to dicts recursively."""

    def transform(value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        return value

    return _process_event_dict(event_dict, transform)


def unpack_pydantic_models(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Unpack Pydantic models to dicts recursively."""

    def transform(value: Any) -> Any:
        if callable(getattr(value, "model_dump", None)):
            return value.model_dump()
        return value

    return _process_event_dict(event_dict, transform)


def unpack_generic_objects(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Unpack objects with __dict__ to dicts recursively."""

    def transform(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool, type(None), list, dict, tuple)):
            return value
        if is_dataclass(value) and not isinstance(value, type):
            return value
        if callable(getattr(value, "model_dump", None)):
            return value
        if hasattr(value, "__dict__"):
            return {k: v for k, v in value.__dict__.items() if not k.startswith("_")}
        return value

    return _process_event_dict(event_dict, transform)
