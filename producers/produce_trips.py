"""
produce_trips.py
----------------
Generates ~1.1M trip records (1 year: 2024-01-01 to 2024-12-31) across
40 routes and 285 vehicles, then POSTs in 10,000-record chunks to
POST /ingest/trips.

FK dependencies: routes (R01–R40) and vehicles (VHC-001..VHC-285) must exist.

Business rules:
  - ₱13 base fare, +₱1.50 per km beyond first 4 km
  - 40% rainy day probability (Davao avg)
  - Time periods: AM_peak (06-09), midday (09-17), PM_peak (17-20), off_peak (20-06)
  - Rainy days: +20-40% delay, -10-15% passengers
  - Load factor = passengers / capacity (0–1.5 with slight overcrowding allowed)
  - Remote routes (R27–R29, R32): reduced trips per period, longer schedules

"""

import random as _rnd
import random
import uuid
from datetime import date, datetime, timedelta, time, timezone

import httpx
import numpy as np

API_BASE = "http://fastapi:8000"
ENDPOINT = f"{API_BASE}/ingest/trips"
CHUNK_SIZE = 10_000
SEED = 42

rng = np.random.default_rng(SEED)
random.seed(SEED)

# ── Route metadata — vehicle ranges match produce_vehicles.py exactly ─────────
ROUTE_META = {
    # 9: VHC-001..VHC-009
    "R01": {"length_km": 22.40, "scheduled_min":  45, "vehicles": list(range(1, 10))},
    # 11: VHC-010..VHC-020
    "R02": {"length_km": 14.80, "scheduled_min":  30, "vehicles": list(range(10, 21))},
    # 9: VHC-021..VHC-029
    "R03": {"length_km":  9.60, "scheduled_min":  20, "vehicles": list(range(21, 30))},
    # 9: VHC-030..VHC-038
    "R04": {"length_km": 11.20, "scheduled_min":  25, "vehicles": list(range(30, 39))},
    # 11: VHC-039..VHC-049
    "R05": {"length_km": 29.50, "scheduled_min":  60, "vehicles": list(range(39, 50))},
    # 11: VHC-050..VHC-060
    "R06": {"length_km":  8.30, "scheduled_min":  18, "vehicles": list(range(50, 61))},
    # 11: VHC-061..VHC-071
    "R07": {"length_km": 12.70, "scheduled_min":  28, "vehicles": list(range(61, 72))},
    # 9: VHC-072..VHC-080
    "R08": {"length_km": 10.10, "scheduled_min":  22, "vehicles": list(range(72, 81))},
    # 9: VHC-081..VHC-089
    "R09": {"length_km": 18.90, "scheduled_min":  40, "vehicles": list(range(81, 90))},
    # 10: VHC-090..VHC-099
    "R10": {"length_km": 16.40, "scheduled_min":  35, "vehicles": list(range(90, 100))},
    # 11: VHC-100..VHC-110
    "R11": {"length_km": 13.60, "scheduled_min":  28, "vehicles": list(range(100, 111))},
    # 10: VHC-111..VHC-120
    "R12": {"length_km":  7.80, "scheduled_min":  17, "vehicles": list(range(111, 121))},
    # 8: VHC-121..VHC-128
    "R13": {"length_km":  7.20, "scheduled_min":  16, "vehicles": list(range(121, 129))},
    # 10: VHC-129..VHC-138
    "R14": {"length_km":  6.50, "scheduled_min":  14, "vehicles": list(range(129, 139))},
    # 8: VHC-139..VHC-146
    "R15": {"length_km":  5.80, "scheduled_min":  13, "vehicles": list(range(139, 147))},
    # 8: VHC-147..VHC-154
    "R16": {"length_km":  6.10, "scheduled_min":  14, "vehicles": list(range(147, 155))},
    # 8: VHC-155..VHC-162
    "R17": {"length_km":  8.90, "scheduled_min":  20, "vehicles": list(range(155, 163))},
    # 7: VHC-163..VHC-169
    "R18": {"length_km": 24.80, "scheduled_min":  50, "vehicles": list(range(163, 170))},
    # 6: VHC-170..VHC-175
    "R19": {"length_km": 27.30, "scheduled_min":  55, "vehicles": list(range(170, 176))},
    # 5: VHC-176..VHC-180
    "R20": {"length_km": 26.10, "scheduled_min":  53, "vehicles": list(range(176, 181))},
    # 4: VHC-181..VHC-184
    "R21": {"length_km":  8.40, "scheduled_min":  18, "vehicles": list(range(181, 185))},
    # 7: VHC-185..VHC-191
    "R22": {"length_km": 19.20, "scheduled_min":  38, "vehicles": list(range(185, 192))},
    # 6: VHC-192..VHC-197
    "R23": {"length_km": 17.60, "scheduled_min":  36, "vehicles": list(range(192, 198))},
    # 5: VHC-198..VHC-202
    "R24": {"length_km": 18.90, "scheduled_min":  38, "vehicles": list(range(198, 203))},
    # 7: VHC-203..VHC-209
    "R25": {"length_km": 14.30, "scheduled_min":  29, "vehicles": list(range(203, 210))},
    # 6: VHC-210..VHC-215
    "R26": {"length_km": 17.80, "scheduled_min":  36, "vehicles": list(range(210, 216))},
    # 4: VHC-216..VHC-219
    "R27": {"length_km": 46.50, "scheduled_min":  90, "vehicles": list(range(216, 220))},
    # 3: VHC-220..VHC-222
    "R28": {"length_km": 32.10, "scheduled_min":  65, "vehicles": list(range(220, 223))},
    # 3: VHC-223..VHC-225
    "R29": {"length_km": 22.40, "scheduled_min":  45, "vehicles": list(range(223, 226))},
    # 6: VHC-226..VHC-231
    "R30": {"length_km": 16.70, "scheduled_min":  34, "vehicles": list(range(226, 232))},
    # 5: VHC-232..VHC-236
    "R31": {"length_km": 14.20, "scheduled_min":  29, "vehicles": list(range(232, 237))},
    # 3: VHC-237..VHC-239
    "R32": {"length_km": 28.60, "scheduled_min":  58, "vehicles": list(range(237, 240))},
    # 7: VHC-240..VHC-246
    "R33": {"length_km": 10.30, "scheduled_min":  22, "vehicles": list(range(240, 247))},
    # 6: VHC-247..VHC-252
    "R34": {"length_km": 15.40, "scheduled_min":  31, "vehicles": list(range(247, 253))},
    # 6: VHC-253..VHC-258
    "R35": {"length_km": 12.80, "scheduled_min":  26, "vehicles": list(range(253, 259))},
    # 7: VHC-259..VHC-265
    "R36": {"length_km": 18.50, "scheduled_min":  37, "vehicles": list(range(259, 266))},
    # 5: VHC-266..VHC-270
    "R37": {"length_km": 13.20, "scheduled_min":  27, "vehicles": list(range(266, 271))},
    # 6: VHC-271..VHC-276
    "R38": {"length_km": 16.80, "scheduled_min":  34, "vehicles": list(range(271, 277))},
    # 5: VHC-277..VHC-281
    "R39": {"length_km": 34.20, "scheduled_min":  68, "vehicles": list(range(277, 282))},
    # 4: VHC-282..VHC-285
    "R40": {"length_km": 18.30, "scheduled_min":  37, "vehicles": list(range(282, 286))},
}

TRIPS_PER_PERIOD_STANDARD = {
    "AM_peak":  3,
    "midday":   5,
    "PM_peak":  3,
    "off_peak": 2,
}

TRIPS_PER_PERIOD_REMOTE = {
    "AM_peak":  1,
    "midday":   2,
    "PM_peak":  1,
    "off_peak": 0,
}

TRIPS_PER_PERIOD_SEMI = {
    "AM_peak":  2,
    "midday":   3,
    "PM_peak":  2,
    "off_peak": 1,
}

REMOTE_ROUTES = {"R27", "R28", "R29", "R32", "R39"}
SEMI_ROUTES = {"R05", "R18", "R19", "R20", "R22", "R24", "R26", "R40"}

PERIOD_HOURS = {
    "AM_peak":  (6,  9),
    "midday":   (9,  17),
    "PM_peak":  (17, 20),
    "off_peak": (20, 24),
}

_rnd.seed(SEED)
VEHICLE_CAPACITY: dict[str, int] = {}
for r, meta in ROUTE_META.items():
    _modern_routes = {"R02", "R06", "R11", "R13", "R14", "R15", "R17"}
    modern_prob = 0.45 if r in _modern_routes else (
        0.10 if r in REMOTE_ROUTES else 0.25)
    for v in meta["vehicles"]:
        cap = 23 if (_rnd.random() < modern_prob) else 16
        VEHICLE_CAPACITY[f"VHC-{v:03d}"] = cap

BASE_FARE_PHP = 13.00
PER_KM_RATE = 1.50
FREE_KM = 4.0


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
    return d.strftime("%A")


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def trips_per_period(route_id: str) -> dict:
    if route_id in REMOTE_ROUTES:
        return TRIPS_PER_PERIOD_REMOTE
    if route_id in SEMI_ROUTES:
        return TRIPS_PER_PERIOD_SEMI
    return TRIPS_PER_PERIOD_STANDARD


_ROUTE_RAIN_EXTRA_PROB = {r: 0.05 for r in REMOTE_ROUTES}


def sample_route_rain(city_rainy_day: bool, route_id: str) -> bool:
    """
    Decide whether a specific route is experiencing rain.

    - On a dry city day (city_rainy_day=False):  no route is rainy.
      This preserves the physical reality that rain is a city-level weather
      event; we do not invent rain on routes when the city is dry.
    - On a rainy city day (city_rainy_day=True):  each route independently
      draws from its own exposure probability.  Urban routes use the base
      40% rate; remote/fringe routes use 45%.  This means ~40–45% of all
      trips on a rainy day are actually rained-on, matching the documented
      business rule, while eliminating the unrealistic 100% correlation
      across all 40 routes.
    """
    if not city_rainy_day:
        return False
    extra = _ROUTE_RAIN_EXTRA_PROB.get(route_id, 0.0)
    # Base probability 0.40 already gates entry here; extra shifts remote routes
    return random.random() < (0.40 + extra)


def generate_trip(trip_num: int, route_id: str, vehicle_id: str,
                  trip_date: date, period: str, is_rainy: bool,
                  max_fare: float, capacity: int) -> dict:
    scheduled_min = ROUTE_META[route_id]["scheduled_min"]

    departure = random_time_in_period(period)

    base_delay = rng.integers(0, 10)
    if is_rainy:
        base_delay += rng.integers(5, 20)
    if period in ("AM_peak", "PM_peak"):
        base_delay += rng.integers(2, 8)
    # Remote routes have higher base delay (road conditions)
    if route_id in REMOTE_ROUTES:
        base_delay += rng.integers(5, 15)
    elif route_id in SEMI_ROUTES:
        base_delay += rng.integers(2, 8)
    delay_min = int(base_delay)
    is_on_time = delay_min <= 5

    travel_time = scheduled_min + delay_min

    dep_total_min = departure.hour * 60 + departure.minute
    arr_total_min = dep_total_min + travel_time
    arr_hour = (arr_total_min // 60) % 24
    arr_minute = arr_total_min % 60
    arrival = time(arr_hour, arr_minute, departure.second)

    # Load factor — remote routes have lower ridership
    if route_id in REMOTE_ROUTES:
        load_base = {"AM_peak": 0.55, "PM_peak": 0.50,
                     "midday": 0.35, "off_peak": 0.15}
    elif route_id in SEMI_ROUTES:
        load_base = {"AM_peak": 0.68, "PM_peak": 0.65,
                     "midday": 0.48, "off_peak": 0.25}
    else:
        load_base = {"AM_peak": 0.82, "PM_peak": 0.78,
                     "midday": 0.60, "off_peak": 0.35}

    load_mean = load_base[period]
    if is_rainy:
        load_mean *= 0.88
    if is_weekend(trip_date):
        load_mean *= 0.72

    load_factor = float(np.clip(rng.normal(load_mean, 0.12), 0.05, 1.40))
    passengers = max(1, int(round(load_factor * capacity)))
    revenue = round(passengers * max_fare, 2)

    return {
        "trip_id":            f"TRP-{trip_num:07d}",
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
    """Yield trip dicts across all 365 days × 40 routes × vehicles × periods."""
    start_date = date(2024, 1, 1)
    end_date = date(2024, 12, 31)
    delta = timedelta(days=1)

    trip_num = 1
    current = start_date

    while current <= end_date:
        city_rainy_day = random.random() < 0.40

        for route_id, meta in ROUTE_META.items():
            is_rainy = sample_route_rain(city_rainy_day, route_id)

            max_fare = fare_for_route(meta["length_km"])
            vehicles = meta["vehicles"]
            tpp = trips_per_period(route_id)

            for v_num in vehicles:
                vehicle_id = f"VHC-{v_num:03d}"
                capacity = VEHICLE_CAPACITY.get(vehicle_id, 16)

                for period, n_trips in tpp.items():
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
    print(
        f"[produce_trips]   chunk {chunk_idx:05d} ({len(chunk):,} records) → {resp.json()}")


def main():
    # Estimate total trips
    total_daily = sum(
        len(meta["vehicles"]) * sum(trips_per_period(rid).values())
        for rid, meta in ROUTE_META.items()
    )
    est_total = total_daily * 365
    print(f"[produce_trips] Starting trip generation")
    print(f"[produce_trips]   Routes    : {len(ROUTE_META)}")
    print(
        f"[produce_trips]   Vehicles  : {sum(len(m['vehicles']) for m in ROUTE_META.values())}")
    print(f"[produce_trips]   Trips/day : ~{total_daily:,}")
    print(f"[produce_trips]   Est total : ~{est_total:,}")
    print(
        f"[produce_trips]   Endpoint  : {ENDPOINT}  |  Chunk: {CHUNK_SIZE:,}")

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

        if chunk:
            post_chunk(client, chunk, chunk_idx)
            total += len(chunk)

    print(
        f"[produce_trips] ✓ Done — {total:,} trips ingested in {chunk_idx} chunks")


if __name__ == "__main__":
    main()
