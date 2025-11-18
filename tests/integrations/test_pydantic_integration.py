"""Integration tests for Pydantic model types."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, Field, field_validator

from dossier import get_logger


def read_jsonl_logs(session_dir: Path) -> list[dict]:
    """Read and parse all JSONL log entries."""
    log_file = session_dir / "events.jsonl"
    logs = []
    with open(log_file) as f:
        for line in f:
            logs.append(json.loads(line))
    return logs


class SimpleModel(BaseModel):
    """Simple Pydantic model for testing."""

    name: str
    age: int


class RequestModel(BaseModel):
    """Example HTTP request model."""

    method: str
    path: str
    body: dict[str, Any]
    headers: dict[str, str] = Field(default_factory=dict)


class NestedModel(BaseModel):
    """Model with nested Pydantic models."""

    user_id: str
    request: RequestModel


class ModelWithValidation(BaseModel):
    """Model with field validation."""

    email: str
    score: int = Field(ge=0, le=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Must be a valid email")
        return v.lower()


def test_simple_pydantic_model():
    """Test that simple Pydantic models are properly unpacked and logged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(log_dir=tmpdir, session_id="test_simple_model")

        # Create and log a simple model
        model = SimpleModel(name="Alice", age=30)
        logger.info(model)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have session_start and our model
        assert len(logs) == 1

        # Check the model log entry
        model_log = logs[0]
        assert model_log["event"] == "SimpleModel"
        assert model_log["name"] == "Alice"
        assert model_log["age"] == 30
        assert "timestamp" in model_log
        assert "level" in model_log


def test_request_model():
    """Test logging of a more complex request model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(log_dir=tmpdir, session_id="test_request_model")

        # Create and log a request model
        request = RequestModel(
            method="POST",
            path="/api/chat",
            body={"message": "hello", "user_id": "123"},
            headers={"Content-Type": "application/json", "Authorization": "Bearer xyz"},
        )
        logger.info(request)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the request log entry
        req_log = logs[0]
        assert req_log["event"] == "RequestModel"
        assert req_log["method"] == "POST"
        assert req_log["path"] == "/api/chat"
        assert req_log["body"]["message"] == "hello"
        assert req_log["headers"]["Content-Type"] == "application/json"


def test_nested_pydantic_model():
    """Test that nested Pydantic models are properly unpacked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(log_dir=tmpdir, session_id="test_nested_model")

        # Create nested models
        request = RequestModel(
            method="GET",
            path="/api/user",
            body={},
            headers={"Accept": "application/json"},
        )
        nested = NestedModel(user_id="user_456", request=request)

        logger.info(nested)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the nested model log entry
        nested_log = logs[0]
        assert nested_log["event"] == "NestedModel"
        assert nested_log["user_id"] == "user_456"
        assert nested_log["request"]["method"] == "GET"
        assert nested_log["request"]["path"] == "/api/user"
        assert nested_log["request"]["headers"]["Accept"] == "application/json"


def test_pydantic_with_validation():
    """Test models with field validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(log_dir=tmpdir, session_id="test_validation_model")

        # Create model with validation (email gets lowercased)
        model = ModelWithValidation(email="Alice@Example.com", score=85)
        logger.info(model)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the model log entry
        model_log = logs[0]
        assert model_log["event"] == "ModelWithValidation"
        assert model_log["email"] == "alice@example.com"  # Lowercased by validator
        assert model_log["score"] == 85


def test_pydantic_with_bound_context():
    """Test that bound context is preserved with Pydantic model logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(log_dir=tmpdir, session_id="test_bound_pydantic")

        # Bind some context
        logger.bind(environment="production", version="1.2.3")

        # Log a model
        model = SimpleModel(name="Bob", age=25)
        logger.info(model)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the model has bound context
        model_log = logs[0]
        assert model_log["environment"] == "production"
        assert model_log["version"] == "1.2.3"
        assert model_log["name"] == "Bob"
        assert model_log["age"] == 25


def test_pydantic_in_kwargs():
    """Test logging Pydantic models as keyword arguments."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(log_dir=tmpdir, session_id="test_pydantic_kwargs")

        # Log an event with a Pydantic model as a kwarg
        model = SimpleModel(name="Charlie", age=35)
        logger.info("user_action", action="login", user=model, ip_address="192.168.1.1")

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the log entry
        log_entry = logs[0]
        assert log_entry["event"] == "user_action"
        assert log_entry["action"] == "login"
        assert log_entry["ip_address"] == "192.168.1.1"
        # The model should be unpacked with a prefix
        assert log_entry["user_name"] == "Charlie"
        assert log_entry["user_age"] == 35


def test_pydantic_list():
    """Test logging lists of Pydantic models."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(log_dir=tmpdir, session_id="test_pydantic_list")

        # Create a list of models
        users = [
            SimpleModel(name="Alice", age=30),
            SimpleModel(name="Bob", age=25),
            SimpleModel(name="Charlie", age=35),
        ]

        logger.info("batch_users", users=users, count=len(users))

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the log entry
        log_entry = logs[0]
        assert log_entry["event"] == "batch_users"
        assert log_entry["count"] == 3
        assert len(log_entry["users"]) == 3
        # Models should be converted to dicts
        assert log_entry["users"][0]["name"] == "Alice"
        assert log_entry["users"][1]["name"] == "Bob"
        assert log_entry["users"][2]["name"] == "Charlie"


def test_mixed_dataclass_and_pydantic():
    """Test logging with both Pydantic models and dataclasses."""
    from dataclasses import dataclass

    @dataclass
    class DataclassUser:
        username: str
        email: str

    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(log_dir=tmpdir, session_id="test_mixed_models")

        # Log events with both types
        pydantic_model = SimpleModel(name="PydanticUser", age=28)
        logger.info(pydantic_model)

        dataclass_user = DataclassUser(
            username="DataclassUser", email="user@example.com"
        )
        logger.info(dataclass_user)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check both were logged correctly
        assert len(logs) == 2  # + 2 models

        pydantic_log = logs[0]
        assert pydantic_log["event"] == "SimpleModel"
        assert pydantic_log["name"] == "PydanticUser"

        dataclass_log = logs[1]
        assert dataclass_log["event"] == "DataclassUser"
        assert dataclass_log["username"] == "DataclassUser"


def test_pydantic_with_default_values():
    """Test that Pydantic models with default values log correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(log_dir=tmpdir, session_id="test_defaults")

        # Create model without providing optional fields
        request = RequestModel(method="GET", path="/", body={})
        logger.info(request)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check the log entry
        req_log = logs[0]
        assert req_log["event"] == "RequestModel"
        assert req_log["method"] == "GET"
        assert req_log["headers"] == {}  # Default empty dict


def test_complex_pydantic_workflow():
    """Test a realistic workflow with multiple Pydantic models."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_logger(
            log_dir=tmpdir,
            session_id="test_workflow",
        )
        logger.bind(service="api", version="2.0")

        # Simulate a request workflow
        incoming_request = RequestModel(
            method="POST",
            path="/api/users",
            body={"name": "NewUser", "email": "newuser@example.com"},
            headers={"Content-Type": "application/json"},
        )
        logger.info(incoming_request)

        # Process the data
        user = SimpleModel(name="NewUser", age=28)
        logger.info("user_created", user_data=user, source="api")

        # Validation step
        validated = ModelWithValidation(email="newuser@example.com", score=95)
        logger.info(validated)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have 3 workflow steps
        assert len(logs) == 3

        # Metadata bound after, so check logs [1:]
        for log in logs[1:]:
            assert log["service"] == "api"
            assert log["version"] == "2.0"

    # Verify workflow sequence
    assert logs[0]["event"] == "RequestModel"
    assert logs[1]["event"] == "user_created"
    assert logs[2]["event"] == "ModelWithValidation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
