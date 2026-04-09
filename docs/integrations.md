# Integrations

Dossier automatically unpacks objects from popular libraries into flat structured log fields. Pass any object as the event argument and dossier infers the event name from the class and flattens the fields.

## Pydantic

```python
from pydantic import BaseModel
from dossier import get_session

class RequestModel(BaseModel):
    method: str
    path: str
    body: dict

logger = get_session()
request = RequestModel(method="POST", path="/api/chat", body={"msg": "hi"})
logger.info(request)
# {"event": "RequestModel", "method": "POST", "path": "/api/chat", "body": {"msg": "hi"}, ...}
```

Nested Pydantic models are recursively unpacked via `model_dump()`.

## LangChain

```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dossier import get_session

logger = get_session()

logger.info(HumanMessage(content="What's 2+2?"))
# {"event": "HumanMessage", "content": "What's 2+2?", "type": "human", ...}

logger.info(AIMessage(content="4"))
# {"event": "AIMessage", "content": "4", "type": "ai", ...}
```

All LangChain message types work — `HumanMessage`, `AIMessage`, `SystemMessage`, `ToolMessage`, etc.

## OpenAI SDK

```python
from dossier import get_session

logger = get_session()

# Log the full ChatCompletion response object
logger.info(response)
# Unpacks: model, choices, usage fields, etc.

# Or log specific parts
logger.info(response.choices[0].message)
logger.info(response.usage)
```

## Dataclasses

```python
from dataclasses import dataclass
from dossier import get_session

@dataclass
class ToolCall:
    tool_name: str
    arguments: dict

logger = get_session()
logger.info(ToolCall(tool_name="web_search", arguments={"q": "weather"}))
# {"event": "ToolCall", "tool_name": "web_search", "arguments": {"q": "weather"}, ...}
```

Dataclasses are unpacked via `dataclasses.asdict()` for deep recursive conversion.

## Generic Objects

Any object with `__dict__` is unpacked automatically. Private attributes (those starting with `_`) are excluded:

```python
class Config:
    def __init__(self):
        self.host = "localhost"
        self.port = 8080
        self._internal = "hidden"

logger.info(Config())
# {"event": "Config", "host": "localhost", "port": 8080, ...}
```

## Unpacking Priority

When an object matches multiple categories, dossier uses this priority:

1. **Dataclass** — `dataclasses.asdict()` (deepest conversion)
2. **Pydantic model** — `.model_dump()`
3. **Generic object** — `__dict__` (excluding private attrs)

## Nested Objects

Objects nested inside kwargs are also unpacked and flattened with key prefixing:

```python
logger.info("api_call", request=RequestModel(method="GET", path="/health", body={}))
# {"event": "api_call", "request_method": "GET", "request_path": "/health", "request_body": {}, ...}
```
