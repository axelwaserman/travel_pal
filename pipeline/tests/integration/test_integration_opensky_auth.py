"""Live integration test for OpenSky OAuth2 client_credentials flow.

Skipped unless OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET are set in the
environment.  This test makes a real HTTPS call to OpenSky's auth realm
and verifies the OpenSkyResource token-refresh path end-to-end.

Marked @pytest.mark.integration.  Does NOT require Docker.

Expected behaviour:
    - Without env vars set: both tests SKIP with a message naming the two
      required env vars.
    - With valid OPENSKY_CLIENT_ID / OPENSKY_CLIENT_SECRET set in the
      environment: both tests PASS, exercising the real auth handshake
      against ``auth.opensky-network.org``.  Each test instantiates its
      own OpenSkyResource — there is no shared resource fixture, so the
      second test does NOT rely on the first having run.
"""

import os
import time

import pytest

from pipeline.resources.opensky import OpenSkyResource

pytestmark = pytest.mark.integration


_LIVE_AUTH_TIMEOUT_S: float = 30.0


@pytest.fixture
def live_credentials() -> tuple[str, str]:
    client_id = os.environ.get("OPENSKY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("OPENSKY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        pytest.skip(
            "OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET must be set "
            "to exercise the live OpenSky token endpoint"
        )
    return client_id, client_secret


@pytest.mark.asyncio
async def test_live_token_endpoint_returns_bearer(
    live_credentials: tuple[str, str],
) -> None:
    """OpenSkyResource._ensure_token_valid() must successfully obtain a
    bearer token from the real OpenSky auth realm and populate _token +
    _expires_at on the resource."""
    client_id, client_secret = live_credentials
    resource = OpenSkyResource(client_id=client_id, client_secret=client_secret)

    before = time.monotonic()
    await resource._ensure_token_valid()
    elapsed = time.monotonic() - before

    assert elapsed < _LIVE_AUTH_TIMEOUT_S, (
        f"token fetch took {elapsed:.1f}s (threshold {_LIVE_AUTH_TIMEOUT_S}s)"
    )
    assert resource._token, "expected a non-empty bearer token"
    assert isinstance(resource._token, str)
    # OpenSky tokens typically last ~30 minutes; assert at least 60s remaining
    # so the assertion holds even on a slow/loaded test machine.
    remaining = resource._expires_at - time.monotonic()
    assert remaining > 60, f"expected at least 60s of token life, got {remaining:.1f}s"


@pytest.mark.asyncio
async def test_live_token_cached_within_ttl(
    live_credentials: tuple[str, str],
) -> None:
    """A second _ensure_token_valid() call within TTL must reuse the cached
    token (same _token, same _expires_at — no second network round trip)."""
    client_id, client_secret = live_credentials
    resource = OpenSkyResource(client_id=client_id, client_secret=client_secret)

    await resource._ensure_token_valid()
    first_token = resource._token
    first_expiry = resource._expires_at

    await resource._ensure_token_valid()

    assert resource._token == first_token, "token changed on cached call"
    assert resource._expires_at == first_expiry, "expiry changed on cached call"
