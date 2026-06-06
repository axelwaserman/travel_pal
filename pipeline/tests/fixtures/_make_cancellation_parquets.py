"""Generate stub cancellation Parquet fixtures for the frontend E2E smoke test.

CI E2E uploads these to SeaweedFS via the frontend_exports stub path so the
browser smoke test renders both Highcharts bars without running the whole BTS
pipeline. Re-run after schema changes; commit the resulting Parquet files.
"""

from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

OUT_DIR = Path(__file__).parent

CARRIER = pa.table(
    {
        "origin_icao": ["KJFK"] * 4,
        "carrier_icao": ["AAL", "DAL", "UAL", "JBU"],
        "carrier_name": [
            "American Airlines",
            "Delta Air Lines",
            "United Airlines",
            "JetBlue Airways",
        ],
        "total_scheduled": [1000, 900, 800, 700],
        "cancelled": [50, 27, 16, 14],
        "cancellation_rate": [0.05, 0.03, 0.02, 0.02],
        "period_start": pa.array([date(2024, 1, 1)] * 4, type=pa.date32()),
        "period_end": pa.array([date(2024, 12, 31)] * 4, type=pa.date32()),
    }
)

ROUTE = pa.table(
    {
        "origin_icao": ["KJFK"] * 5,
        "destination_icao": ["KLAX", "KORD", "KMIA", "KATL", "KSEA"],
        "total_scheduled": [400, 350, 300, 280, 250],
        "cancelled": [20, 14, 9, 8, 5],
        "cancellation_rate": [0.05, 0.04, 0.03, 0.029, 0.02],
        "period_start": pa.array([date(2024, 1, 1)] * 5, type=pa.date32()),
        "period_end": pa.array([date(2024, 12, 31)] * 5, type=pa.date32()),
    }
)


def main() -> None:
    pq.write_table(CARRIER, OUT_DIR / "carrier_cancellations.parquet")
    pq.write_table(ROUTE, OUT_DIR / "route_cancellations.parquet")
    print(f"wrote carrier ({CARRIER.num_rows} rows) + route ({ROUTE.num_rows} rows) parquets")


if __name__ == "__main__":
    main()
