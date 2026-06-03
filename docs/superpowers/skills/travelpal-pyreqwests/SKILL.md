---
name: travelpal-pyreqwests
description: Use when writing or reviewing HTTP client code in the TravelPal data pipeline, including OpenSky adapter implementation, retry middleware, or unit tests that mock HTTP responses.
---

# TravelPal pyreqwests Reference

## Overview

`pyreqwests` is a Rust-backed Python HTTP client (reqwest crate) used in the TravelPal pipeline for all outbound HTTP. Python 3.11+ required. Install with `uv add pyreqwests`.

Key modules: `pyreqwest.client`, `pyreqwest.exceptions`, `pyreqwest.middleware`.

## Quick Reference

### Client Setup

In TravelPal, the HTTP client is stored as a lazy `cached_property` on the adapter. This avoids the async context manager lifecycle mismatch with Dagster's synchronous resource system.

```python
from datetime import timedelta
from functools import cached_property
from pyreqwest.client import ClientBuilder

class OpenSkyAdapter:
    def __init__(self, username: str = "", password: str = "") -> None:
        self._username = username
        self._password = password

    @cached_property
    def _client(self):
        builder = (
            ClientBuilder()
            .base_url("https://opensky-network.org/api/flights/")
            .connect_timeout(timedelta(seconds=5))
            .timeout(timedelta(seconds=30))
        )
        if self._username:
            builder = builder.basic_auth(self._username, self._password)
        return builder.build()
```

The builder is a fluent chain — call methods in any order, then `.build()` once. The client does **not** need to be used as a context manager.

### Request Builder Pattern

```python
response = await (
    self._client.get("departure")
    .query({"airport": "KJFK", "begin": 1704067200, "end": 1704672000})
    .build()
    .send()
)
```

Parentheses around the full chain are required when splitting across lines. `.build()` must come before `.send()`. `send()` returns a coroutine — always `await` it.

Other builder methods:

```python
client.get(url)
    .query({"key": "val"})         # URL query params
    .headers({"X-Req": "val"})     # custom headers
    .bearer_auth("token")          # Bearer token
    .body_json({"msg": "hello"})   # JSON body
    .build()
    .send()
```

### Response Access

```python
response.status         # int — check this before calling .json()
await response.json()   # dict / list — coroutine, must await
await response.text()   # str — coroutine, must await
await response.bytes()  # bytes — coroutine, must await
response.headers        # dict
```

`.json()`, `.text()`, and `.bytes()` are all coroutines. Forgetting `await` is the most common mistake.

### Status Checking

Do not use `.error_for_status()`. Check `response.status` explicitly so that legitimate non-2xx responses (e.g. HTTP 404 for empty flight windows) can be handled as data rather than errors:

```python
if response.status == 404:
    return []
raw = await response.json() or []
```

### Error Handling

```python
from pyreqwest.exceptions import StatusError

try:
    response = await (client.get(url).build().send())
except StatusError as e:
    status = e.status  # int attribute — not e.details["status"]
```

### Retry Middleware (OpenSky 429s)

```python
from pyreqwest.middleware import Middleware, NextHandler

class RetryOn429(Middleware):
    async def run(self, req, next_handler: NextHandler):
        for attempt in range(3):
            try:
                return await next_handler.run(req)
            except StatusError as e:
                if e.status != 429 or attempt == 2:
                    raise
```

Wire the middleware into the builder:

```python
builder = ClientBuilder().base_url(...).with_middleware(RetryOn429())
```

### Testing

Mock `_client` or `_fetch_chunk` via `patch.object` — this works against the real adapter constructor without needing to inject a client:

```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

@pytest.mark.asyncio
async def test_fetch_chunk_handles_404():
    adapter = OpenSkyAdapter()
    mock_response = MagicMock()
    mock_response.status = 404

    with patch.object(adapter, "_client") as mock_client:
        mock_req = MagicMock()
        mock_req.build.return_value.send = AsyncMock(return_value=mock_response)
        mock_client.get.return_value.query.return_value = mock_req
        result = await adapter._fetch_chunk("departure", "KJFK", 0, 86400)

    assert result == []
```

No real HTTP calls in unit tests.

## Common Mistakes

- **Forgetting `await` on response methods** — `.json()`, `.text()`, `.bytes()` are all coroutines.
- **Using `.error_for_status(True)`** — breaks 404-as-empty-range semantics; check `response.status` manually.
- **`e.details["status"]` on `StatusError`** — use `e.status` (attribute, not dict key).
- **Calling `.send()` before `.build()`** — the chain requires `.build()` then `.send()`.
- **No parens on multi-line chain** — Python won't continue a dotted chain across line breaks without parens or backslashes.
- **Hardcoding credentials** — read `opensky_username` and `opensky_password` from `PipelineConfig`, never inline.
