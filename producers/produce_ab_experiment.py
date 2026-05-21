"""
produce_ab_experiment.py
------------------------
Simulates an 8-week A/B experiment on Cluster 3 (Underserved Riders):
  Control   (A): existing multi-transfer route — avg 55 min, 1-2 transfers
  Treatment (B): Matina->SM Lanang express direct — avg 35 min, 0 transfers

Records are POSTed to POST /ingest/ab-experiment.

FK dependencies:
  - passengers (PAX-XXXX) must exist first (produce_passengers.py).
"""

import os
import random
from datetime import date, datetime, timezone

import boto3
import httpx
import numpy as np
from botocore.config import Config

API_BASE = "http://fastapi:8000"
ENDPOINT = f"{API_BASE}/ingest/ab-experiment"
CHUNK_SIZE = 1_000
SEED = 42

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "minioLocalAccessKey")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "minioLocalSecretKey123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "raw")
ENTITY = "ab_experiment"


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
            f"[produce_ab_experiment] 🗑  Cleared {keys_deleted} stale file(s) from s3://{MINIO_BUCKET}/{prefix}")
    else:
        print(
            f"[produce_ab_experiment] ✓ Partition s3://{MINIO_BUCKET}/{prefix} was already clean")


rng = np.random.default_rng(SEED)
random.seed(SEED)

EXPERIMENT_ID = "EXP-001"
N_WEEKS = 8

CLUSTER_SIZES = {0: 1200, 1: 1000, 2: 900, 3: 1000, 4: 900}


def _cluster3_pax_range() -> tuple:
    """Return (start, end) inclusive PAX number range for cluster 3."""
    start = 1
    for cid in sorted(CLUSTER_SIZES):
        if cid == 3:
            return start, start + CLUSTER_SIZES[3] - 1
        start += CLUSTER_SIZES[cid]
    raise RuntimeError("Cluster 3 not found in CLUSTER_SIZES")


_C3_START, _C3_END = _cluster3_pax_range()
CLUSTER_3_COUNT = CLUSTER_SIZES[3]   # 1,000


def passenger_ids_cluster3() -> list:
    return [f"PAX-{i:04d}" for i in range(_C3_START, _C3_END + 1)]


def assign_groups(pax_ids: list) -> dict:
    """50/50 random split into control / treatment (fixed per passenger)."""
    ids = pax_ids.copy()
    random.shuffle(ids)
    half = len(ids) // 2
    groups = {}
    for pid in ids[:half]:
        groups[pid] = "control"
    for pid in ids[half:]:
        groups[pid] = "treatment"
    return groups


def simulate_control_week(week: int) -> dict:
    """Control group (A): existing multi-transfer route."""
    travel_time = int(np.clip(rng.normal(55, 8), 35, 90))
    fare = round(float(np.clip(rng.normal(22.0, 4.0), 13.0, 40.0)), 2)
    transfers = int(rng.integers(1, 3))
    sat_mean = max(1.0, 2.2 - week * 0.04)
    satisfaction = int(np.clip(round(rng.normal(sat_mean, 0.6)), 1, 5))
    would_use_again = random.random() < 0.45
    return dict(
        route_variant="A_existing_route",
        group="control",
        simulated_travel_time_min=travel_time,
        simulated_fare_php=fare,
        transfers_needed=transfers,
        satisfaction_score=satisfaction,
        would_use_again=would_use_again,
    )


def simulate_treatment_week(week: int) -> dict:
    """Treatment group (B): Matina->SM Lanang express direct."""
    travel_time = int(np.clip(rng.normal(35, 5), 20, 55))
    fare = round(float(np.clip(rng.normal(18.0, 2.0), 15.0, 25.0)), 2)
    transfers = 0

    sat_mean = min(5.0, 3.8 + week * 0.08)
    satisfaction = int(np.clip(round(rng.normal(sat_mean, 0.5)), 1, 5))
    would_use_again = random.random() < 0.82
    return dict(
        route_variant="B_express_direct",
        group="treatment",
        simulated_travel_time_min=travel_time,
        simulated_fare_php=fare,
        transfers_needed=transfers,
        satisfaction_score=satisfaction,
        would_use_again=would_use_again,
    )


def generate_experiment_records() -> list:
    pax_ids = passenger_ids_cluster3()
    groups = assign_groups(pax_ids)
    records = []

    for week in range(1, N_WEEKS + 1):
        for pax_id, group in groups.items():
            if group == "control":
                sim = simulate_control_week(week)
            else:
                sim = simulate_treatment_week(week)

            record_id = f"EXP001-{pax_id}-W{week}"
            records.append({
                "experiment_record_id":      record_id,
                "experiment_id":             EXPERIMENT_ID,
                "passenger_id":              pax_id,
                "cluster_id":                3,
                "group":                     sim["group"],
                "route_variant":             sim["route_variant"],
                "test_week":                 week,
                "simulated_travel_time_min": sim["simulated_travel_time_min"],
                "simulated_fare_php":        sim["simulated_fare_php"],
                "transfers_needed":          sim["transfers_needed"],
                "satisfaction_score":        sim["satisfaction_score"],
                "would_use_again":           sim["would_use_again"],
                "created_at":                datetime.now(timezone.utc).isoformat(),
            })

    return records


def print_summary(records: list):
    control = [r for r in records if r["group"] == "control"]
    treatment = [r for r in records if r["group"] == "treatment"]
    print(f"\n[produce_ab_experiment] Experiment summary:")
    print(f"  Total records : {len(records):,}")
    print(f"  Control (A)   : {len(control):,} records")
    print(f"  Treatment (B) : {len(treatment):,} records")
    c_sat = sum(r["satisfaction_score"] for r in control) / len(control)
    t_sat = sum(r["satisfaction_score"] for r in treatment) / len(treatment)
    c_time = sum(r["simulated_travel_time_min"]
                 for r in control) / len(control)
    t_time = sum(r["simulated_travel_time_min"]
                 for r in treatment) / len(treatment)
    print(f"  Avg satisfaction — control: {c_sat:.2f}  treatment: {t_sat:.2f}")
    print(
        f"  Avg travel time  — control: {c_time:.1f} min  treatment: {t_time:.1f} min")


def main():
    print(f"[produce_ab_experiment] Generating A/B experiment records")
    print(f"  Cluster 3 PAX range  : PAX-{_C3_START:04d}..PAX-{_C3_END:04d}")
    print(f"  Cluster 3 passengers : {CLUSTER_3_COUNT:,}")
    print(f"  Weeks                : {N_WEEKS}")
    print(f"  Expected records     : {CLUSTER_3_COUNT * N_WEEKS:,}")
    print(f"  Endpoint             : {ENDPOINT}")

    expected_start = sum(CLUSTER_SIZES[c]
                         for c in sorted(CLUSTER_SIZES) if c < 3) + 1
    expected_end = expected_start + CLUSTER_SIZES[3] - 1
    assert _C3_START == expected_start and _C3_END == expected_end, (
        f"Cluster 3 PAX range mismatch: computed ({_C3_START}–{_C3_END}) "
        f"vs expected ({expected_start}–{expected_end}). "
        "Sync CLUSTER_SIZES with produce_passengers.py."
    )

    records = generate_experiment_records()
    print_summary(records)

    clear_minio_partition()

    print(
        f"\n[produce_ab_experiment] Posting {len(records):,} records in chunks of {CHUNK_SIZE}")
    with httpx.Client(timeout=60) as client:
        for i in range(0, len(records), CHUNK_SIZE):
            batch = records[i: i + CHUNK_SIZE]
            chunk_n = i // CHUNK_SIZE + 1
            resp = client.post(ENDPOINT, json=batch, params={
                               "chunk_index": chunk_n}, timeout=60)
            resp.raise_for_status()
            print(f"[produce_ab_experiment]   chunk {chunk_n}: {resp.json()}")

    print(
        f"[produce_ab_experiment] ✓ Done — {len(records):,} experiment records ingested")


if __name__ == "__main__":
    main()
