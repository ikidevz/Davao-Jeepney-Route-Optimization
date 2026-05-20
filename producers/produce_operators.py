"""
produce_operators.py
--------------------
Generates ~30 synthetic jeepney operators/cooperatives and POSTs them to
POST /ingest/operators on the FastAPI ingestion service.

FK dependencies: none (operators are root-level alongside routes)
"""

import random
from datetime import datetime, timezone

import httpx

API_BASE = "http://fastapi:8000"
ENDPOINT = f"{API_BASE}/ingest/operators"

SEED = 42
random.seed(SEED)

# Real Davao districts for base_district
DAVAO_DISTRICTS = [
    "Agdao", "Baguio", "Buhangin", "Bunawan", "Calinan",
    "Marilog", "Paquibato", "Poblacion", "Talomo", "Toril", "Tugbok",
]

# Cooperative / operator name components grounded in Davao context
COOP_PREFIXES = [
    "Bankerohan", "Toril", "Matina", "Agdao", "Buhangin",
    "Calinan", "Ecoland", "Bajada", "Poblacion", "Mintal",
    "Panacan", "Sasa", "Talomo", "Tibungco", "Davao",
]
COOP_SUFFIXES = [
    "Transport Cooperative", "Jeepney Operators Association",
    "PUV Cooperative", "Transport Services Cooperative",
    "Multi-Purpose Transport Coop", "Haulers Cooperative",
]

INDIVIDUAL_SURNAMES = [
    "Santos", "Reyes", "Cruz", "Garcia", "Mendoza",
    "Torres", "Flores", "Ramos", "Dela Cruz", "Villanueva",
    "Bautista", "Aquino", "Gonzales", "Ramirez", "Soriano",
]

FRANCHISE_TYPES = ["individual", "cooperative", "corporation"]
FRANCHISE_WEIGHTS = [0.35, 0.50, 0.15]


def make_ph_mobile() -> str:
    """Generate a synthetic Philippine mobile number."""
    prefix = random.choice(
        ["0917", "0918", "0919", "0927", "0928", "0939", "0947"])
    return f"{prefix}{random.randint(1000000, 9999999)}"


def generate_operators(n: int = 30) -> list[dict]:
    operators = []
    used_names: set[str] = set()

    for i in range(1, n + 1):
        operator_id = f"OPR-{i:03d}"
        franchise_type = random.choices(
            FRANCHISE_TYPES, weights=FRANCHISE_WEIGHTS, k=1)[0]

        if franchise_type == "individual":
            surname = random.choice(INDIVIDUAL_SURNAMES)
            # Avoid duplicate names
            given = random.choice(["Juan", "Pedro", "Jose", "Maria", "Ricardo",
                                   "Eduardo", "Roberto", "Antonio", "Carmelo", "Renato"])
            name = f"{given} {surname}"
        elif franchise_type == "corporation":
            city_part = random.choice(COOP_PREFIXES)
            name = f"{city_part} Transport Corporation"
        else:
            city_part = random.choice(COOP_PREFIXES)
            suffix = random.choice(COOP_SUFFIXES)
            name = f"{city_part} {suffix}"

        # Deduplicate
        base_name = name
        counter = 2
        while name in used_names:
            name = f"{base_name} {counter}"
            counter += 1
        used_names.add(name)

        if franchise_type == "individual":
            num_units = random.randint(1, 5)
        elif franchise_type == "cooperative":
            num_units = random.randint(8, 40)
        else:
            num_units = random.randint(15, 60)

        operators.append({
            "operator_id": operator_id,
            "operator_name": name,
            "contact_number": make_ph_mobile(),
            "franchise_type": franchise_type,
            "num_units": num_units,
            "base_district": random.choice(DAVAO_DISTRICTS),
            "is_compliant_puv": random.random() < 0.60,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return operators


def main():
    operators = generate_operators(30)
    print(
        f"[produce_operators] Posting {len(operators)} operators to {ENDPOINT}")
    with httpx.Client(timeout=30) as client:
        resp = client.post(ENDPOINT, json=operators)
        resp.raise_for_status()
        result = resp.json()
    print(f"[produce_operators] ✓ Response: {result}")


if __name__ == "__main__":
    main()
