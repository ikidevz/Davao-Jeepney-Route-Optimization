"""
produce_routes.py
-----------------
Generates 12 real Davao City jeepney routes and POSTs them to
POST /ingest/routes on the FastAPI ingestion service.

FK dependencies: none (routes are root-level)
"""

import httpx
from datetime import datetime, timezone

API_BASE = "http://fastapi:8000"
ENDPOINT = f"{API_BASE}/ingest/routes"

# 12 real Davao jeepney routes grounded in LTFRB data
ROUTES = [
    {
        "route_id": "R01",
        "route_name": "Bankerohan–Toril",
        "origin": "Bankerohan Market Terminal",
        "destination": "Toril Public Market",
        "district_covered": "Toril",
        "route_length_km": 22.40,
        "num_stops": 18,
        "base_fare_php": 13.00,
        "peak_frequency_min": 8,
        "off_peak_frequency_min": 15,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R02",
        "route_name": "Ecoland–SM Lanang",
        "origin": "Ecoland Bus Terminal",
        "destination": "SM City Lanang",
        "district_covered": "Buhangin",
        "route_length_km": 14.80,
        "num_stops": 14,
        "base_fare_php": 13.00,
        "peak_frequency_min": 6,
        "off_peak_frequency_min": 12,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R03",
        "route_name": "Agdao Loop",
        "origin": "Agdao Public Market",
        "destination": "Agdao Public Market",
        "district_covered": "Agdao",
        "route_length_km": 9.60,
        "num_stops": 12,
        "base_fare_php": 13.00,
        "peak_frequency_min": 7,
        "off_peak_frequency_min": 14,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R04",
        "route_name": "Matina–Davao Medical Center",
        "origin": "Matina Town Square",
        "destination": "Davao Medical Center",
        "district_covered": "Talomo",
        "route_length_km": 11.20,
        "num_stops": 13,
        "base_fare_php": 13.00,
        "peak_frequency_min": 9,
        "off_peak_frequency_min": 18,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R05",
        "route_name": "Calinan–Bankerohan",
        "origin": "Calinan Market Terminal",
        "destination": "Bankerohan Market Terminal",
        "district_covered": "Calinan",
        "route_length_km": 29.50,
        "num_stops": 22,
        "base_fare_php": 13.00,
        "peak_frequency_min": 12,
        "off_peak_frequency_min": 25,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R06",
        "route_name": "Poblacion–Buhangin",
        "origin": "Poblacion District Hall",
        "destination": "Buhangin District Terminal",
        "district_covered": "Poblacion",
        "route_length_km": 8.30,
        "num_stops": 10,
        "base_fare_php": 13.00,
        "peak_frequency_min": 6,
        "off_peak_frequency_min": 10,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R07",
        "route_name": "Bajada–Tibungco",
        "origin": "Bajada Terminal",
        "destination": "Tibungco Market",
        "district_covered": "Buhangin",
        "route_length_km": 12.70,
        "num_stops": 15,
        "base_fare_php": 13.00,
        "peak_frequency_min": 8,
        "off_peak_frequency_min": 16,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R08",
        "route_name": "Talomo–Ulas Loop",
        "origin": "Talomo Public Market",
        "destination": "Ulas Barangay Hall",
        "district_covered": "Talomo",
        "route_length_km": 10.10,
        "num_stops": 11,
        "base_fare_php": 13.00,
        "peak_frequency_min": 10,
        "off_peak_frequency_min": 20,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R09",
        "route_name": "Mintal–Bankerohan",
        "origin": "Mintal Market",
        "destination": "Bankerohan Market Terminal",
        "district_covered": "Calinan",
        "route_length_km": 18.90,
        "num_stops": 16,
        "base_fare_php": 13.00,
        "peak_frequency_min": 11,
        "off_peak_frequency_min": 22,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R10",
        "route_name": "Panacan–Agdao",
        "origin": "Panacan Wharf Terminal",
        "destination": "Agdao Public Market",
        "district_covered": "Paquibato",
        "route_length_km": 16.40,
        "num_stops": 14,
        "base_fare_php": 13.00,
        "peak_frequency_min": 10,
        "off_peak_frequency_min": 20,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R11",
        "route_name": "Matina–SM Lanang Express",
        "origin": "Matina Town Square",
        "destination": "SM City Lanang",
        "district_covered": "Talomo",
        "route_length_km": 13.60,
        "num_stops": 9,
        "base_fare_php": 15.00,
        "peak_frequency_min": 7,
        "off_peak_frequency_min": 13,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "route_id": "R12",
        "route_name": "Sasa–Davao City Hall",
        "origin": "Sasa Port Terminal",
        "destination": "Davao City Hall",
        "district_covered": "Buhangin",
        "route_length_km": 7.80,
        "num_stops": 10,
        "base_fare_php": 13.00,
        "peak_frequency_min": 8,
        "off_peak_frequency_min": 15,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
]


def main():
    print(f"[produce_routes] Posting {len(ROUTES)} routes to {ENDPOINT}")
    with httpx.Client(timeout=30) as client:
        resp = client.post(ENDPOINT, json=ROUTES)
        resp.raise_for_status()
        result = resp.json()
    print(f"[produce_routes] ✓ Response: {result}")


if __name__ == "__main__":
    main()
