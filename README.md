# dossier

A structured logging library with session management and object unpacking, built on [structlog](https://www.structlog.org/).

## Why `dossier`?

`structlog` is great, but while I was using it for AI agents, I found myself writing a lot of boilerplate code to handle session management and object unpacking:

- I want to organize my logs by agent session, so I can easily find logs for a specific session.
- I want to throw objects like dataclasses, Pydantic models, or any other object at the logger and let it handle unpacking them for structured logging.

With `dossier`, each session is automatically organized:

```
logs/
└── session_20251118_120000/
    └── events.jsonl      # Structured JSONL logs
```

And you can throw objects like dataclasses, Pydantic models, regular dicts, and `dossier` will handle the unpacking.

## Installation

```bash
pip install dossier
# or
uv add dossier
```

## Quick Start

```python
from dataclasses import dataclass
import dossier

log = dossier.get_logger()

# Bind info to the logger for the entire session
log.bind(model="gpt-4", mode="agent", user_id="user_123", experiment="feature_test")

log.info("session_start")
# logs: {"event": "session_start", "timestamp": "2025-11-18T12:00:00.000Z", "level": "info",
#        "model": "gpt-4", "mode": "agent", "user_id": "user_123", "experiment": "feature_test"}


# Unbind keys
log.unbind("mode", "user_id")

# Log similarly to structlog
log.info("user_message", content="What's the weather?", role="user")

# Or use dataclasses - event type auto-detected!
@dataclass
class ToolCall:
    tool_name: str
    arguments: dict

tool_call = ToolCall(tool_name="web_search", arguments={"q": "weather"})
log.info(tool_call)  # Same as log.info("tool_call", tool_name=tool_call.tool_name, arguments=tool_call.arguments)
```
Get current session information:

```python
session_id = logger.get_session_id()
session_dir = logger.get_session_path()
```

## Reusing a logger

`dossier` implements a logger registry similar to Python's standard `logging.getLogger(name)`. This means you can retrieve the same logger instance from anywhere in your application using its `session_id` without needing to pass it around or set global variables.

```python
from dossier import get_logger

# First call creates the logger
logger = get_logger(session_id="main")
logger.bind(app_version="1.0.0", user_id="user_123")

# Later, anywhere else in your app: this returns the same instance
logger2 = get_logger(session_id="main")
assert logger is logger2  # True!

# Force a new session:
logger3 = get_logger(session_id="main", force_new=True)
```

This also means that you that the sessions are isolated from each other by using different session_ids.

## Custom Processors

Dossier allows you to register custom structlog processors for advanced use cases like cost tracking, metrics collection, or adding custom fields.

#### Function Processors

Simple stateless processors that add fields or transform data:

```python
from dossier import get_logger

# Add a custom field to every log
def add_hostname(logger, method_name, event_dict):
    import socket
    event_dict["hostname"] = socket.gethostname()
    return event_dict

# Add environment info
def add_environment(logger, method_name, event_dict):
    import os
    event_dict["environment"] = os.environ.get("ENV", "development")
    return event_dict

logger = get_logger(
    log_dir="logs",
    processors=[add_hostname, add_environment],
)
logger.bind(model="gpt-4")
logger.info("test_event")
# Output includes: hostname, environment, model
```

### Stateful Class Processors

For tracking state across log calls (like token counting, cost tracking, etc.):

```python
from dossier import get_logger

class TokenCounter:
    """Track cumulative token usage across the session"""

    def __init__(self):
        self.total_tokens = 0
        self.call_count = 0

    def __call__(self, logger, method_name, event_dict):
        # Only process token_usage events
        if "input_tokens" in event_dict and "output_tokens" in event_dict:
            total = event_dict["input_tokens"] + event_dict["output_tokens"]
            self.total_tokens += total
            self.call_count += 1

            # Add cumulative info to the log
            event_dict["cumulative_tokens"] = self.total_tokens
            event_dict["token_call_count"] = self.call_count

        return event_dict

# Create the counter instance
counter = TokenCounter()

logger = get_logger(log_dir="logs", processors=[counter])
logger.bind(model="gpt-4")

# Log token usage
logger.info("token_usage", input_tokens=100, output_tokens=50)
logger.info("token_usage", input_tokens=200, output_tokens=100)

# Access the counter's state
print(f"Total tokens used: {counter.total_tokens}")  # 450
```

#### Real-World Example: Cost Tracker

Here's a complete cost tracking processor similar to OpenAI's pricing:

```python
from dossier import get_logger

# Pricing per million tokens (USD)
PRICING = {
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

class CostTracker:
    """Track API costs across the session"""

    def __init__(self):
        self.total_cost = 0.0
        self.total_calls = 0

    def __call__(self, logger, method_name, event_dict):
        # Process token_usage events
        if event_dict.get("event") == "token_usage":
            model = event_dict.get("model", "gpt-4")
            input_tokens = event_dict.get("input_tokens", 0)
            output_tokens = event_dict.get("output_tokens", 0)

            if model in PRICING:
                pricing = PRICING[model]
                cost = (
                    (input_tokens / 1_000_000) * pricing["input"] +
                    (output_tokens / 1_000_000) * pricing["output"]
                )
                self.total_cost += cost
                self.total_calls += 1

                # Add cost info to log
                event_dict["call_cost_usd"] = round(cost, 6)
                event_dict["cumulative_cost_usd"] = round(self.total_cost, 6)

        return event_dict

    def get_summary(self):
        """Get formatted summary"""
        return f"Total cost: ${self.total_cost:.4f} across {self.total_calls} calls"

# Use the cost tracker
cost_tracker = CostTracker()
logger = get_logger(
    log_dir="logs",
    processors=[cost_tracker],
)
logger.bind(model="gpt-4-turbo")

# Log some API usage
logger.info("token_usage", model="gpt-4-turbo", input_tokens=1000, output_tokens=500)
logger.info("token_usage", model="gpt-4-turbo", input_tokens=2000, output_tokens=1000)

# Get cost summary
print(cost_tracker.get_summary())
# Output: Total cost: $0.0500 across 2 calls
```


### LangChain Integration

Works seamlessly with LangChain objects:

```python
from langchain_core.messages import HumanMessage, AIMessage

user_msg = HumanMessage(content="What's 2+2?")
logger.info(user_msg)  # Event type: "human_message"

ai_msg = AIMessage(content="4")
logger.info(ai_msg)  # Event type: "ai_message"
```

### Pydantic Models

```python
from pydantic import BaseModel

class RequestModel(BaseModel):
    method: str
    path: str
    body: dict

request = RequestModel(method="POST", path="/api/chat", body={"msg": "hi"})
logger.info(request)  # Auto-unpacks to flat dict
```

## Directory Structure



## License

Apache 2.0

## TODO
- instead of get_logger -> start_session()
-
