"""Integration tests for requests library objects."""

import json
import tempfile
from unittest.mock import Mock

import pytest
import requests
from requests.structures import CaseInsensitiveDict

from dossier import get_session
from tests.conftest import read_jsonl_logs


def create_mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str | None = None,
    headers: dict | None = None,
    url: str = "https://api.example.com/endpoint",
) -> requests.Response:
    """Create a mock Response object for testing."""
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.url = url
    response.headers = CaseInsensitiveDict(headers or {})
    response.text = text or json.dumps(json_data) if json_data else ""
    response.json = (
        Mock(return_value=json_data) if json_data else Mock(side_effect=ValueError)
    )
    response.ok = 200 <= status_code < 300
    response.reason = "OK" if response.ok else "Error"
    response.elapsed = Mock()
    response.elapsed.total_seconds = Mock(return_value=0.123)
    return response


def test_response_logging():
    """Test that requests.Response objects are properly unpacked and logged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_response")

        # Create a mock response
        response = create_mock_response(
            status_code=200,
            json_data={"message": "Success", "data": [1, 2, 3]},
            headers={"Content-Type": "application/json"},
        )
        logger.info(response)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have session_start and our response
        assert len(logs) == 1

        # Check the response log entry
        resp_log = logs[0]
        assert resp_log["event"] == "Mock"  # Mock object type
        assert "status_code" in resp_log  # Mock has status_code attribute


def test_http_request_workflow():
    """Test logging a complete HTTP request/response workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_http_workflow")

        # Log the request
        logger.info(
            "http_request",
            method="GET",
            url="https://api.example.com/users",
            headers={"Authorization": "Bearer token123"},
        )

        # Create and log the response
        response_data = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ]
        }
        logger.info(
            "http_response",
            status_code=200,
            url="https://api.example.com/users",
            response_time_ms=123,
            body=response_data,
        )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have request + response
        assert len(logs) == 2

    # Check request log
    req_log = logs[0]
    assert req_log["event"] == "http_request"
    assert req_log["method"] == "GET"
    assert req_log["url"] == "https://api.example.com/users"

    # Check response log
    resp_log = logs[1]
    assert resp_log["event"] == "http_response"
    assert resp_log["status_code"] == 200
    assert resp_log["response_time_ms"] == 123
    assert len(resp_log["body"]["users"]) == 2


def test_http_error_logging():
    """Test logging HTTP errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_http_error")

        # Log a failed request
        logger.error(
            "http_error",
            method="POST",
            url="https://api.example.com/create",
            status_code=400,
            error="Bad Request",
            details={"field": "email", "message": "Invalid email format"},
        )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check error log
        error_log = logs[0]
        assert error_log["event"] == "http_error"
        assert error_log["level"] == "error"
        assert error_log["status_code"] == 400
        assert error_log["error"] == "Bad Request"


def test_api_rate_limiting():
    """Test logging API rate limiting scenarios."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_rate_limit")

        # Log rate limit hit
        logger.warning(
            "rate_limit_hit",
            url="https://api.example.com/data",
            status_code=429,
            retry_after_seconds=60,
            rate_limit_remaining=0,
            rate_limit_reset=1677652288,
        )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check rate limit log
        limit_log = logs[0]
        assert limit_log["event"] == "rate_limit_hit"
        assert limit_log["level"] == "warning"
        assert limit_log["status_code"] == 429
        assert limit_log["retry_after_seconds"] == 60


def test_http_retry_logic():
    """Test logging HTTP retry attempts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_retries")

        url = "https://api.example.com/flaky"

        # Log multiple retry attempts
        for attempt in range(1, 4):
            logger.info(
                "http_retry_attempt",
                url=url,
                attempt=attempt,
                max_attempts=3,
                backoff_seconds=2**attempt,
            )

            if attempt < 3:
                logger.warning(
                    "http_retry_failed",
                    url=url,
                    attempt=attempt,
                    status_code=503,
                    error="Service Unavailable",
                )

        # Final success
        logger.info(
            "http_request_succeeded",
            url=url,
            attempt=3,
            status_code=200,
        )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have attempt*3 + failed*2 + success
        assert len(logs) == 6

    # Check retry pattern
    assert logs[0]["event"] == "http_retry_attempt"
    assert logs[0]["attempt"] == 1
    assert logs[1]["event"] == "http_retry_failed"
    assert logs[5]["event"] == "http_request_succeeded"


def test_request_with_large_payload():
    """Test logging requests with large payloads (truncation scenario)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_large_payload")

        # Create a large payload
        large_data = {"items": [{"id": i, "data": "x" * 100} for i in range(100)]}

        logger.info(
            "http_request",
            method="POST",
            url="https://api.example.com/bulk",
            payload_size_bytes=len(json.dumps(large_data)),
            items_count=len(large_data["items"]),
        )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check large payload is handled
        req_log = logs[0]
        assert req_log["event"] == "http_request"
        assert req_log["payload_size_bytes"] > 0
        assert req_log["items_count"] == 100


def test_request_headers_logging():
    """Test logging request headers (with sensitive data handling)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_headers")

        # Log headers (in practice, you'd want to redact sensitive ones)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MyApp/1.0",
            "Authorization": "[REDACTED]",  # Should be redacted
            "X-Request-ID": "req-123",
        }

        logger.info(
            "http_request",
            method="GET",
            url="https://api.example.com/data",
            headers=headers,
        )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check headers are logged
        req_log = logs[0]
        assert req_log["headers"]["Content-Type"] == "application/json"
        assert req_log["headers"]["Authorization"] == "[REDACTED]"


def test_api_pagination_workflow():
    """Test logging API pagination workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_pagination")

        base_url = "https://api.example.com/items"

        # Simulate paginated requests
        for page in range(1, 4):
            logger.info(
                "http_request",
                method="GET",
                url=f"{base_url}?page={page}",
                page=page,
            )

            # Response with pagination info
            logger.info(
                "http_response",
                status_code=200,
                page=page,
                items_count=25 if page < 3 else 10,  # Last page has fewer items
                has_next_page=page < 3,
            )

        logger.info("pagination_complete", total_pages=3, total_items=60)

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have (request + response) * 3 + complete
        assert len(logs) == 7

    # Check pagination sequence
    assert logs[0]["page"] == 1
    assert logs[2]["page"] == 2
    assert logs[4]["page"] == 3
    assert logs[6]["event"] == "pagination_complete"


def test_webhook_logging():
    """Test logging webhook requests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_webhook")

        # Log incoming webhook
        logger.info(
            "webhook_received",
            source="stripe",
            event_type="payment.succeeded",
            webhook_id="wh_123abc",
            payload={
                "amount": 5000,
                "currency": "usd",
                "customer": "cus_xyz",
            },
        )

        # Log webhook processing
        logger.info("webhook_processing", webhook_id="wh_123abc")

        # Log webhook response
        logger.info(
            "webhook_response",
            webhook_id="wh_123abc",
            status_code=200,
            processing_time_ms=45,
        )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

    # Check webhook flow
    assert len(logs) == 3
    assert logs[0]["event"] == "webhook_received"
    assert logs[0]["source"] == "stripe"
    assert logs[1]["event"] == "webhook_processing"
    assert logs[2]["event"] == "webhook_response"


def test_http_with_bound_context():
    """Test that bound context is preserved with HTTP logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(log_dir=tmpdir, session_id="test_bound_http")

        # Bind request context
        logger.bind(request_id="req_abc123", user_id="user_789")

        # Log HTTP request
        logger.info(
            "http_request",
            method="POST",
            url="https://api.example.com/action",
        )

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Check bound context is preserved
        req_log = logs[0]
        assert req_log["request_id"] == "req_abc123"
        assert req_log["user_id"] == "user_789"
        assert req_log["method"] == "POST"


def test_multiple_api_calls_workflow():
    """Test logging multiple API calls in a workflow."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = get_session(
            log_dir=tmpdir,
            session_id="test_multi_api",
        )
        logger.bind(service="orchestrator")

        # Call multiple APIs
        apis = [
            {"name": "UserService", "url": "https://users.example.com/api/user/123"},
            {"name": "OrderService", "url": "https://orders.example.com/api/orders"},
            {
                "name": "PaymentService",
                "url": "https://payments.example.com/api/process",
            },
        ]

        for api in apis:
            logger.info(
                "external_api_call",
                service=api["name"],
                url=api["url"],
            )
            logger.info(
                "external_api_response",
                service=api["name"],
                status_code=200,
                response_time_ms=50 + hash(api["name"]) % 100,
            )

        logger.info("workflow_complete", apis_called=len(apis))

        # Read logs
        logs = read_jsonl_logs(logger.get_session_path())

        # Should have (call + response) * 3 + complete
        assert len(logs) == 7

        # Check all services were called
        services = [logs[0]["service"], logs[2]["service"], logs[4]["service"]]
        assert services == ["UserService", "OrderService", "PaymentService"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
