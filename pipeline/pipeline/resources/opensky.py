from dataclasses import dataclass
from datetime import datetime, timezone
import httpx
import pyarrow as pa


BASE_URL = "https://opensky-network.org/api/flights"


@dataclass
class FlightRecord:
    icao24: str
    callsign: str
    first_seen: int
    last_seen: int
    est_departure_airport: str | None
    est_arrival_airport: str | None


class OpenSkyAdapter:
    """Thin adapter over the OpenSky REST API. Swap this file to change data source."""

    def fetch_departures(
        self, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        begin = int(datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc).timestamp())
        end = int(datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc).timestamp())
        response = httpx.get(
            f"{BASE_URL}/departure",
            params={"airport": airport_icao, "begin": begin, "end": end},
            timeout=30,
        )
        if response.status_code == 404:
            return self._to_arrow([])
        response.raise_for_status()
        return self._to_arrow(response.json() or [])

    def fetch_arrivals(
        self, airport_icao: str, start_date: str, end_date: str
    ) -> pa.Table:
        begin = int(datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc).timestamp())
        end = int(datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc).timestamp())
        response = httpx.get(
            f"{BASE_URL}/arrival",
            params={"airport": airport_icao, "begin": begin, "end": end},
            timeout=30,
        )
        if response.status_code == 404:
            return self._to_arrow([])
        response.raise_for_status()
        return self._to_arrow(response.json() or [])

    def _to_arrow(self, records: list[dict]) -> pa.Table:
        records = records or []
        return pa.table(
            {
                "icao24": [r["icao24"] for r in records],
                "callsign": [r.get("callsign", "").strip() for r in records],
                "first_seen": [r["firstSeen"] for r in records],
                "last_seen": [r["lastSeen"] for r in records],
                "est_departure_airport": [
                    r.get("estDepartureAirport") for r in records
                ],
                "est_arrival_airport": [r.get("estArrivalAirport") for r in records],
            }
        )
