Search the codebase for defensive programming anti-patterns that sweep bugs under the rug. Remove fallbacks and make code fail fast instead. The goal is to discover bugs early, not hide them with defaults.

**Find and fix these patterns:**

1. **`.get()` with defaults on required keys** - Replace `data.get("key", default)` with `data["key"]` when the key should always be present. Let it raise KeyError if missing.

2. **Defensive validation of programming errors** - Remove validation code that checks for programmer mistakes. Let the code fail naturally when given invalid inputs.

3. **Excessive try/except blocks** - Remove try/except wrappers around code that shouldn't fail in normal operation. Let exceptions propagate with their full stack traces.

4. **Logging warnings instead of raising** - Replace warning logs with exceptions when the data is invalid. Warnings get ignored, exceptions force fixes.

5. **Fallback chains** - Replace chains like `value or default1 or default2 or None` with explicit logic that fails when required values are missing.

6. **Defensive attribute checking** - Remove `hasattr()`, `getattr()`, and `dir()` checks that work around missing attributes. Let AttributeError occur naturally.

7. **Validating "impossible" states** - Remove checks for conditions that "can't happen". If they truly can't, delete the check. If they can, replace with a clear exception.

8. **Excessive attribute inspection** - Remove `dir()` loops that inspect all object attributes "just in case". If an attribute is missing, let AttributeError happen naturally.

9. **Type inspection for debugging** - Remove logging of `str(type(obj))` or introspection for debugging. If the type is wrong, let the method call fail with a proper error.

**Examples:**

**Bad - `.get()` with defaults on required keys:**
```python
user_id = data.get("id", None)
name = data.get("name", "")
```

**Good - Direct access:**
```python
user_id = data["id"]  # Raises KeyError if missing
name = data["name"]
```

**Bad - Logging warnings instead of raising:**
```python
if data.value is None:
    logger.warning("Value is None", extra={
        "data_type": str(type(data)),
        "source": data.source,
    })
    return
process(data.value)
```

**Good - Simple conditional or let it fail:**
```python
if data.value:
    process(data.value)
# Or just: process(data.value)  - fails with clear AttributeError/TypeError
```

**Bad - Fallback chain:**
```python
value = param or (self.config.default if self.config else None) or None
```

**Good - Single fallback:**
```python
value = param or (self.config.default if self.config else None)
# Or fail fast: value = param or raise ValueError("param is required")
```

**Bad - Excessive attribute inspection:**
```python
obj_attrs = {
    attr: getattr(obj, attr, "<not present>")
    for attr in dir(obj)
    if not attr.startswith("_")
    and not callable(getattr(obj, attr, None))
}
logger.warning("Missing attributes", extra={"attributes": obj_attrs})
```

**Good - Direct access:**
```python
value = getattr(obj, "expected_attr", None)
if value:
    process(value)
# Or just: process(obj.expected_attr)  - raises AttributeError if missing
```

**Bad - Warning for invalid state:**
```python
if not self.is_initialized:
    logger.warning("Component not initialized, operation skipped: %s", action)
    return
```

**Good - Silent early return or exception:**
```python
if not self.is_initialized:
    return  # Or: raise RuntimeError("Not initialized")
```

**Impact:** Removing these patterns typically reduces code by 30-50% while making actual bugs easier to find. The code fails at the source of the problem instead of logging warnings that get ignored. Stack traces point to the real problem location.
