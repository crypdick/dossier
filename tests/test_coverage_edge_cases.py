"""Test edge cases to achieve 100% coverage."""

import json
from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from dossier import get_logger


def test_debug_method(tmp_path):
    """Test the debug() log level method (line 89)."""
    logger = get_logger(log_dir=tmp_path / "logs")
    logger.debug("debug_event", detail="testing debug level")

    # Verify the event was logged with debug level
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])

        assert event["event"] == "debug_event"
        assert event["detail"] == "testing debug level"
        assert event["level"] == "debug"


def test_event_none_raises_error(tmp_path):
    """Test that passing None as event raises ValueError (line 48)."""
    logger = get_logger(log_dir=tmp_path / "logs")

    with pytest.raises(ValueError, match="Must provide event string or object"):
        logger.info(None)


def test_primitive_event_raises_error(tmp_path):
    """Test that passing a primitive as event raises ValueError (lines 21, 42-43)."""
    logger = get_logger(log_dir=tmp_path / "logs")

    # Test with string (should work normally)
    logger.info("string_event")  # This should work

    # Test with int as event (should fail)
    with pytest.raises(
        ValueError,
        match="Must provide event type string or object with inferrable type",
    ):
        logger.info(123)

    # Test with float as event (should fail)
    with pytest.raises(
        ValueError,
        match="Must provide event type string or object with inferrable type",
    ):
        logger.info(3.14)

    # Test with bool as event (should fail)
    with pytest.raises(
        ValueError,
        match="Must provide event type string or object with inferrable type",
    ):
        logger.info(True)

    # Test with list as event (should fail)
    with pytest.raises(
        ValueError,
        match="Must provide event type string or object with inferrable type",
    ):
        logger.info([1, 2, 3])

    # Test with dict as event (should fail)
    with pytest.raises(
        ValueError,
        match="Must provide event type string or object with inferrable type",
    ):
        logger.info({"key": "value"})


def test_context_manager(tmp_path):
    """Test using logger as a context manager (line 141)."""
    with get_logger(log_dir=tmp_path / "logs") as logger:
        logger.info("context_event", data="inside context manager")

    # Verify the event was logged
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])

        assert event["event"] == "context_event"
        assert event["data"] == "inside context manager"


def test_tuple_processing(tmp_path):
    """Test that tuples are processed correctly in processors (line 17)."""
    logger = get_logger(log_dir=tmp_path / "logs")

    # Log with tuple data
    logger.info("tuple_event", tuple_data=(1, 2, 3, "four"))

    # Verify tuple was processed
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])

        assert event["event"] == "tuple_event"
        # Tuples get converted to lists in JSON
        assert event["tuple_data"] == [1, 2, 3, "four"]


def test_nested_tuple_processing(tmp_path):
    """Test nested tuples in data structures (line 17)."""
    logger = get_logger(log_dir=tmp_path / "logs")

    # Log with nested tuple data
    logger.info(
        "nested_tuple_event",
        nested={"inner_tuple": (1, (2, 3), 4), "list_with_tuple": [1, (5, 6)]},
    )

    # Verify nested structures were processed
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])

        assert event["event"] == "nested_tuple_event"
        # Tuples get converted to lists in JSON
        assert event["nested"]["inner_tuple"] == [1, [2, 3], 4]
        assert event["nested"]["list_with_tuple"] == [1, [5, 6]]


def test_generic_object_with_dataclass_field(tmp_path):
    """Test generic object unpacking with dataclass fields (line 102).

    When a generic object contains a dataclass field, the generic unpacker
    leaves the dataclass as-is (returns value unchanged at line 102) so it
    gets stringified by make_json_safe.
    """

    @dataclass
    class InnerData:
        value: int

    class OuterObject:
        def __init__(self):
            self.inner = InnerData(value=42)
            self.name = "test"

    logger = get_logger(log_dir=tmp_path / "logs")
    obj = OuterObject()
    logger.info(obj)

    # Verify the object was unpacked and inner dataclass was stringified
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])

        assert event["event"] == "OuterObject"
        assert event["name"] == "test"
        # The dataclass gets stringified because it's exposed after
        # the dataclass processor already ran
        assert "InnerData" in event["inner"]
        assert "42" in event["inner"]


def test_generic_object_with_pydantic_field(tmp_path):
    """Test generic object unpacking with Pydantic model fields (line 104).

    When a generic object contains a Pydantic model field, the generic unpacker
    leaves the model as-is (returns value unchanged at line 104) so it
    gets stringified by make_json_safe.
    """

    class InnerModel(BaseModel):
        value: int

    class OuterObject:
        def __init__(self):
            self.inner = InnerModel(value=99)
            self.name = "test"

    logger = get_logger(log_dir=tmp_path / "logs")
    obj = OuterObject()
    logger.info(obj)

    # Verify the object was unpacked and inner model was stringified
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])

        assert event["event"] == "OuterObject"
        assert event["name"] == "test"
        # The pydantic model gets stringified because it's exposed after
        # the pydantic processor already ran
        assert "InnerModel" in event["inner"] or "value" in event["inner"]


def test_warning_method(tmp_path):
    """Test the warning() log level method for completeness."""
    logger = get_logger(log_dir=tmp_path / "logs")
    logger.warning("warning_event", detail="testing warning level")

    # Verify the event was logged with warning level
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])

        assert event["event"] == "warning_event"
        assert event["detail"] == "testing warning level"
        assert event["level"] == "warning"


def test_error_method(tmp_path):
    """Test the error() log level method for completeness."""
    logger = get_logger(log_dir=tmp_path / "logs")
    logger.error("error_event", detail="testing error level")

    # Verify the event was logged with error level
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])

        assert event["event"] == "error_event"
        assert event["detail"] == "testing error level"
        assert event["level"] == "error"


def test_dataclass_in_list_with_generic_object(tmp_path):
    """Test dataclass inside a list within a generic object (targets line 102)."""

    @dataclass
    class Item:
        id: int

    class Container:
        def __init__(self):
            self.items = [Item(id=1), Item(id=2)]

    logger = get_logger(log_dir=tmp_path / "logs")
    obj = Container()
    logger.info(obj)

    # Verify logging succeeded
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])
        assert event["event"] == "Container"
        assert "items" in event


def test_pydantic_in_dict_with_generic_object(tmp_path):
    """Test pydantic model inside a dict within a generic object (targets line 104)."""

    class Value(BaseModel):
        amount: int

    class Store:
        def __init__(self):
            self.values = {"first": Value(amount=100), "second": Value(amount=200)}

    logger = get_logger(log_dir=tmp_path / "logs")
    obj = Store()
    logger.info(obj)

    # Verify logging succeeded
    with open(logger.session_dir / "events.jsonl") as f:
        lines = f.readlines()
        event = json.loads(lines[-1])
        assert event["event"] == "Store"
        assert "values" in event
