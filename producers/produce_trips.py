"""
produce_trips.py
----------------
Generates ~500,000 trip records (1 year: 2024-01-01 to 2024-12-31) across
12 routes and 120 vehicles, then POSTs in 10,000-record chunks to
POST /ingest/trips.

FK dependencies: routes (R01–R12) and vehicles (VHC-001..VHC-120) must exist.

Business rules:
  - ₱13 base fare, +₱1.50 per km beyond first 4 km
  - 40% rainy day probability (Davao avg)
  - Time periods: AM_peak (06-09), midday (09-17), PM_peak (17-20), off_peak (20-06)
  - Rainy days: +20-40% delay, -10-15% passengers
  - Load factor = passengers / capacity (0–1.5 with slight overcrowding allowed)
  - ~114 trips/day average across all routes
"""

import random
import uuid
from datetime import date, datetime, timedelta, time, timezone
from itertools import product as iproduct

import httpx
import numpy as np

API_BASE = "http://fastapi:8000"
ENDPOINT = f"{API_BASE}/ingest/trips"
CHUNK_SIZE = 10_000
SEED = 42

rng = np.random.default_rng(SEED)
random.seed(SEED)

# ── Route metadata ────────────────────────────────────────────────────────────
# Vehicle ranges mirror produce_vehicles.py allocation exactly:
#   route_alloc = {r: 10 for r in ROUTE_IDS}
#   +1 for R02, R05, R06, R07, R11  → 11 each
#   -1 for R01, R03, R04, R08, R09  →  9 each
#   R10, R12 stay at 10
#   Sequential vid starting at 1 → VHC-001..VHC-120, no gaps, no overlaps.
ROUTE_META = {
    "R01": {"length_km": 22.40, "scheduled_min": 45, "vehicles": list(range(1,   10))},  #  9: VHC-001..009
    "R02": {"length_km": 14.80, "scheduled_min": 30, "vehicles": list(range(10,  21))},  # 11: VHC-010..020
    "R03": {"length_km":  9.60, "scheduled_min": 20, "vehicles": list(range(21,  30))},  #  9: VHC-021..029
    "R04": {"length_km": 11.20, "scheduled_min": 25, "vehicles": list(range(30,  39))},  #  9: VHC-030..038
    "R05": {"length_km": 29.50, "scheduled_min": 60, "vehicles": list(range(39,  50))},  # 11: VHC-039..049
    "R06": {"length_km":  8.30, "scheduled_min": 18, "vehicles": list(range(50,  61))},  # 11: VHC-050..060
    "R07": {"length_km": 12.70, "scheduled_min": 28, "vehicles": list(range(61,  72))},  # 11: VHC-061..071
    "R08": {"length_km": 10.10, "scheduled_min": 22, "vehicles": list(range(72,  81))},  #  9: VHC-072..080
    "R09": {"length_km": 18.90, "scheduled_min": 40, "vehicles": list(range(81,  90))},  #  9: VHC-081..089
    "R10": {"length_km": 16.40, "scheduled_min": 35, "vehicles": list(range(90, 100))},  # 10: VHC-090..099
    "R11": {"length_km": 13.60, "scheduled_min": 28, "vehicles": list(range(100, 111))}, # 11: VHC-100..110
    "R12": {"length_km":  7.80, "scheduled_min": 17, "vehicles": list(range(111, 121))}, # 10: VHC-111..120
}

VEHICLE_CAPACITY = {}  # VHC-NNN → capacity
for r, meta in ROUTE_META.items():
    for v in meta["vehicles"]:
        # Same modern_prob logic as produce_vehicles.py
        modern = r in ("R02", "R11", "R06")
        cap = 23 if (random.random() < (0.45 if modern else 0.25)) else 16
        VEHICLE_CAPACITY[f"VHC-{v:03d}"] = cap

# Trips per vehicle per day by time period (approximate headway-based)
TRIPS_PER_PERIOD = {
    "AM_peak":  3,
    "midday":   5,
    "PM_peak":  3,
    "off_peak": 2,
}

PERIOD_HOURS = {
    "AM_peak":  (6,  9),
    "midday":   (9,  17),
    "PM_peak":  (17, 20),
    "off_peak": (20, 24),   # wrap; also covers 0-6 but we simplify to late night
}

BASE_FARE_PHP = 13.00
PER_KM_RATE   = 1.50
FREE_KM       = 4.0


def fare_for_route(length_km: float) -> float:
    extra = max(0.0, length_km - FREE_KM)
    return round(BASE_FARE_PHP + extra * PER_KM_RATE, 2)


def random_time_in_period(period: str) -> time:
    lo, hi = PERIOD_HOURS[period]
    hour = random.randint(lo, hi - 1)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return time(hour % 24, minute, second)


def day_of_week(d: date) -> str:
    return d.strftime("%A")   # Monday … Sunday


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def generate_trip(trip_num: int, route_id: str, vehicle_id: str,
                  trip_date: date, period: str, is_rainy: bool,
                  max_fare: float, capacity: int) -> dict:
    """Produce one trip record dict."""
    scheduled_min = ROUTE_META[route_id]["scheduled_min"]

    # Departure time random within period
    departure = random_time_in_period(period)

    # Delay logic: rainy adds more delay; peak adds some
    base_delay = rng.integers(0, 10)
    if is_rainy:
        base_delay += rng.integers(5, 20)
    if period in ("AM_peak", "PM_peak"):
        base_delay += rng.integers(2, 8)
    delay_min = int(base_delay)
    is_on_time = delay_min <= 5

    travel_time = scheduled_min + delay_min
    # Arrival time (simple addition, not wrapping past midnight for brevity)
    dep_total_min = departure.hour * 60 + departure.minute
    arr_total_min = dep_total_min + travel_time
    arr_hour = (arr_total_min // 60) % 24
    arr_minute = arr_total_min % 60
    arrival = time(arr_hour, arr_minute, departure.second)

    # Passenger load: peak higher, rainy slightly lower, weekends lower
    if period == "AM_peak":
        load_mean = 0.82
    elif period == "PM_peak":
        load_mean = 0.78
    elif period == "midday":
        load_mean = 0.60
    else:
        load_mean = 0.35

    if is_rainy:
        load_mean *= 0.88
    if is_weekend(trip_date):
        load_mean *= 0.72

    load_factor = float(np.clip(rng.normal(load_mean, 0.12), 0.05, 1.40))
    passengers = max(1, int(round(load_factor * capacity)))
    revenue = round(passengers * max_fare, 2)

    return {
        "trip_id":            f"TRP-{trip_num:06d}",
        "route_id":           route_id,
        "vehicle_id":         vehicle_id,
        "trip_date":          trip_date.isoformat(),
        "departure_time":     departure.isoformat(),
        "arrival_time":       arrival.isoformat(),
        "time_period":        period,
        "day_of_week":        day_of_week(trip_date),
        "passengers_boarded": passengers,
        "revenue_php":        revenue,
        "travel_time_min":    travel_time,
        "scheduled_time_min": scheduled_min,
        "delay_min":          delay_min,
        "is_on_time":         is_on_time,
        "is_rainy_day":       is_rainy,
        "load_factor":        round(load_factor, 4),
        "created_at":         datetime.now(timezone.utc).isoformat(),
    }


def trip_generator():
    """Yield trip dicts one by one across all 365 days × routes × vehicles × periods."""
    start_date = date(2024, 1, 1)
    end_date   = date(2024, 12, 31)
    delta = timedelta(days=1)

    trip_num = 1
    current = start_date

    while current <= end_date:
        is_rainy = random.random() < 0.40   # 40% rainy day probability

        for route_id, meta in ROUTE_META.items():
            max_fare = fare_for_route(meta["length_km"])
            vehicles = meta["vehicles"]

            for v_num in vehicles:
                vehicle_id = f"VHC-{v_num:03d}"
                capacity   = VEHICLE_CAPACITY.get(vehicle_id, 16)

                for period, n_trips in TRIPS_PER_PERIOD.items():
                    for _ in range(n_trips):
                        yield generate_trip(
                            trip_num, route_id, vehicle_id,
                            current, period, is_rainy, max_fare, capacity,
                        )
                        trip_num += 1

        current += delta


def post_chunk(client: httpx.Client, chunk: list[dict], chunk_idx: int):
    resp = client.post(ENDPOINT, json=chunk, timeout=120)
    resp.raise_for_status()
    print(f"[produce_trips]   chunk {chunk_idx:04d} ({len(chunk):,} records) → {resp.json()}")


def main():
    print(f"[produce_trips] Starting trip generation — target ~500K records")
    print(f"[produce_trips] Endpoint: {ENDPOINT}  |  Chunk size: {CHUNK_SIZE:,}")

    chunk: list[dict] = []
    chunk_idx = 1
    total = 0

    with httpx.Client(timeout=120) as client:
        for trip in trip_generator():
            chunk.append(trip)
            if len(chunk) >= CHUNK_SIZE:
                post_chunk(client, chunk, chunk_idx)
                total += len(chunk)
                chunk = []
                chunk_idx += 1

        # Flush remainder
        if chunk:
            post_chunk(client, chunk, chunk_idx)
            total += len(chunk)

    print(f"[produce_trips] ✓ Done — {total:,} trips ingested in {chunk_idx} chunks")


if __name__ == "__main__":
    main()
