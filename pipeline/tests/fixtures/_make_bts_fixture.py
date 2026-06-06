"""One-off generator for the BTS test fixture.

Run once and commit the output ZIP. Re-run only if the BTS schema changes.
This file is part of the test fixture set, not production code.
"""

import csv
import io
import zipfile
from pathlib import Path

ROWS = [
    # FlightDate, Reporting_Airline, Tail_Number, Flight_Number_Reporting_Airline,
    # Origin, Dest, CRSDepTime, Cancelled, CancellationCode, Diverted
    ("2024-01-01", "AA", "N123AA", "100", "JFK", "LAX", "0700", "0.00", "", "0.00"),
    ("2024-01-01", "AA", "N124AA", "101", "JFK", "ORD", "0800", "1.00", "B", "0.00"),
    ("2024-01-02", "AA", "N125AA", "102", "JFK", "MIA", "0900", "0.00", "", "0.00"),
    ("2024-01-02", "DL", "N201DL", "201", "JFK", "ATL", "0710", "0.00", "", "0.00"),
    ("2024-01-03", "DL", "N202DL", "202", "JFK", "SEA", "0810", "1.00", "A", "0.00"),
    ("2024-01-03", "DL", "N203DL", "203", "LAX", "JFK", "0900", "0.00", "", "0.00"),
    ("2024-01-04", "AA", "N126AA", "103", "ORD", "JFK", "1000", "0.00", "", "1.00"),
    ("2024-01-04", "DL", "N204DL", "204", "JFK", "BOS", "1100", "1.00", "C", "0.00"),
    # Row that should be filtered out (LAX→ORD, no JFK):
    ("2024-01-05", "UA", "N301UA", "301", "LAX", "ORD", "1200", "0.00", "", "0.00"),
    # Row with unknown IATA (ZZZ): kept in raw extract because filter is
    # origin OR dest = JFK, dropped later by stg_bts_on_time INNER JOIN dim_airport.
    ("2024-01-05", "AA", "N127AA", "104", "JFK", "ZZZ", "1300", "0.00", "", "0.00"),
]

HEADER = [
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


def main() -> None:
    out_path = Path(__file__).parent / "bts_kjfk_2024_01.csv.zip"

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(HEADER)
    writer.writerows(ROWS)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("On_Time_Reporting_Carrier_2024_1.csv", csv_bytes)

    print(f"wrote {out_path} ({out_path.stat().st_size} bytes, {len(ROWS)} rows)")


if __name__ == "__main__":
    main()
