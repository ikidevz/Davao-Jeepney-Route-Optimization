"""
produce_passengers.py
---------------------
Generates 5,000 synthetic passenger survey records and POSTs them to
POST /ingest/passengers.

Records are crafted to naturally form 5 clusters when K-Means is later run:
  Cluster 0 — Student Commuters   : high freq, low fare, school destination
  Cluster 1 — Market Workers      : AM peak, Toril/Calinan → Bankerohan
  Cluster 2 — CBD Workers         : daily, higher fare, Poblacion/Lanang dest
  Cluster 3 — Underserved Riders  : 2+ transfers, long wait, low satisfaction ← A/B target
  Cluster 4 — Occasional Riders   : low freq, mall/hospital trips

FK dependencies: routes (R01–R40) must exist.
"""

import os
import random
from datetime import date, datetime, timedelta, timezone

import boto3
import httpx
import numpy as np
from botocore.config import Config

API_BASE = os.getenv("FASTAPI_URL", "http://fastapi:8000")
ENDPOINT = f"{API_BASE}/ingest/passengers"
CHUNK_SIZE = 500
SEED = 42

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "minioLocalAccessKey")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "minioLocalSecretKey123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "raw")
ENTITY = "passengers"


def clear_minio_partition(partition_date: str | None = None) -> None:
    """Delete all parquet files for this entity+date so re-runs don't accumulate stale chunks."""
    run_date = partition_date or date.today().isoformat()
    prefix = f"jeepney/{ENTITY}/date={run_date}/"
    s3 = boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS,
        aws_secret_access_key=MINIO_SECRET,
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )
    paginator = s3.get_paginator("list_objects_v2")
    keys_deleted = 0
    for page in paginator.paginate(Bucket=MINIO_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            s3.delete_object(Bucket=MINIO_BUCKET, Key=obj["Key"])
            keys_deleted += 1
    if keys_deleted:
        print(
            f"[produce_passengers] 🗑  Cleared {keys_deleted} stale file(s) from s3://{MINIO_BUCKET}/{prefix}")
    else:
        print(
            f"[produce_passengers] ✓ Partition s3://{MINIO_BUCKET}/{prefix} was already clean")


rng = np.random.default_rng(SEED)
random.seed(SEED)

# ── Davao barangays by district ───────────────────────────────────────────────
DISTRICT_BARANGAYS: dict[str, list[str]] = {
    "Agdao":      ["Agdao", "Sto. Niño", "Piapi", "Obrero", "Leon Garcia"],
    "Buhangin":   ["Buhangin Proper", "Communal", "Mandug", "Sasa", "Lanang",
                   "Tibungco", "Callawa", "Indangan", "New Carmen"],
    "Bunawan":    ["Bunawan", "Gatungan", "Lasang", "Magtuod", "Alejandra Navarro"],
    "Calinan":    ["Calinan", "Mintal", "Biao Escuela", "Sirib", "Wangan",
                   "Lacson", "Tawan-Tawan", "Riverside", "Malagos"],
    "Marilog":    ["Marilog", "Daliaon Plantation", "Lubogan"],
    "Paquibato":  ["Panacan", "Mapula", "Lumiad", "Colosas", "New Visayas"],
    "Poblacion":  ["Bankerohan", "Davao City Proper", "San Pedro", "Bajada",
                   "Obrero", "Bangkal", "Poblacion"],
    "Talomo":     ["Matina", "Catalunan Grande", "Catalunan Pequeño", "Talomo",
                   "Maa", "Catitipan", "Ecoland", "Bucana", "Dumoy", "Langub",
                   "GSIS Heights"],
    "Toril":      ["Toril", "Ulas", "Bayabas", "Sirawan", "Baracatan",
                   "Colo", "Puan", "Darong"],
    "Tugbok":     ["Tugbok", "Tacunan", "New Valencia", "Tomobe"],
    "Baguio":     ["Baguio", "Biao Guianga"],
}


CLUSTER_DISTRICT_BIAS: dict[int, list[str]] = {
    0: ["Talomo", "Buhangin", "Agdao"],
    1: ["Toril", "Calinan", "Tugbok"],
    2: ["Poblacion", "Buhangin", "Talomo"],
    3: ["Paquibato", "Marilog", "Bunawan", "Calinan"],
    4: ["Talomo", "Buhangin", "Toril", "Agdao"],
}


CLUSTER_ROUTE_BIAS: dict[int, list[str]] = {
    # Cluster 0 — Student Commuters (Talomo, Buhangin, Agdao)
    # Urban inner-city corridors with school-side routes
    0: ["R02", "R06", "R12", "R04", "R03", "R14", "R17", "R33", "R36"],

    # Cluster 1 — Market Workers (Toril, Calinan, Tugbok)
    # Long-haul outer routes terminating at Bankerohan market
    1: ["R01", "R05", "R09", "R18", "R19", "R20", "R30", "R39", "R40"],

    # Cluster 2 — CBD Workers (Poblacion, Buhangin, Talomo)
    # Express + high-frequency CBD-bound routes
    2: ["R02", "R06", "R11", "R07", "R13", "R15", "R16", "R25", "R38"],

    # Cluster 3 — Underserved Riders (Paquibato, Marilog, Bunawan, Calinan)
    # Remote/fringe routes requiring transfers — A/B test target
    3: ["R05", "R09", "R10", "R22", "R23", "R24", "R26", "R27", "R28", "R29", "R32"],

    # Cluster 4 — Occasional Riders (Talomo, Buhangin, Toril, Agdao)
    # Mixed urban routes used for mall/hospital/occasional trips
    4: ["R01", "R02", "R04", "R08", "R21", "R31", "R34", "R35", "R37"],
}

DESTINATION_BY_CLUSTER: dict[int, list[str]] = {
    0: ["school"],
    1: ["market", "work"],
    2: ["work"],
    3: ["work", "market", "hospital"],
    4: ["mall", "hospital", "market"],
}

PURPOSE_BY_CLUSTER: dict[int, list[str]] = {
    0: ["daily_commute"],
    1: ["daily_commute"],
    2: ["daily_commute"],
    3: ["daily_commute", "occasional"],
    4: ["occasional", "weekend_only"],
}

INCOME_BY_CLUSTER: dict[int, list[tuple[str, float]]] = {
    0: [("low", 0.70), ("middle", 0.30)],
    1: [("low", 0.80), ("middle", 0.20)],
    2: [("middle", 0.60), ("high", 0.40)],
    3: [("low", 0.85), ("middle", 0.15)],
    4: [("low", 0.40), ("middle", 0.45), ("high", 0.15)],
}


def weighted_choice(choices: list[tuple[str, float]]) -> str:
    items, weights = zip(*choices)
    return random.choices(items, weights=weights, k=1)[0]


def random_survey_date() -> str:
    start = date(2024, 1, 1)
    offset = rng.integers(0, 365)
    return (start + timedelta(days=int(offset))).isoformat()


def cluster_params(cluster_id: int) -> dict:
    """Return realistic feature distributions per cluster."""
    if cluster_id == 0:   # Student Commuters
        return dict(
            trips_per_week=int(np.clip(rng.normal(10, 1.5), 5, 14)),
            avg_fare=round(
                float(np.clip(rng.normal(14.5, 1.0), 13.0, 18.0)), 2),
            transfers=int(np.clip(rng.integers(0, 2), 0, 3)),
            wait_time=int(np.clip(rng.normal(12, 4), 3, 30)),
            travel_time=int(np.clip(rng.normal(25, 8), 10, 60)),
            satisfaction=int(np.clip(rng.integers(3, 6), 1, 5)),
            prefers_aircon=random.random() < 0.65,
        )
    elif cluster_id == 1:  # Market Workers
        return dict(
            trips_per_week=int(np.clip(rng.normal(8, 1.5), 4, 12)),
            avg_fare=round(
                float(np.clip(rng.normal(16.0, 2.0), 13.0, 25.0)), 2),
            transfers=int(np.clip(rng.integers(0, 2), 0, 3)),
            wait_time=int(np.clip(rng.normal(18, 5), 5, 40)),
            travel_time=int(np.clip(rng.normal(40, 10), 20, 80)),
            satisfaction=int(np.clip(rng.integers(2, 5), 1, 5)),
            prefers_aircon=random.random() < 0.30,
        )
    elif cluster_id == 2:  # CBD Workers
        return dict(
            trips_per_week=int(np.clip(rng.normal(9, 1.0), 6, 14)),
            avg_fare=round(
                float(np.clip(rng.normal(19.0, 3.0), 13.0, 35.0)), 2),
            transfers=int(np.clip(rng.integers(0, 2), 0, 2)),
            wait_time=int(np.clip(rng.normal(10, 3), 3, 20)),
            travel_time=int(np.clip(rng.normal(30, 7), 15, 60)),
            satisfaction=int(np.clip(rng.integers(3, 6), 1, 5)),
            prefers_aircon=random.random() < 0.75,
        )
    elif cluster_id == 3:  # Underserved Riders ← A/B test target
        return dict(
            trips_per_week=int(np.clip(rng.normal(6, 2), 1, 12)),
            avg_fare=round(
                float(np.clip(rng.normal(22.0, 4.0), 13.0, 40.0)), 2),
            transfers=int(np.clip(rng.integers(2, 4), 0, 3)),
            wait_time=int(np.clip(rng.normal(30, 6), 15, 60)),
            travel_time=int(np.clip(rng.normal(55, 12), 30, 100)),
            satisfaction=int(np.clip(rng.integers(1, 3), 1, 5)),
            prefers_aircon=random.random() < 0.50,
        )
    else:                  # Occasional Riders (cluster 4)
        return dict(
            trips_per_week=int(np.clip(rng.normal(2, 1.0), 0, 6)),
            avg_fare=round(
                float(np.clip(rng.normal(15.0, 2.0), 13.0, 25.0)), 2),
            transfers=int(np.clip(rng.integers(0, 3), 0, 3)),
            wait_time=int(np.clip(rng.normal(20, 7), 5, 45)),
            travel_time=int(np.clip(rng.normal(35, 12), 10, 80)),
            satisfaction=int(np.clip(rng.integers(2, 5), 1, 5)),
            prefers_aircon=random.random() < 0.55,
        )


# Cluster size distribution: target ~5,000 total with Cluster 3 at ~1,000
CLUSTER_SIZES = {
    0: 1200,   # Student Commuters
    1: 1000,   # Market Workers
    2: 900,    # CBD Workers
    3: 1000,   # Underserved Riders (A/B eligible)
    4: 900,    # Occasional Riders
}


def generate_passengers() -> list[dict]:
    records = []
    pax_num = 1

    for cluster_id, count in CLUSTER_SIZES.items():
        districts = CLUSTER_DISTRICT_BIAS[cluster_id]
        routes = CLUSTER_ROUTE_BIAS[cluster_id]

        for _ in range(count):
            origin_district = random.choice(districts)
            origin_barangay = random.choice(
                DISTRICT_BARANGAYS[origin_district])
            primary_route = random.choice(routes)
            params = cluster_params(cluster_id)
            income = weighted_choice(INCOME_BY_CLUSTER[cluster_id])
            dest_type = random.choice(DESTINATION_BY_CLUSTER[cluster_id])
            purpose = random.choice(PURPOSE_BY_CLUSTER[cluster_id])

            records.append({
                "passenger_id":        f"PAX-{pax_num:04d}",
                "survey_date":         random_survey_date(),
                "origin_barangay":     origin_barangay,
                "origin_district":     origin_district,
                "destination_type":    dest_type,
                "trip_purpose":        purpose,
                "primary_route_used":  primary_route,
                "trips_per_week":      params["trips_per_week"],
                "avg_fare_paid_php":   params["avg_fare"],
                "transfers_required":  params["transfers"],
                "wait_time_min":       params["wait_time"],
                "travel_time_min":     params["travel_time"],
                "satisfaction_score":  params["satisfaction"],
                "income_bracket":      income,
                "prefers_aircon":      params["prefers_aircon"],
                # cluster_id and cluster_label are NULL at staging layer
                # (populated later by science/clustering.py)
                "cluster_id":          None,
                "cluster_label":       None,
                "created_at":          datetime.now(timezone.utc).isoformat(),
            })
            pax_num += 1

    return records


def main():
    passengers = generate_passengers()
    total = len(passengers)
    print(
        f"[produce_passengers] Generating {total:,} passenger survey records")
    print(f"[produce_passengers] Endpoint: {ENDPOINT}  |  Chunk: {CHUNK_SIZE}")

    clear_minio_partition()

    with httpx.Client(timeout=60) as client:
        for i in range(0, total, CHUNK_SIZE):
            batch = passengers[i: i + CHUNK_SIZE]
            resp = client.post(ENDPOINT, json=batch, timeout=60)
            resp.raise_for_status()
            print(
                f"[produce_passengers]   chunk {i//CHUNK_SIZE + 1}: {resp.json()}")

    print(f"[produce_passengers] ✓ Done — {total:,} records ingested")

    # Cluster breakdown summary
    print("\n[produce_passengers] Cluster breakdown:")
    for cid, count in CLUSTER_SIZES.items():
        labels = {
            0: "Student Commuters",
            1: "Market Workers",
            2: "CBD Workers",
            3: "Underserved Riders ← A/B target",
            4: "Occasional Riders",
        }
        print(f"  Cluster {cid} ({labels[cid]}): {count:,} records")


if __name__ == "__main__":
    main()
