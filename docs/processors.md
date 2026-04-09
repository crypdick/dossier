# Custom Processors

Dossier supports [structlog processors](https://www.structlog.org/en/stable/processors.html) for adding custom fields, tracking state, or transforming log data. Pass them via the `processors` parameter on `get_session`.

## Function Processors

A processor is any callable with the signature `(logger, method_name, event_dict) -> event_dict`:

```python
from dossier import get_session

def add_hostname(logger, method_name, event_dict):
    import socket
    event_dict["hostname"] = socket.gethostname()
    return event_dict

def add_environment(logger, method_name, event_dict):
    import os
    event_dict["environment"] = os.environ.get("ENV", "development")
    return event_dict

logger = get_session(processors=[add_hostname, add_environment])
logger.info("test_event")
# {"event": "test_event", "hostname": "myhost", "environment": "development", ...}
```

## Stateful Processors

Use a class with `__call__` to track state across log calls:

```python
from dossier import get_session

class TokenCounter:
    """Track cumulative token usage across the session."""

    def __init__(self):
        self.total_tokens = 0
        self.call_count = 0

    def __call__(self, logger, method_name, event_dict):
        if "input_tokens" in event_dict and "output_tokens" in event_dict:
            total = event_dict["input_tokens"] + event_dict["output_tokens"]
            self.total_tokens += total
            self.call_count += 1
            event_dict["cumulative_tokens"] = self.total_tokens
            event_dict["token_call_count"] = self.call_count
        return event_dict

counter = TokenCounter()
logger = get_session(processors=[counter])

logger.info("token_usage", input_tokens=100, output_tokens=50)
logger.info("token_usage", input_tokens=200, output_tokens=100)
print(counter.total_tokens)  # 450
```

## Example: Cost Tracker

A more complete stateful processor for tracking API costs:

```python
from dossier import get_session

PRICING = {  # per million tokens (USD)
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

class CostTracker:
    def __init__(self):
        self.total_cost = 0.0
        self.total_calls = 0

    def __call__(self, logger, method_name, event_dict):
        if event_dict.get("event") == "token_usage":
            model = event_dict.get("model", "gpt-4")
            input_tokens = event_dict.get("input_tokens", 0)
            output_tokens = event_dict.get("output_tokens", 0)

            if model in PRICING:
                pricing = PRICING[model]
                cost = (
                    (input_tokens / 1_000_000) * pricing["input"]
                    + (output_tokens / 1_000_000) * pricing["output"]
                )
                self.total_cost += cost
                self.total_calls += 1
                event_dict["call_cost_usd"] = round(cost, 6)
                event_dict["cumulative_cost_usd"] = round(self.total_cost, 6)

        return event_dict

    def get_summary(self):
        return f"Total cost: ${self.total_cost:.4f} across {self.total_calls} calls"

cost_tracker = CostTracker()
logger = get_session(processors=[cost_tracker])

logger.info("token_usage", model="gpt-4-turbo", input_tokens=1000, output_tokens=500)
logger.info("token_usage", model="gpt-4-turbo", input_tokens=2000, output_tokens=1000)
print(cost_tracker.get_summary())  # Total cost: $0.0500 across 2 calls
```

## How Processors Fit In

Custom processors run **in addition to** the built-in processor chain:

1. `unpack_objects` — flatten dataclasses, Pydantic models, generic objects
2. `add_log_level` — add `level` field
3. `TimeStamper` — add ISO timestamp
4. `format_exc_info` — format exceptions
5. `make_json_safe` — convert non-serializable values to strings
6. `JSONRenderer` — serialize to JSON

Your custom processors wrap this chain via `structlog.wrap_logger`, so they run before the built-in chain processes the event.
