import asyncio
import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pyarrow as pa
import pytest

from pipeline.resources.bts import (
    BTSDownloadError,
    BTSResource,
    extract_csv_from_zip,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bts_kjfk_2024_01.csv.zip"


@pytest.mark.unit
def test_bts_resource_parses_fixture_zip():
    """Fixture mode: download_month returns the fixture ZIP bytes verbatim, no HTTP."""
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=str(FIXTURE_PATH),
    )

    payload = asyncio.run(resource.download_month(2024, 1))

    assert payload[:2] == b"PK", "Returned bytes must start with ZIP magic"
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        assert any(n.endswith(".csv") for n in zf.namelist())


@pytest.mark.unit
def test_bts_resource_raises_on_missing_fixture(tmp_path):
    """Fixture mode with a path that does not exist raises BTSDownloadError."""
    missing = tmp_path / "nope.zip"
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=str(missing),
    )

    with pytest.raises(BTSDownloadError, match="fixture not found"):
        asyncio.run(resource.download_month(2024, 1))


@pytest.mark.unit
def test_extract_csv_from_zip_filters_to_airport():
    """extract_csv_from_zip returns only rows where origin OR dest matches IATA."""
    table = extract_csv_from_zip(FIXTURE_PATH.read_bytes(), origin_iata="JFK")

    assert isinstance(table, pa.Table)
    # Fixture has 9 rows touching JFK (rows 1-8 + row 10), 1 LAX-only row dropped:
    assert table.num_rows == 9
    column_names = set(table.column_names)
    assert {
        "flight_date",
        "carrier_iata",
        "origin_iata",
        "destination_iata",
        "cancelled",
        "diverted",
        "year_month",
    }.issubset(column_names), f"missing columns: {column_names}"


@pytest.mark.unit
def test_extract_casts_cancelled_diverted_to_bool():
    """'0.00'/'1.00' string flags are cast to bool."""
    table = extract_csv_from_zip(FIXTURE_PATH.read_bytes(), origin_iata="JFK")

    cancelled = table.column("cancelled").to_pylist()
    diverted = table.column("diverted").to_pylist()

    assert all(isinstance(v, bool) for v in cancelled)
    assert all(isinstance(v, bool) for v in diverted)
    # Fixture: rows with Cancelled='1.00' → True; ours has 3 such rows.
    assert sum(cancelled) == 3
    # Fixture: row 7 has Diverted='1.00'.
    assert sum(diverted) == 1


@pytest.mark.unit
def test_extract_stamps_year_month_partition():
    """All rows for a single download month carry the same year_month partition value."""
    table = extract_csv_from_zip(FIXTURE_PATH.read_bytes(), origin_iata="JFK")

    year_months = set(table.column("year_month").to_pylist())
    assert year_months == {"2024-01"}


@pytest.mark.unit
def test_bts_resource_post_payload_when_no_fixture():
    """Without a fixture, BTSResource POSTs the BTS prezip URL with the right form."""
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=None,
    )

    fake_response = MagicMock()
    fake_response.status = 200
    fake_response.read = AsyncMock(return_value=b"PK\x03\x04fake")
    fake_builder = MagicMock()
    fake_builder.build.return_value.send = AsyncMock(return_value=fake_response)
    fake_client = MagicMock()
    fake_client.get.return_value = fake_builder

    with patch.object(BTSResource, "_client", new_callable=lambda: fake_client):
        payload = asyncio.run(resource.download_month(2024, 1))

    assert payload == b"PK\x03\x04fake"
    fake_client.get.assert_called_once()
    called_url = fake_client.get.call_args.args[0]
    assert "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_1.zip" in called_url
    assert called_url.startswith("https://transtats.bts.gov/PREZIP/")


@pytest.mark.unit
def test_bts_resource_raises_on_404():
    """A 404 from BTS surfaces as BTSDownloadError, not a generic HTTP error."""
    resource = BTSResource(
        endpoint="https://transtats.bts.gov/PREZIP",
        fixture_file=None,
    )

    fake_response = MagicMock()
    fake_response.status = 404
    fake_response.read = AsyncMock(return_value=b"")
    fake_builder = MagicMock()
    fake_builder.build.return_value.send = AsyncMock(return_value=fake_response)
    fake_client = MagicMock()
    fake_client.get.return_value = fake_builder

    with patch.object(BTSResource, "_client", new_callable=lambda: fake_client):
        with pytest.raises(BTSDownloadError, match="status 404"):
            asyncio.run(resource.download_month(2024, 1))
