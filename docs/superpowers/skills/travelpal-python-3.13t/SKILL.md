---
name: travelpal-python-3.13t
description: Use when writing, reviewing, or refactoring Python code in the TravelPal pipeline that targets Python 3.13 or the free-threaded 3.13t interpreter — including free-threading safety in Dagster assets, `type` alias declarations, and `warnings.deprecated`. Supplements `dignified-python`; this skill covers free-threaded-specific guidance that the base skill does not address.
---

# TravelPal Python 3.13t

Extends `dignified-python` for Python 3.13 and free-threaded (`3.13t`) specifics in the TravelPal Dagster pipeline. When both skills apply, this one wins on version-specific features.

## Interpreter and pyproject.toml

Always target the free-threaded build:

```toml
[project]
requires-python = ">=3.13"

[tool.uv]
python = "python3.13t"
```

The `[tool.uv] python` key pins the interpreter for uv commands in this project. Alternatively, create a `.python-version` file containing `3.13t` or set `UV_PYTHON=python3.13t` in the environment.

Run with `python3.13t`, not `python3.13`. The free-threaded build has the GIL disabled.

## Free-Threaded Mode (PEP 703)

The GIL is disabled in `3.13t`. True parallelism is available for CPU-bound work in threads.

```python
from concurrent.futures import ThreadPoolExecutor

def fetch_chunk(interval: tuple[int, int]) -> list[OpenSkyFlight]:
    # Create adapter per-thread — do not share a single instance across threads
    adapter = OpenSkyAdapter()
    return asyncio.run(adapter._fetch_chunk("departure", "KJFK", *interval))

with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(fetch_chunk, intervals))
```

Dagster context:
- Dagster assets run in **separate processes** by default — free-threading is not relevant at the asset boundary.
- Free-threading matters within a single asset that spawns threads (e.g., concurrent chunk fetching).
- `ResourceParam`-injected resources are isolated per-run; no cross-run sharing concern.
- `OpenSkyAdapter` uses `asyncio.run()` internally via `cached_property` on `_client`. The event loop is tied to the thread that first accessed `_client`. **A `threading.Lock` does not fix event-loop affinity** — always instantiate `OpenSkyAdapter` per thread, never share a single instance across threads.

## `type` Aliases

Declare domain concepts with the `type` statement (available since 3.12):

```python
type IcaoCode = str
type UnixTimestamp = int
type FlightId = str
```

Use these aliases instead of bare `str` or `int` where domain meaning matters.

## `warnings.deprecated`

Mark legacy functions before removal:

```python
from warnings import deprecated

@deprecated("Use fetch_departures_v2() instead. Removed in pipeline v3.")
def fetch_departures_v1(airport: IcaoCode) -> list[OpenSkyFlight]: ...
```

## Checklist

- [ ] `requires-python = ">=3.13"` and `python3.13t` interpreter in `[tool.uv]`
- [ ] No shared mutable state across threads within an asset
- [ ] `OpenSkyAdapter` instantiated per-thread (never share across threads — event loop affinity)
- [ ] Domain primitives declared with `type` aliases
- [ ] Deprecated functions annotated with `@deprecated`
