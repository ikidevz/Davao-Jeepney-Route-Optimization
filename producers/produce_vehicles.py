"""
produce_vehicles.py
-------------------
Generates 280 synthetic jeepney vehicles assigned to 40 routes and operators,
then POSTs to POST /ingest/vehicles.

Expanded from 120 vehicles (12 routes) to 280 vehicles (40 routes).

Vehicle allocation strategy:
  - High-demand inner-city routes (R01–R17): 8–12 vehicles each
  - Mid-demand named routes (R18–R26, R30–R40): 5–8 vehicles each
  - Remote/low-demand routes (R27–R29, R32): 3–5 vehicles each
  - Total target: 280 vehicles

Modernization rates:
  - Express / high-frequency routes (R02, R06, R11, R13, R14, R15, R17): 45%
  - Standard urban routes: 25%
  - Remote rural routes (R27–R29, R32): 10%

FK dependencies: routes (R01–R40) and operators (OPR-001..OPR-030) must exist.
"""

import random
from datetime import datetime, timezone

import httpx

API_BASE = "http://fastapi:8000"
ENDPOINT = f"{API_BASE}/ingest/vehicles"

SEED = 42
random.seed(SEED)

ROUTE_IDS = [f"R{i:02d}" for i in range(1, 41)]
OPERATOR_IDS = [f"OPR-{i:03d}" for i in range(1, 31)]

FUEL_TYPES_BY_TYPE = {
    "traditional":    ["diesel", "euro4_diesel"],
    "modernized_PUV": ["euro4_diesel", "electric"],
}

PLATE_LETTERS = ["DBX", "DBA", "DBC", "DBD", "DBE", "DBF", "DBG", "DBH",
                 "DBI", "DBJ", "DBK", "DBL"]


def make_plate(used: set) -> str:
    while True:
        letters = random.choice(PLATE_LETTERS)
        digits = random.randint(1000, 9999)
        plate = f"{letters}-{digits}"
        if plate not in used:
            used.add(plate)
            return plate


# Vehicle count and modernization rate per route
# Format: route_id -> (count, modern_prob)
ROUTE_CONFIG = {
    # Original routes — preserve original allocations for R01–R12
    "R01": (9,  0.25),   # Bankerohan–Toril (long)
    "R02": (11, 0.45),   # Ecoland–SM Lanang (high demand, express)
    "R03": (9,  0.25),   # Agdao Loop
    "R04": (9,  0.25),   # Matina–Davao Medical Center
    "R05": (11, 0.25),   # Calinan–Bankerohan (long)
    "R06": (11, 0.45),   # Poblacion–Buhangin (high frequency)
    "R07": (11, 0.30),   # Bajada–Tibungco
    "R08": (9,  0.25),   # Talomo–Ulas Loop
    "R09": (9,  0.25),   # Mintal–Bankerohan
    "R10": (10, 0.25),   # Panacan–Agdao
    "R11": (11, 0.45),   # Matina–SM Lanang Express (modernized)
    "R12": (10, 0.30),   # Sasa–Davao City Hall
    # New CBD numbered routes (high frequency, smaller fleet)
    "R13": (8,  0.40),   # Route 1 – Marfori–Chinatown
    "R14": (10, 0.45),   # Route 2 – Ecoland–Chinatown
    "R15": (8,  0.40),   # Route 4 – Claveria–SPMC
    "R16": (8,  0.35),   # Route 5 – Bankerohan–Agdao
    "R17": (8,  0.45),   # Route 10 – SPMC–Buhangin
    # Toril inner routes
    "R18": (7,  0.20),   # Toril–Roxas
    "R19": (6,  0.20),   # Daliao–Bankerohan
    "R20": (5,  0.15),   # Puan–Bankerohan
    "R21": (4,  0.15),   # Inawayan–Toril (feeder)
    # Bunawan routes
    "R22": (7,  0.25),   # Bunawan–SM Lanang via Sasa
    "R23": (6,  0.20),   # Lasang–Agdao
    "R24": (5,  0.15),   # Magtuod–Bankerohan
    # Paquibato additional
    "R25": (7,  0.30),   # Panacan–SM Lanang
    "R26": (6,  0.20),   # Panacan–Bankerohan via Cabaguio
    # Marilog (remote — fewest vehicles, lowest modernization)
    "R27": (4,  0.10),   # Marilog–Bankerohan
    "R28": (3,  0.10),   # Tamugan–Mintal
    "R29": (3,  0.10),   # Marahan–Calinan
    # Tugbok
    "R30": (6,  0.20),   # Tugbok–Bankerohan via Roxas
    "R31": (5,  0.20),   # New Valencia–Ecoland
    # Baguio (most remote)
    "R32": (3,  0.10),   # Guianga–Calinan
    # Talomo additional
    "R33": (7,  0.30),   # Ma-a–Agdao
    "R34": (6,  0.20),   # Bago Aplaya–Bankerohan
    "R35": (6,  0.25),   # Catitipan–Bankerohan
    # Buhangin additional
    "R36": (7,  0.25),   # Tibungco–Bankerohan via Cabaguio
    "R37": (5,  0.20),   # Mandug–Agdao
    "R38": (6,  0.25),   # Indangan–SM Lanang
    # Calinan additional
    "R39": (5,  0.15),   # Sirib–Bankerohan
    "R40": (4,  0.15),   # Wa-an–Mintal
}


def generate_vehicles() -> list[dict]:
    vehicles = []
    used_plates: set[str] = set()
    vid = 1

    for route_id in ROUTE_IDS:
        count, modern_prob = ROUTE_CONFIG[route_id]
        for _ in range(count):
            vtype = "modernized_PUV" if random.random() < modern_prob else "traditional"
            capacity = 23 if vtype == "modernized_PUV" else 16
            fuel = random.choice(FUEL_TYPES_BY_TYPE[vtype])

            if vtype == "traditional":
                year = random.randint(2005, 2019)
                daily_fuel = round(random.uniform(600, 900), 2)
            else:
                year = random.randint(2019, 2024)
                daily_fuel = round(
                    random.uniform(200, 400) if fuel == "electric"
                    else random.uniform(400, 650), 2
                )

            vehicles.append({
                "vehicle_id":             f"VHC-{vid:03d}",
                "plate_number":           make_plate(used_plates),
                "vehicle_type":           vtype,
                "capacity":               capacity,
                "fuel_type":              fuel,
                "year_manufactured":      year,
                "route_assigned":         route_id,
                "operator_id":            random.choice(OPERATOR_IDS),
                "avg_fuel_cost_daily_php": daily_fuel,
                "is_active":              random.random() < 0.92,
                "created_at":             datetime.now(timezone.utc).isoformat(),
            })
            vid += 1

    return vehicles


def main():
    vehicles = generate_vehicles()
    total = len(vehicles)
    print(
        f"[produce_vehicles] Generating {total} vehicles across {len(ROUTE_IDS)} routes")

    # Summary by route
    from collections import Counter
    route_counts = Counter(v["route_assigned"] for v in vehicles)
    modern_counts = Counter(
        v["route_assigned"] for v in vehicles if v["vehicle_type"] == "modernized_PUV"
    )
    print(f"[produce_vehicles] Vehicle distribution (total: {total}):")
    for rid in ROUTE_IDS:
        mod = modern_counts.get(rid, 0)
        tot = route_counts.get(rid, 0)
        print(f"  {rid}: {tot} vehicles ({mod} modernized)")

    print(f"\n[produce_vehicles] Posting {total} vehicles to {ENDPOINT}")
    with httpx.Client(timeout=60) as client:
        resp = client.post(ENDPOINT, json=vehicles)
        resp.raise_for_status()
        result = resp.json()
    print(f"[produce_vehicles] ✓ Response: {result}")


if __name__ == "__main__":
    main()
