"""Direct unit tests for processor functions to achieve 100% coverage."""

from dataclasses import dataclass

from pydantic import BaseModel

from dossier.processors import unpack_generic_objects


def test_unpack_generic_objects_with_dataclass_value():
    """Test that unpack_generic_objects leaves dataclasses unchanged (line 102)."""

    @dataclass
    class MyData:
        value: int

    # Create an event_dict with a dataclass value directly
    event_dict = {"my_data": MyData(value=42), "other": "test"}

    # Call unpack_generic_objects directly
    result = unpack_generic_objects(
        logger=None, method_name="info", event_dict=event_dict
    )

    # The dataclass should be left unchanged (line 102 executes)
    assert isinstance(result["my_data"], MyData)
    assert result["my_data"].value == 42
    assert result["other"] == "test"


def test_unpack_generic_objects_with_pydantic_value():
    """Test that unpack_generic_objects leaves Pydantic models unchanged (line 104)."""

    class MyModel(BaseModel):
        value: int

    # Create an event_dict with a Pydantic model value directly
    event_dict = {"my_model": MyModel(value=99), "other": "test"}

    # Call unpack_generic_objects directly
    result = unpack_generic_objects(
        logger=None, method_name="info", event_dict=event_dict
    )

    # The Pydantic model should be left unchanged (line 104 executes)
    assert isinstance(result["my_model"], MyModel)
    assert result["my_model"].value == 99
    assert result["other"] == "test"


def test_unpack_generic_objects_with_nested_dataclass():
    """Test dataclass in a list (recursive transform hits line 102)."""

    @dataclass
    class Item:
        id: int

    # Create an event_dict with dataclasses in a list
    event_dict = {"items": [Item(id=1), Item(id=2), Item(id=3)]}

    # Call unpack_generic_objects directly
    result = unpack_generic_objects(
        logger=None, method_name="info", event_dict=event_dict
    )

    # The dataclasses in the list should be left unchanged (line 102 executes)
    assert len(result["items"]) == 3
    assert all(isinstance(item, Item) for item in result["items"])
    assert [item.id for item in result["items"]] == [1, 2, 3]


def test_unpack_generic_objects_with_nested_pydantic():
    """Test Pydantic model in a dict (recursive transform hits line 104)."""

    class Value(BaseModel):
        amount: int

    # Create an event_dict with Pydantic models in a dict
    event_dict = {"values": {"a": Value(amount=10), "b": Value(amount=20)}}

    # Call unpack_generic_objects directly
    result = unpack_generic_objects(
        logger=None, method_name="info", event_dict=event_dict
    )

    # The Pydantic models in the dict should be left unchanged (line 104 executes)
    assert isinstance(result["values"]["a"], Value)
    assert isinstance(result["values"]["b"], Value)
    assert result["values"]["a"].amount == 10
    assert result["values"]["b"].amount == 20
