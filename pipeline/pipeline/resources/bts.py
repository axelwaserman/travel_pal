"""BTS On-Time Performance resource.

Downloads monthly ZIPs from the BTS PREZIP endpoint and projects the
columns we care about (flight date, carrier IATA, origin/dest IATA,
cancelled/diverted flags, cancellation code) into a PyArrow table.

Fixture mode (`fixture_file` set) bypasses HTTP entirely and reads the
ZIP from disk. CI uses fixture mode so the test suite never hits BTS.
"""

import io
import zipfile
from datetime import timedelta
from functools import cached_property
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
from dagster import ConfigurableResource
from pyarrow import csv as pa_csv
from pyreqwest.client import Client, ClientBuilder


class BTSDownloadError(RuntimeError):
    """Raised when BTS download fails (network error, missing month, bad fixture)."""


_FILENAME_TEMPLATE = "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"

# BTS columns we project; everything else is dropped at parse time so we don't
# pay deserialization cost for fields we don't use.
_BTS_COLUMNS = [
    "FlightDate",
    "Reporting_Airline",
    "Tail_Number",
    "Flight_Number_Reporting_Airline",
    "Origin",
    "Dest",
    "CRSDepTime",
    "Cancelled",
    "CancellationCode",
    "Diverted",
]

_RENAME_MAP = {
    "FlightDate": "flight_date",
    "Reporting_Airline": "carrier_iata",
    "Tail_Number": "tail_number",
    "Flight_Number_Reporting_Airline": "flight_number",
    "Origin": "origin_iata",
    "Dest": "destination_iata",
    "CRSDepTime": "crs_dep_time",
    "Cancelled": "cancelled",
    "CancellationCode": "cancellation_code",
    "Diverted": "diverted",
}


class BTSResource(ConfigurableResource):
    """Pyreqwest-backed BTS On-Time Performance downloader.

    Set ``fixture_file`` to a path string to skip HTTP and use a local ZIP.
    Useful for unit tests + CI E2E where transtats.bts.gov must not be hit.

    Note: Dagster's ConfigurableResource does not support ``pathlib.Path`` as a
    config field type, so ``fixture_file`` is stored as ``str | None`` and
    converted to ``Path`` at use time.
    """

    endpoint: str = "https://transtats.bts.gov/PREZIP"
    fixture_file: str | None = None

    @cached_property
    def _client(self) -> Client:
        return (
            ClientBuilder()
            .connect_timeout(timedelta(seconds=10))
            .timeout(timedelta(seconds=120))
            .build()
        )

    async def download_month(self, year: int, month: int) -> bytes:
        """Return raw BTS ZIP bytes for the given (year, month)."""
        if self.fixture_file is not None:
            fixture_path = Path(self.fixture_file)
            if not fixture_path.exists():
                raise BTSDownloadError(
                    f"BTS fixture not found at {fixture_path} — "
                    "unset BTS_FIXTURE_FILE or point it at a real ZIP"
                )
            return fixture_path.read_bytes()

        url = f"{self.endpoint.rstrip('/')}/{_FILENAME_TEMPLATE.format(year=year, month=month)}"
        response = await self._client.get(url).build().send()
        if response.status != 200:
            raise BTSDownloadError(
                f"BTS download for {year}-{month:02d} failed with status {response.status}"
            )
        payload: bytes = await response.read()  # ty: ignore[unresolved-attribute]  # pyreqwest stubs incomplete
        if not payload.startswith(b"PK"):
            raise BTSDownloadError(
                f"BTS response for {year}-{month:02d} is not a ZIP "
                f"(first 16 bytes: {payload[:16]!r})"
            )
        return payload


def _csv_member(zip_bytes: bytes) -> bytes:
    """Return the bytes of the single CSV inside a BTS ZIP."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise BTSDownloadError(f"BTS ZIP has no .csv member: {zf.namelist()}")
        return zf.read(names[0])


def _parse_year_month(table: pa.Table) -> str:
    """Derive 'YYYY-MM' partition value from the first FlightDate row.

    All rows in a BTS monthly download share a year_month, so we read once
    rather than computing per-row.
    """
    flight_dates = table.column("flight_date").to_pylist()
    if not flight_dates:
        return ""
    first = flight_dates[0]  # 'YYYY-MM-DD'
    return first[:7]


def extract_csv_from_zip(zip_bytes: bytes, origin_iata: str) -> pa.Table:
    """Parse a BTS ZIP and return a projected, airport-filtered PyArrow table.

    Returns columns: flight_date, carrier_iata, tail_number, flight_number,
    origin_iata, destination_iata, crs_dep_time, cancelled, cancellation_code,
    diverted, year_month.
    """
    csv_bytes = _csv_member(zip_bytes)

    parse_options = pa_csv.ParseOptions(quote_char='"', escape_char=False)
    convert_options = pa_csv.ConvertOptions(
        include_columns=_BTS_COLUMNS,
        column_types={col: pa.string() for col in _BTS_COLUMNS},
        strings_can_be_null=True,
        null_values=["", "NA"],
    )
    raw = pa_csv.read_csv(
        io.BytesIO(csv_bytes),
        parse_options=parse_options,
        convert_options=convert_options,
    )

    renamed = raw.rename_columns([_RENAME_MAP[c] for c in raw.column_names])

    # Filter to rows where origin OR destination IATA matches the airport.
    mask_origin = pc.equal(renamed.column("origin_iata"), origin_iata)  # ty: ignore[unresolved-attribute]
    mask_dest = pc.equal(renamed.column("destination_iata"), origin_iata)  # ty: ignore[unresolved-attribute]
    filtered = renamed.filter(pc.or_(mask_origin, mask_dest))  # ty: ignore[unresolved-attribute]

    # Cast string flags to bool: '1.00' → True, anything else → False.
    cancelled_bool = pc.equal(filtered.column("cancelled"), "1.00")  # ty: ignore[unresolved-attribute]
    diverted_bool = pc.equal(filtered.column("diverted"), "1.00")  # ty: ignore[unresolved-attribute]
    filtered = filtered.set_column(
        filtered.column_names.index("cancelled"),
        "cancelled",
        cancelled_bool,
    )
    filtered = filtered.set_column(
        filtered.column_names.index("diverted"),
        "diverted",
        diverted_bool,
    )

    # Stamp partition column.
    year_month = _parse_year_month(filtered)
    filtered = filtered.append_column(
        "year_month",
        pa.array([year_month] * filtered.num_rows, type=pa.string()),
    )

    return filtered
