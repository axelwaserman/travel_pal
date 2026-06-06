"""Live BTS download — gated behind TRAVELPAL_BTS_LIVE=1.

CI never runs this. Local devs validate against the real BTS endpoint by:

    TRAVELPAL_BTS_LIVE=1 uv run pytest \\
        tests/integration/test_integration_bts_download.py -v

Mirrors the live OpenSky-token gate pattern in test_integration_opensky_auth.py.
"""

import asyncio
import io
import os
import zipfile

import pytest

from pipeline.resources.bts import BTSResource


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("TRAVELPAL_BTS_LIVE") != "1",
    reason="set TRAVELPAL_BTS_LIVE=1 to hit transtats.bts.gov for real",
)
def test_live_bts_download_returns_valid_zip_with_many_rows():
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=None,
    )
    payload = asyncio.run(resource.download_month(2024, 1))

    assert payload[:2] == b"PK", "Payload must be a ZIP"
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        assert csv_names, "ZIP must contain at least one CSV"
        sample = zf.read(csv_names[0])
        # Crude row-count proxy: 100k+ flights/month nationally.
        assert sample.count(b"\n") > 100_000, (
            f"Expected ≥100k rows in BTS January 2024; got {sample.count(b'\\n')}"
        )
