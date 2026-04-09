"""Direct unit tests for processor functions to achieve 100% coverage."""

from dataclasses import dataclass

from pydantic import BaseModel

from dossier.processors import unpack_objects


def test_unpack_objects_with_dataclass_value():
    """Test that unpack_objects converts dataclasses via asdict."""

    @dataclass
    class MyData:
        value: int

    event_dict = {"my_data": MyData(value=42), "other": "test"}

    result = unpack_objects(logger=None, method_name="info", event_dict=event_dict)

    # Dataclass should be unpacked and flattened with key prefix
    assert result["my_data_value"] == 42
    assert result["other"] == "test"


def test_unpack_objects_with_pydantic_value():
    """Test that unpack_objects converts Pydantic models via model_dump."""

    class MyModel(BaseModel):
        value: int

    event_dict = {"my_model": MyModel(value=99), "other": "test"}

    result = unpack_objects(logger=None, method_name="info", event_dict=event_dict)

    # Pydantic model should be unpacked and flattened with key prefix
    assert result["my_model_value"] == 99
    assert result["other"] == "test"


def test_unpack_objects_with_nested_dataclass():
    """Test dataclass in a list (recursive transform)."""

    @dataclass
    class Item:
        id: int

    event_dict = {"items": [Item(id=1), Item(id=2), Item(id=3)]}

    result = unpack_objects(logger=None, method_name="info", event_dict=event_dict)

    # Dataclasses in a list should be converted to dicts
    assert len(result["items"]) == 3
    assert result["items"] == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_unpack_objects_with_nested_pydantic():
    """Test Pydantic model in a dict (recursive transform)."""

    class Value(BaseModel):
        amount: int

    event_dict = {"values": {"a": Value(amount=10), "b": Value(amount=20)}}

    result = unpack_objects(logger=None, method_name="info", event_dict=event_dict)

    # Pydantic models in a dict should be converted
    assert result["values"]["a"] == {"amount": 10}
    assert result["values"]["b"] == {"amount": 20}


def test_unpack_objects_with_generic_object():
    """Test that generic objects with __dict__ are unpacked."""

    class Config:
        def __init__(self):
            self.host = "localhost"
            self.port = 8080
            self._internal = "hidden"

    event_dict = {"config": Config()}

    result = unpack_objects(logger=None, method_name="info", event_dict=event_dict)

    # Generic object should be unpacked, private attrs excluded
    assert result["config_host"] == "localhost"
    assert result["config_port"] == 8080
    assert "config__internal" not in result
