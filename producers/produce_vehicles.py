"""
produce_vehicles.py
-------------------
Generates 120 synthetic jeepney vehicles assigned to routes and operators,
then POSTs to POST /ingest/vehicles.

FK dependencies: routes (R01–R12) and operators (OPR-001 … OPR-030) must exist first.

Vehicle distribution:
  - 70% traditional jeepneys (capacity 16, diesel/euro4_diesel)
  - 30% modernized PUVs (capacity 23, euro4_diesel/electric)
  - 10 vehicles per route on average
"""

import random
from datetime import datetime, timezone

import httpx

API_BASE = "http://fastapi:8000"
ENDPOINT = f"{API_BASE}/ingest/vehicles"

SEED = 42
random.seed(SEED)

ROUTE_IDS = [f"R{i:02d}" for i in range(1, 13)]
OPERATOR_IDS = [f"OPR-{i:03d}" for i in range(1, 31)]

VEHICLE_TYPES = ["traditional", "modernized_PUV"]
FUEL_TYPES_BY_TYPE = {
    "traditional":    ["diesel", "euro4_diesel"],
    "modernized_PUV": ["euro4_diesel", "electric"],
}

PLATE_LETTERS = ["DBX", "DBA", "DBC", "DBD", "DBE", "DBF", "DBG", "DBH"]


def make_plate(used: set) -> str:
    while True:
        letters = random.choice(PLATE_LETTERS)
        digits = random.randint(1000, 9999)
        plate = f"{letters}-{digits}"
        if plate not in used:
            used.add(plate)
            return plate


def generate_vehicles(total: int = 120) -> list[dict]:
    vehicles = []
    used_plates: set[str] = set()

    route_alloc = {r: 10 for r in ROUTE_IDS}
    for r in ["R02", "R05", "R06", "R07", "R11"]:
        route_alloc[r] += 1
    for r in ["R01", "R03", "R04", "R08", "R09"]:
        route_alloc[r] -= 1

    vid = 1
    for route_id, count in route_alloc.items():
        for _ in range(count):
            modern_prob = 0.45 if route_id in ("R02", "R11", "R06") else 0.25
            vtype = "modernized_PUV" if random.random() < modern_prob else "traditional"

            capacity = 23 if vtype == "modernized_PUV" else 16
            fuel = random.choice(FUEL_TYPES_BY_TYPE[vtype])

            if vtype == "traditional":
                year = random.randint(2005, 2019)
                daily_fuel = round(random.uniform(600, 900), 2)
            else:
                year = random.randint(2019, 2024)
                daily_fuel = round(
                    random.uniform(
                        200, 400) if fuel == "electric" else random.uniform(400, 650),
                    2,
                )

            operator_id = random.choice(OPERATOR_IDS)

            vehicles.append({
                "vehicle_id": f"VHC-{vid:03d}",
                "plate_number": make_plate(used_plates),
                "vehicle_type": vtype,
                "capacity": capacity,
                "fuel_type": fuel,
                "year_manufactured": year,
                "route_assigned": route_id,
                "operator_id": operator_id,
                "avg_fuel_cost_daily_php": daily_fuel,
                "is_active": random.random() < 0.92,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            vid += 1

    return vehicles


def main():
    vehicles = generate_vehicles(120)
    print(f"[produce_vehicles] Posting {len(vehicles)} vehicles to {ENDPOINT}")
    with httpx.Client(timeout=60) as client:
        resp = client.post(ENDPOINT, json=vehicles)
        resp.raise_for_status()
        result = resp.json()
    print(f"[produce_vehicles] ✓ Response: {result}")


if __name__ == "__main__":
    main()
