# dossier

A structured logging library with session management and object unpacking, built on [structlog](https://www.structlog.org/).

## Why dossier?

`structlog` is great, but when building AI agents I kept writing boilerplate for two things:

- **Session management** — organize logs into per-session directories with a registry pattern (like `logging.getLogger`)
- **Object unpacking** — throw dataclasses, Pydantic models, or any object at the logger and get flat structured output

```
logs/
└── session_20251118_120000/
    ├── events.jsonl
    └── worker.jsonl
```

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

log = dossier.get_session()

# Bind context for the entire session
log.bind(model="gpt-4", user_id="user_123")

# Log like structlog
log.info("user_message", content="What's the weather?", role="user")

# Or pass objects directly — event type auto-detected, fields flattened
@dataclass
class ToolCall:
    tool_name: str
    arguments: dict

log.info(ToolCall(tool_name="web_search", arguments={"q": "weather"}))
# {"event": "ToolCall", "tool_name": "web_search", "arguments": {"q": "weather"}, ...}
```

## Session Registry

Retrieve the same session from anywhere by `session_id`, no globals needed:

```python
# Creates logs/main_TIMESTAMP/
logger = get_session(session_id="main")

# Same instance, anywhere in your app
logger2 = get_session(session_id="main")
assert logger is logger2

# Force a fresh session with the same name
logger3 = get_session(session_id="main", force_new=True)
```

## Namespaced Logging

Route logs to separate files within a session:

```python
logger.info("task_started")                      # → events.jsonl
logger.info("task_started", namespace="worker")   # → worker.jsonl
```

## Custom Processors

Register [structlog processors](https://www.structlog.org/en/stable/processors.html) for custom fields or stateful tracking:

```python
def add_hostname(logger, method_name, event_dict):
    import socket
    event_dict["hostname"] = socket.gethostname()
    return event_dict

logger = get_session(processors=[add_hostname])
```

## Object Unpacking

Works with dataclasses, Pydantic models, LangChain messages, OpenAI SDK objects, and any object with `__dict__`. See the [full documentation](https://dossier.ricardodecal.com/) for details and examples.

## License

Apache 2.0
