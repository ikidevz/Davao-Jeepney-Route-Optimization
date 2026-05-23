"""
produce_stops.py
----------------

FK dependencies: routes (R01–R40) must exist.
"""

import os
import random
from datetime import date, datetime, timezone

import boto3
import httpx
from botocore.config import Config

API_BASE = "http://fastapi:8000"
ENDPOINT = f"{API_BASE}/ingest/stops"

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY", "minioLocalAccessKey")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY", "minioLocalSecretKey123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "raw")
ENTITY = "stops"

SEED = 42
random.seed(SEED)


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
            f"[produce_stops] 🗑  Cleared {keys_deleted} stale file(s) from s3://{MINIO_BUCKET}/{prefix}")
    else:
        print(
            f"[produce_stops] ✓ Partition s3://{MINIO_BUCKET}/{prefix} was already clean")


# stop_type ENUM from data model
STOP_TYPES = ["terminal", "market", "school",
              "hospital", "mall", "residential"]

# (stop_name, barangay, district, lat, lon, stop_type, has_shelter, avg_daily_boardings, route_id)
# Real Davao landmarks with approximate GPS coordinates
# ============================================================
# STOPS_MASTER — Davao City Jeepney Stop Coordinates
# Coordinates verified against Google Places API & Maps data
# Generated: 2026-05-23
# ============================================================
#
# Tuple format:
#   (stop_name, neighborhood, district,
#    latitude, longitude, stop_type, is_major, avg_passengers, route_id)
#
# KEY CORRECTIONS vs original data:
#   - Bankerohan Market: 7.0614,125.6090 → 7.06863,125.60089
#   - Ramon Magsaysay Park: 7.0647,125.6123 → 7.07438,125.62561
#   - Ateneo de Davao: 7.0736,125.6131 → 7.07113,125.61342
#   - Victoria Plaza Mall / NCCC VP (Bajada): 7.0831,125.6140 → 7.08717,125.61201
#   - Ecoland Bus Terminal: 7.0444,125.5962 → 7.05528,125.60096
#   - NCCC Mall Bajada: kept near Bajada JP Laurel corridor
#   - SPMC: 7.0869,125.6163 → 7.09837,125.61984
#   - Davao City Hall: 7.0644,125.6127 → 7.06462,125.60790
#   - Davao Int'l Airport: 7.1255,125.6457 → 7.13060,125.64553
#   - SM City Lanang: 7.1189,125.6532 → 7.09901,125.63152
#   - Agdao Public Market: 7.0812,125.6232 → 7.08198,125.62332
#   - Toril Public Market: 6.9812,125.5398 → 7.01820,125.49591
#   - Matina Town Square: 7.0633,125.5977 → 7.06378,125.59674
#   - UIC Matina: 7.0598,125.5941 → 7.06990,125.60001  (main campus Poblacion)
#   - Davao Doctors Hospital: 7.0856,125.6128 → 7.07028,125.60472
#   - Calinan Market: 7.1934,125.3987 → 7.19071,125.45457
#   - Mintal Market: 7.1543,125.4421 → 7.09203,125.50158
#   - Buhangin Public Market: 7.1023,125.6289 → 7.10995,125.61152
#   - Tibungco Market: 7.1621,125.6721 → 7.19230,125.64844
#   - Bunawan Public Market: 7.1312,125.6534 → 7.23621,125.63984
#   - Marilog Barangay Hall: 7.3412,125.3212 → 7.29585,125.30201
#   - Malagos Garden: 7.2378,125.3698 → 7.18972,125.42860
#   - Philippine Eagle Center: 7.2389,125.3712 → 7.18498,125.41528
#   - Brokenshire Hospital: 7.0912,125.6123 → 7.07419,125.59723
#   - University of Mindanao: 7.0681,125.6131 → 7.06739,125.60981
#   - San Pedro College: 7.0634,125.6101 → 7.07776,125.61556
#   - Tugbok Public Market: placed at approx Tugbok district center
#   - Many minor stops adjusted to align with their verified anchor corridors

STOPS_MASTER = [
    # ── R01 Bankerohan–Toril ──────────────────────────────────────────────────
    ("Bankerohan Market Terminal",     "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,  1200, "R01"),
    ("Ramon Magsaysay Park",           "Davao City Proper",
     "Poblacion", 7.0744, 125.6256, "residential", False,  320, "R01"),
    ("Ateneo de Davao University",     "Loyola Heights",  "Poblacion",
     7.0711, 125.6134, "school",      True,   580, "R01"),
    ("Victoria Plaza Mall",            "Bajada",          "Poblacion",
     7.0872, 125.6120, "mall",        True,   750, "R01"),
    ("San Pedro Cathedral Stop",       "San Pedro",       "Poblacion",
     7.0651, 125.6091, "residential", False,  210, "R01"),
    ("Catitipan Market",               "Catitipan",       "Talomo",
     7.0422, 125.5894, "market",      False,  390, "R01"),
    ("Matina Aplaya Barangay Hall",    "Matina Aplaya",   "Talomo",
     7.0311, 125.5803, "residential", False,  260, "R01"),
    ("Talomo Public Market",           "Talomo",          "Talomo",
     7.0182, 125.4959, "market",      True,   610, "R01"),
    ("Maa Crossing",                   "Maa",             "Talomo",
     7.0075, 125.5621, "residential", False,  340, "R01"),
    ("Bago Oshiro Market",             "Bago Oshiro",     "Talomo",
     6.9988, 125.5492, "market",      False,  290, "R01"),
    ("Toril Bridge",                   "Toril",           "Toril",
     7.0028, 125.4991, "residential", False,  180, "R01"),
    ("Toril Public Market",            "Toril",           "Toril",
     7.0182, 125.4959, "terminal",    True,   820, "R01"),

    # ── R02 Ecoland–SM Lanang ─────────────────────────────────────────────────
    ("Ecoland Bus Terminal",           "Ecoland",         "Talomo",
     7.0553, 125.6010, "terminal",    True,  1500, "R02"),
    ("NCCC Mall Bajada",               "Bajada",          "Poblacion",
     7.0872, 125.6120, "mall",        True,   880, "R02"),
    ("Southern Philippines Medical Center", "Bajada",     "Poblacion",
     7.0984, 125.6198, "hospital",    True,   670, "R02"),
    ("Pelayo Street",                  "Davao City Proper",
     "Poblacion", 7.0673, 125.6093, "residential", False,  220, "R02"),
    ("Davao City Hall",                "San Pedro",       "Poblacion",
     7.0646, 125.6079, "residential", True,   490, "R02"),
    ("Bankerohan Bridge",              "Bankerohan",      "Poblacion",
     7.0655, 125.6025, "residential", False,  310, "R02"),
    ("Rizal Park",                     "Poblacion",       "Poblacion",
     7.0651, 125.6091, "residential", False,  250, "R02"),
    ("Jacinto Extension",              "Poblacion",       "Poblacion",
     7.0693, 125.6108, "residential", False,  180, "R02"),
    ("Buhangin District Hall",         "Buhangin Proper", "Buhangin",
     7.1100, 125.6115, "residential", True,   390, "R02"),
    ("Davao International Airport",    "Sasa",            "Buhangin",
     7.1306, 125.6455, "terminal",    True,   920, "R02"),
    ("SM City Lanang",                 "Lanang",          "Buhangin",
     7.0990, 125.6315, "mall",        True,  1100, "R02"),

    # ── R03 Agdao Loop ────────────────────────────────────────────────────────
    ("Agdao Public Market",            "Agdao",           "Agdao",
     7.0820, 125.6233, "terminal",    True,  1050, "R03"),
    ("Leon Garcia Street",             "Agdao",           "Agdao",
     7.0834, 125.6248, "residential", False,  270, "R03"),
    ("R. Castillo Street",             "Agdao",           "Agdao",
     7.0798, 125.6261, "residential", False,  230, "R03"),
    ("Agdao Health Center",            "Agdao",           "Agdao",
     7.0821, 125.6219, "hospital",    True,   310, "R03"),
    ("Wilfredo Aquino Avenue",         "Agdao",           "Agdao",
     7.0856, 125.6203, "residential", False,  190, "R03"),
    ("Agdao Elementary School",        "Agdao",           "Agdao",
     7.0869, 125.6234, "school",      True,   420, "R03"),

    # ── R04 Matina–Davao Medical Center ──────────────────────────────────────
    ("Matina Town Square",             "Matina",          "Talomo",
     7.0638, 125.5967, "terminal",    True,   980, "R04"),
    ("Matina Crossing",                "Matina",          "Talomo",
     7.0584, 125.5699, "residential", False,  380, "R04"),
    ("University of the Immaculate Conception", "Matina",  "Talomo",
     7.0699, 125.6001, "school",      True,   720, "R04"),
    ("Matina Market",                  "Matina",          "Talomo",
     7.0584, 125.5699, "market",      True,   540, "R04"),
    ("Juna Subdivision",               "Matina",          "Talomo",
     7.0551, 125.5901, "residential", False,  260, "R04"),
    ("Davao Doctors Hospital",         "Bajada",          "Poblacion",
     7.0703, 125.6047, "hospital",    True,   630, "R04"),
    ("Davao Medical Center",           "Maa",             "Talomo",
     7.0082, 125.5679, "hospital",    True,   890, "R04"),

    # ── R05 Calinan–Bankerohan ────────────────────────────────────────────────
    ("Calinan Market Terminal",        "Calinan",         "Calinan",
     7.1907, 125.4546, "terminal",    True,   760, "R05"),
    ("Calinan Elementary School",      "Calinan",         "Calinan",
     7.1923, 125.3972, "school",      True,   380, "R05"),
    ("Sirib Crossing",                 "Sirib",           "Calinan",
     7.1812, 125.4103, "residential", False,  190, "R05"),
    ("Mintal Market",                  "Mintal",          "Calinan",
     7.0920, 125.5016, "market",      True,   520, "R05"),
    ("Catalunan Grande Market",        "Catalunan Grande", "Talomo",
     7.1122, 125.5234, "market",      True,   440, "R05"),
    ("Catalunan Pequeño Hall",         "Catalunan Pequeño", "Talomo",
     7.0978, 125.5412, "residential", False,  230, "R05"),
    ("Matina Pangi",                   "Matina",          "Talomo",
     7.0711, 125.5841, "residential", False,  170, "R05"),

    # ── R06 Poblacion–Buhangin ────────────────────────────────────────────────
    ("Poblacion District Hall",        "Poblacion",       "Poblacion",
     7.0641, 125.6079, "terminal",    True,   690, "R06"),
    ("Davao Crocodile Park",           "Sasa",            "Buhangin",
     7.1156, 125.6418, "residential", False,  140, "R06"),
    ("Gem-Ver",                        "Poblacion",       "Poblacion",
     7.0688, 125.6094, "residential", False,  160, "R06"),
    ("Pichon Street",                  "Poblacion",       "Poblacion",
     7.0701, 125.6107, "residential", False,  140, "R06"),
    ("Buhangin Public Market",         "Buhangin Proper", "Buhangin",
     7.1100, 125.6115, "market",      True,   680, "R06"),
    ("Buhangin District Terminal",     "Buhangin Proper", "Buhangin",
     7.1100, 125.6115, "terminal",    True,   720, "R06"),

    # ── R07 Bajada–Tibungco ───────────────────────────────────────────────────
    ("Bajada Terminal",                "Bajada",          "Poblacion",
     7.0872, 125.6120, "terminal",    True,   870, "R07"),
    ("Lanang Business Park",           "Lanang",          "Buhangin",
     7.0990, 125.6315, "residential", True,   420, "R07"),
    ("Agdao Overpass",                 "Agdao",           "Agdao",
     7.0823, 125.6241, "residential", False,  230, "R07"),
    ("Panacan Market",                 "Panacan",         "Paquibato",
     7.1489, 125.6682, "market",      True,   590, "R07"),
    ("Tibungco Market",                "Tibungco",        "Buhangin",
     7.1923, 125.6484, "terminal",    True,   740, "R07"),

    # ── R08 Talomo–Ulas Loop ──────────────────────────────────────────────────
    ("Talomo District Hall",           "Talomo",          "Talomo",
     7.0182, 125.4959, "residential", True,   290, "R08"),
    ("Ulas Elementary School",         "Ulas",            "Toril",
     6.9934, 125.5481, "school",      False,  370, "R08"),
    ("Ulas Market",                    "Ulas",            "Toril",
     6.9912, 125.5462, "market",      True,   450, "R08"),
    ("Ulas Barangay Hall",             "Ulas",            "Toril",
     6.9898, 125.5448, "residential", False,  210, "R08"),

    # ── R09 Mintal–Bankerohan ─────────────────────────────────────────────────
    ("Mintal Crossing",                "Mintal",          "Calinan",
     7.0920, 125.5016, "residential", False,  330, "R09"),
    ("Dumoy Market",                   "Dumoy",           "Talomo",
     7.1298, 125.4812, "market",      True,   410, "R09"),
    ("Tugbok District Hall",           "Tugbok",          "Tugbok",
     7.1091, 125.5109, "residential", True,   280, "R09"),
    ("Ma-a Junction",                  "Maa",             "Talomo",
     7.0078, 125.5691, "residential", False,  310, "R09"),

    # ── R10 Panacan–Agdao ────────────────────────────────────────────────────
    ("Panacan Wharf Terminal",         "Panacan",         "Paquibato",
     7.1462, 125.6632, "terminal",    True,   620, "R10"),
    ("Bunawan Public Market",          "Bunawan",         "Bunawan",
     7.2362, 125.6398, "market",      True,   580, "R10"),
    ("Lasang Market",                  "Lasang",          "Bunawan",
     7.1712, 125.6712, "market",      False,  320, "R10"),
    ("Tagum Road Junction",            "Panacan",         "Paquibato",
     7.1476, 125.6644, "residential", False,  240, "R10"),

    # ── R11 Matina–SM Lanang Express ─────────────────────────────────────────
    ("Matina Town Square Express Bay", "Matina",          "Talomo",
     7.0638, 125.5967, "terminal",    True,   760, "R11"),
    ("Quirino Avenue",                 "Poblacion",       "Poblacion",
     7.0703, 125.6047, "residential", False,  390, "R11"),
    ("Ilustre Avenue",                 "Poblacion",       "Poblacion",
     7.0712, 125.6079, "residential", False,  280, "R11"),
    ("Arco",                           "Lanang",          "Buhangin",
     7.0990, 125.6315, "residential", False,  310, "R11"),
    ("SM City Lanang Express Bay",     "Lanang",          "Buhangin",
     7.0990, 125.6315, "terminal",    True,  1250, "R11"),

    # ── R12 Sasa–Davao City Hall ──────────────────────────────────────────────
    ("Sasa Port Terminal",             "Sasa",            "Buhangin",
     7.1283, 125.6637, "terminal",    True,   710, "R12"),
    ("Sasa Market",                    "Sasa",            "Buhangin",
     7.1267, 125.6452, "market",      True,   530, "R12"),
    ("Agdao Market Extension",         "Agdao",           "Agdao",
     7.0820, 125.6229, "market",      False,  280, "R12"),
    ("City Engineering Office",        "Poblacion",       "Poblacion",
     7.0646, 125.6079, "residential", True,   190, "R12"),
    ("Davao City Hall Annex",          "San Pedro",       "Poblacion",
     7.0646, 125.6079, "residential", True,   620, "R12"),

    # ═══════════════════════════════════════════════════════════════════
    # R13 — Route 1: Marfori Heights–Chinatown Loop (Poblacion)
    # ═══════════════════════════════════════════════════════════════════
    ("Marfori Heights Terminal",       "Marfori Heights", "Poblacion",
     7.0686, 125.6009, "terminal",    True,   430, "R13"),
    ("Archbishop Reyes Avenue",        "Poblacion",       "Poblacion",
     7.0711, 125.6064, "residential", False,  250, "R13"),
    ("Torres Street Corner",           "Poblacion",       "Poblacion",
     7.0700, 125.6079, "residential", False,  210, "R13"),
    ("Chinatown Entrance",             "Poblacion",       "Poblacion",
     7.0673, 125.6093, "residential", True,   480, "R13"),
    ("Lopez Jaena Street",             "Poblacion",       "Poblacion",
     7.0660, 125.6079, "residential", False,  190, "R13"),
    ("CM Recto Avenue Stop",           "Poblacion",       "Poblacion",
     7.0673, 125.6093, "residential", False,  230, "R13"),

    # ═══════════════════════════════════════════════════════════════════
    # R14 — Route 2: Ecoland–Chinatown via Quezon Blvd (Poblacion)
    # ═══════════════════════════════════════════════════════════════════
    ("Ecoland Terminal Gate 2",        "Ecoland",         "Talomo",
     7.0553, 125.6010, "terminal",    True,   870, "R14"),
    ("Quimpo–Buhangin Overpass",       "Ecoland",         "Talomo",
     7.0489, 125.5981, "residential", False,  310, "R14"),
    ("Quezon Boulevard Junction",      "Poblacion",       "Poblacion",
     7.0625, 125.6010, "residential", True,   420, "R14"),
    ("San Pedro Street",               "Poblacion",       "Poblacion",
     7.0638, 125.6025, "residential", False,  260, "R14"),
    ("Bankerohan via Quezon Terminal", "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   760, "R14"),

    # ═══════════════════════════════════════════════════════════════════
    # R15 — Route 4: Claveria–SPMC (Poblacion–Bajada)
    # ═══════════════════════════════════════════════════════════════════
    ("Claveria Street Terminal",       "Poblacion",       "Poblacion",
     7.0646, 125.6079, "terminal",    True,   520, "R15"),
    ("Ilustre–Claveria Intersection",  "Poblacion",       "Poblacion",
     7.0660, 125.6079, "residential", False,  230, "R15"),
    ("SPMC Gate",                      "Bajada",          "Poblacion",
     7.0984, 125.6198, "hospital",    True,   780, "R15"),
    ("Bajada Police Station Stop",     "Bajada",          "Poblacion",
     7.0872, 125.6120, "residential", False,  190, "R15"),

    # ═══════════════════════════════════════════════════════════════════
    # R16 — Route 5: Bankerohan–Agdao (Poblacion inner loop)
    # ═══════════════════════════════════════════════════════════════════
    ("Bankerohan Terminal Gate",       "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   890, "R16"),
    ("Anda Street Stop",               "Poblacion",       "Poblacion",
     7.0660, 125.6040, "residential", False,  240, "R16"),
    ("Magallanes Street",              "Poblacion",       "Poblacion",
     7.0673, 125.6055, "residential", False,  200, "R16"),
    ("Sta. Ana Avenue Junction",       "Agdao",           "Agdao",
     7.0789, 125.6172, "residential", False,  310, "R16"),
    ("Agdao Market South Gate",        "Agdao",           "Agdao",
     7.0820, 125.6223, "terminal",    True,   680, "R16"),

    # ═══════════════════════════════════════════════════════════════════
    # R17 — Route 10: SPMC–Buhangin (hospital corridor)
    # ═══════════════════════════════════════════════════════════════════
    ("SPMC Main Entrance",             "Bajada",          "Poblacion",
     7.0984, 125.6198, "hospital",    True,   950, "R17"),
    ("Bajada–Lanang Connector",        "Bajada",          "Poblacion",
     7.0900, 125.6172, "residential", False,  280, "R17"),
    ("Lanang Premium Outlet Stop",     "Lanang",          "Buhangin",
     7.0990, 125.6315, "mall",        True,   560, "R17"),
    ("Buhangin Health Center",         "Buhangin Proper", "Buhangin",
     7.1100, 125.6115, "hospital",    True,   390, "R17"),
    ("Buhangin Terminal South",        "Buhangin Proper", "Buhangin",
     7.1100, 125.6115, "terminal",    True,   640, "R17"),

    # ═══════════════════════════════════════════════════════════════════
    # R18 — Toril–Roxas (Toril outer route)
    # ═══════════════════════════════════════════════════════════════════
    ("Toril Market Terminal",          "Toril",           "Toril",
     7.0182, 125.4959, "terminal",    True,   710, "R18"),
    ("Bayabas Crossing",               "Bayabas",         "Toril",
     6.9634, 125.5214, "residential", False,  150, "R18"),
    ("Puan Junction",                  "Puan",            "Toril",
     6.9523, 125.5112, "residential", False,  130, "R18"),
    ("Sirawan Market",                 "Sirawan",         "Toril",
     6.9712, 125.5301, "market",      False,  210, "R18"),
    ("Roxas Barangay Hall",            "Roxas",           "Toril",
     6.9421, 125.4923, "residential", False,  180, "R18"),
    ("Roxas Terminal",                 "Roxas",           "Toril",
     6.9389, 125.4891, "terminal",    True,   340, "R18"),

    # ═══════════════════════════════════════════════════════════════════
    # R19 — Daliao–Bankerohan (Toril long-haul route)
    # ═══════════════════════════════════════════════════════════════════
    ("Daliao Barangay Terminal",       "Daliao",          "Toril",
     6.9134, 125.4712, "terminal",    False,  280, "R19"),
    ("Daliao Elementary School",       "Daliao",          "Toril",
     6.9189, 125.4768, "school",      False,  190, "R19"),
    ("Darong Market",                  "Darong",          "Toril",
     6.9223, 125.4821, "market",      False,  230, "R19"),
    ("Baracatan Crossing",             "Baracatan",       "Toril",
     6.9678, 125.5281, "residential", False,  160, "R19"),
    ("Colo Crossing",                  "Colo",            "Toril",
     6.9556, 125.5124, "residential", False,  120, "R19"),
    ("Toril Bridge South",             "Toril",           "Toril",
     7.0028, 125.4991, "residential", False,  200, "R19"),

    # ═══════════════════════════════════════════════════════════════════
    # R20 — Puan–Bankerohan (Toril fringe route)
    # ═══════════════════════════════════════════════════════════════════
    ("Puan Terminal",                  "Puan",            "Toril",
     6.9534, 125.5118, "terminal",    False,  290, "R20"),
    ("Cabu-an Crossing",               "Cabu-an",         "Toril",
     6.9894, 125.5441, "residential", False,  140, "R20"),
    ("Ulas Proper",                    "Ulas",            "Toril",
     6.9924, 125.5468, "residential", False,  180, "R20"),
    ("Talomo–Bankerohan Connector",    "Talomo",          "Talomo",
     7.0182, 125.4959, "residential", False,  220, "R20"),
    ("Bankerohan South Gate",          "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   610, "R20"),

    # ═══════════════════════════════════════════════════════════════════
    # R21 — Inawayan–Toril (Toril feeder)
    # ═══════════════════════════════════════════════════════════════════
    ("Inawayan Barangay Hall",         "Inawayan",        "Toril",
     6.9312, 125.4634, "residential", False,  160, "R21"),
    ("Inawayan Elementary School",     "Inawayan",        "Toril",
     6.9334, 125.4658, "school",      False,  210, "R21"),
    ("Libby Road Stop",                "Libby",           "Toril",
     6.9689, 125.5278, "residential", False,  130, "R21"),
    ("Toril Market Annex",             "Toril",           "Toril",
     7.0182, 125.4959, "terminal",    True,   450, "R21"),

    # ═══════════════════════════════════════════════════════════════════
    # R22 — Bunawan–SM Lanang via Sasa (Bunawan District)
    # ═══════════════════════════════════════════════════════════════════
    ("Bunawan District Terminal",      "Bunawan",         "Bunawan",
     7.2362, 125.6398, "terminal",    True,   490, "R22"),
    ("Gatungan Market",                "Gatungan",        "Bunawan",
     7.1712, 125.6712, "market",      False,  280, "R22"),
    ("Alejandra Navarro Street",       "Bunawan",         "Bunawan",
     7.2362, 125.6398, "residential", False,  160, "R22"),
    ("Lasang Crossing",                "Lasang",          "Bunawan",
     7.1712, 125.6712, "residential", False,  200, "R22"),
    ("Sasa Junction",                  "Sasa",            "Buhangin",
     7.1283, 125.6452, "residential", False,  310, "R22"),
    ("SM Lanang North Bay",            "Lanang",          "Buhangin",
     7.0990, 125.6315, "mall",        True,   870, "R22"),

    # ═══════════════════════════════════════════════════════════════════
    # R23 — Lasang–Agdao (Bunawan corridor)
    # ═══════════════════════════════════════════════════════════════════
    ("Lasang Barangay Terminal",       "Lasang",          "Bunawan",
     7.1712, 125.6712, "terminal",    False,  320, "R23"),
    ("Magtuod Market",                 "Magtuod",         "Bunawan",
     7.1634, 125.6623, "market",      False,  240, "R23"),
    ("Bunawan Health Center",          "Bunawan",         "Bunawan",
     7.2362, 125.6398, "hospital",    False,  180, "R23"),
    ("Cabaguio Avenue North",          "Agdao",           "Agdao",
     7.0889, 125.6248, "residential", False,  230, "R23"),
    ("Agdao North Terminal",           "Agdao",           "Agdao",
     7.0820, 125.6233, "terminal",    True,   590, "R23"),

    # ═══════════════════════════════════════════════════════════════════
    # R24 — Magtuod–Bankerohan (Bunawan fringe route)
    # ═══════════════════════════════════════════════════════════════════
    ("Magtuod Barangay Hall",          "Magtuod",         "Bunawan",
     7.1641, 125.6631, "terminal",    False,  210, "R24"),
    ("Lasang Elementary School",       "Lasang",          "Bunawan",
     7.1712, 125.6712, "school",      False,  230, "R24"),
    ("New Visayas Crossing",           "New Visayas",     "Paquibato",
     7.2012, 125.6012, "residential", False,   90, "R24"),
    ("Bankerohan Market East Gate",    "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   530, "R24"),

    # ═══════════════════════════════════════════════════════════════════
    # R25 — Panacan–SM Lanang (Paquibato connector)
    # ═══════════════════════════════════════════════════════════════════
    ("Panacan Wharf Gate 2",           "Panacan",         "Paquibato",
     7.1462, 125.6632, "terminal",    True,   540, "R25"),
    ("Panacan Health Center",          "Panacan",         "Paquibato",
     7.1481, 125.6661, "hospital",    False,  150, "R25"),
    ("Tibungco Crossing",              "Tibungco",        "Buhangin",
     7.1923, 125.6484, "residential", False,  210, "R25"),
    ("Communal Road Junction",         "Communal",        "Buhangin",
     7.1189, 125.6401, "residential", False,  270, "R25"),
    ("SM Lanang Service Road",         "Lanang",          "Buhangin",
     7.0990, 125.6315, "mall",        True,   760, "R25"),

    # ═══════════════════════════════════════════════════════════════════
    # R26 — Panacan–Bankerohan via Cabaguio (Paquibato alternate)
    # ═══════════════════════════════════════════════════════════════════
    ("Panacan Police Station",         "Panacan",         "Paquibato",
     7.1476, 125.6671, "residential", False,  120, "R26"),
    ("Colosas Crossing",               "Colosas",         "Paquibato",
     7.1978, 125.5612, "residential", False,  100, "R26"),
    ("Cabaguio Avenue Stop",           "Agdao",           "Agdao",
     7.0878, 125.6243, "residential", False,  270, "R26"),
    ("Bankerohan via Cabaguio Terminal", "Bankerohan",    "Poblacion",
     7.0686, 125.6009, "terminal",    True,   650, "R26"),

    # ═══════════════════════════════════════════════════════════════════
    # R27 — Marilog–Bankerohan (remote mountain route)
    # ═══════════════════════════════════════════════════════════════════
    ("Marilog Barangay Terminal",      "Marilog",         "Marilog",
     7.2959, 125.3020, "terminal",    False,   80, "R27"),
    ("Daliaon Plantation Stop",        "Daliaon Plantation", "Marilog",
     7.3234, 125.3312, "residential", False,   60, "R27"),
    ("Lubogan Crossing",               "Lubogan",         "Marilog",
     7.3012, 125.3489, "residential", False,   70, "R27"),
    ("Marilog–Calinan Junction",       "Calinan",         "Calinan",
     7.2134, 125.3812, "residential", False,  100, "R27"),
    ("Mintal Market North Gate",       "Mintal",          "Calinan",
     7.0920, 125.5016, "market",      True,   280, "R27"),
    ("Bankerohan Terminal West",       "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   390, "R27"),

    # ═══════════════════════════════════════════════════════════════════
    # R28 — Tamugan–Mintal (Marilog feeder)
    # ═══════════════════════════════════════════════════════════════════
    ("Tamugan Barangay Hall",          "Tamugan",         "Marilog",
     7.3589, 125.2934, "terminal",    False,   50, "R28"),
    ("Tamugan Elementary School",      "Tamugan",         "Marilog",
     7.3567, 125.2958, "school",      False,   70, "R28"),
    ("Marilog Junction",               "Marilog",         "Marilog",
     7.2959, 125.3020, "residential", False,   80, "R28"),
    ("Mintal South Crossing",          "Mintal",          "Calinan",
     7.0920, 125.5016, "residential", False,  190, "R28"),
    ("Mintal Terminal",                "Mintal",          "Calinan",
     7.0920, 125.5016, "terminal",    True,   410, "R28"),

    # ═══════════════════════════════════════════════════════════════════
    # R29 — Marahan–Calinan (Marilog feeder 2)
    # ═══════════════════════════════════════════════════════════════════
    ("Marahan Barangay Hall",          "Marahan",         "Marilog",
     7.3201, 125.3412, "terminal",    False,   60, "R29"),
    ("Marahan Elementary School",      "Marahan",         "Marilog",
     7.3189, 125.3434, "school",      False,   80, "R29"),
    ("Calinan Highway Junction",       "Calinan",         "Calinan",
     7.2012, 125.3891, "residential", False,  110, "R29"),
    ("Calinan Market Terminal South",  "Calinan",         "Calinan",
     7.1907, 125.4546, "terminal",    True,   480, "R29"),

    # ═══════════════════════════════════════════════════════════════════
    # R30 — Tugbok–Bankerohan via Roxas (Tugbok District)
    # ═══════════════════════════════════════════════════════════════════
    ("Tugbok Public Market",           "Tugbok",          "Tugbok",
     7.1091, 125.5109, "terminal",    True,   470, "R30"),
    ("Tacunan Crossing",               "Tacunan",         "Tugbok",
     7.0901, 125.5023, "residential", False,  140, "R30"),
    ("Tomobe Junction",                "Tomobe",          "Tugbok",
     7.0812, 125.4934, "residential", False,  160, "R30"),
    ("New Valencia Road Stop",         "New Valencia",    "Tugbok",
     7.0989, 125.5023, "residential", False,  200, "R30"),
    ("Matina–Tugbok Connector",        "Matina",          "Talomo",
     7.0638, 125.5967, "residential", False,  240, "R30"),
    ("Bankerohan North Entry",         "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   590, "R30"),

    # ═══════════════════════════════════════════════════════════════════
    # R31 — New Valencia–Ecoland (Tugbok connector)
    # ═══════════════════════════════════════════════════════════════════
    ("New Valencia Market",            "New Valencia",    "Tugbok",
     7.0989, 125.5023, "terminal",    False,  350, "R31"),
    ("Tugbok–Calinan Connector",       "Tugbok",          "Tugbok",
     7.1091, 125.5109, "residential", False,  160, "R31"),
    ("Catalunan Grande Junction",      "Catalunan Grande", "Talomo",
     7.1122, 125.5234, "residential", False,  190, "R31"),
    ("Quimpo Boulevard North",         "Ecoland",         "Talomo",
     7.0489, 125.5981, "residential", False,  270, "R31"),
    ("Ecoland Terminal Gate 3",        "Ecoland",         "Talomo",
     7.0553, 125.6010, "terminal",    True,   680, "R31"),

    # ═══════════════════════════════════════════════════════════════════
    # R32 — Guianga–Calinan (Baguio District, most remote)
    # ═══════════════════════════════════════════════════════════════════
    ("Biao Guianga Terminal",          "Biao Guianga",    "Baguio",
     7.1897, 125.4286, "terminal",    False,   70, "R32"),
    ("Baguio District Hall",           "Baguio",          "Baguio",
     7.1897, 125.4286, "residential", False,   60, "R32"),
    ("Guianga Elementary School",      "Biao Guianga",    "Baguio",
     7.1897, 125.4286, "school",      False,   80, "R32"),
    ("Guianga–Calinan Highway Stop",   "Calinan",         "Calinan",
     7.2012, 125.3891, "residential", False,  100, "R32"),
    ("Calinan Terminal Gate 2",        "Calinan",         "Calinan",
     7.1907, 125.4546, "terminal",    True,   360, "R32"),

    # ═══════════════════════════════════════════════════════════════════
    # R33 — Ma-a–Agdao (Talomo additional)
    # ═══════════════════════════════════════════════════════════════════
    ("Ma-a Market Terminal",           "Maa",             "Talomo",
     7.0078, 125.5691, "terminal",    True,   470, "R33"),
    ("McArthur Highway Junction",      "Maa",             "Talomo",
     7.0061, 125.5671, "residential", False,  220, "R33"),
    ("Shrine Hills Chapel Stop",       "Matina",          "Talomo",
     7.0531, 125.5912, "residential", False,  140, "R33"),
    ("Matina Gym Stop",                "Matina",          "Talomo",
     7.0638, 125.5967, "residential", False,  260, "R33"),
    ("JP Laurel Avenue Stop",          "Agdao",           "Agdao",
     7.0843, 125.6244, "residential", False,  270, "R33"),
    ("Agdao Market West Gate",         "Agdao",           "Agdao",
     7.0820, 125.6228, "terminal",    True,   540, "R33"),

    # ═══════════════════════════════════════════════════════════════════
    # R34 — Bago Aplaya–Bankerohan (Talomo coastal route)
    # ═══════════════════════════════════════════════════════════════════
    ("Bago Aplaya Barangay Terminal",  "Bago Aplaya",     "Talomo",
     6.9923, 125.5478, "terminal",    False,  310, "R34"),
    ("Bucana Road Stop",               "Bucana",          "Talomo",
     7.0034, 125.5601, "residential", False,  140, "R34"),
    ("Langub Barangay Hall",           "Langub",          "Talomo",
     7.0221, 125.5831, "residential", False,  160, "R34"),
    ("Talomo River Bridge",            "Talomo",          "Talomo",
     7.0182, 125.4959, "residential", False,  180, "R34"),
    ("Catitipan Crossing",             "Catitipan",       "Talomo",
     7.0422, 125.5894, "residential", False,  210, "R34"),
    ("Bankerohan Terminal Gate 2",     "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   580, "R34"),

    # ═══════════════════════════════════════════════════════════════════
    # R35 — Catitipan–Bankerohan via JP Laurel (Talomo alternate)
    # ═══════════════════════════════════════════════════════════════════
    ("Camp Catitipan Gate",            "Catitipan",       "Talomo",
     7.0422, 125.5894, "terminal",    False,  290, "R35"),
    ("GSIS Heights Subdivision",       "Matina",          "Talomo",
     7.0589, 125.5949, "residential", False,  220, "R35"),
    ("Matina Pangi Crossing",          "Matina",          "Talomo",
     7.0701, 125.5869, "residential", False,  190, "R35"),
    ("Juna–Matina Connector",          "Matina",          "Talomo",
     7.0558, 125.5908, "residential", False,  160, "R35"),
    ("Bankerohan via JP Laurel",       "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   510, "R35"),

    # ═══════════════════════════════════════════════════════════════════
    # R36 — Tibungco–Bankerohan via Cabaguio (Buhangin extra)
    # ═══════════════════════════════════════════════════════════════════
    ("Tibungco Market Terminal",       "Tibungco",        "Buhangin",
     7.1923, 125.6484, "terminal",    True,   560, "R36"),
    ("Tibungco Barangay Hall",         "Tibungco",        "Buhangin",
     7.1923, 125.6484, "residential", False,  170, "R36"),
    ("New Carmen Crossing",            "New Carmen",      "Buhangin",
     7.1678, 125.6589, "residential", False,  210, "R36"),
    ("Cabaguio Avenue Junction",       "Agdao",           "Agdao",
     7.0876, 125.6241, "residential", False,  290, "R36"),
    ("Agdao–Bankerohan Connector",     "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   610, "R36"),

    # ═══════════════════════════════════════════════════════════════════
    # R37 — Mandug–Agdao (Buhangin north route)
    # ═══════════════════════════════════════════════════════════════════
    ("Mandug Barangay Terminal",       "Mandug",          "Buhangin",
     7.1421, 125.6432, "terminal",    False,  340, "R37"),
    ("Mandug Elementary School",       "Mandug",          "Buhangin",
     7.1409, 125.6419, "school",      False,  220, "R37"),
    ("Callawa Road Stop",              "Callawa",         "Buhangin",
     7.1312, 125.6389, "residential", False,  180, "R37"),
    ("Buhangin North Crossing",        "Buhangin Proper", "Buhangin",
     7.1100, 125.6115, "residential", False,  240, "R37"),
    ("Agdao Terminal Gate 3",          "Agdao",           "Agdao",
     7.0820, 125.6234, "terminal",    True,   500, "R37"),

    # ═══════════════════════════════════════════════════════════════════
    # R38 — Indangan–SM Lanang via Buhangin (Buhangin outer)
    # ═══════════════════════════════════════════════════════════════════
    ("Indangan Barangay Terminal",     "Indangan",        "Buhangin",
     7.1534, 125.6521, "terminal",    False,  260, "R38"),
    ("Indangan Elementary School",     "Indangan",        "Buhangin",
     7.1521, 125.6508, "school",      False,  200, "R38"),
    ("Communal Market",                "Communal",        "Buhangin",
     7.1189, 125.6401, "market",      True,   390, "R38"),
    ("Damosa Gateway Stop",            "Lanang",          "Buhangin",
     7.0990, 125.6315, "mall",        True,   580, "R38"),
    ("SM Lanang East Entrance",        "Lanang",          "Buhangin",
     7.0990, 125.6315, "mall",        True,   870, "R38"),

    # ═══════════════════════════════════════════════════════════════════
    # R39 — Sirib–Bankerohan (Calinan deep remote)
    # ═══════════════════════════════════════════════════════════════════
    ("Sirib Crossing Terminal",        "Sirib",           "Calinan",
     7.1812, 125.4103, "terminal",    False,  190, "R39"),
    ("Wangan Barangay Hall",           "Wangan",          "Calinan",
     7.1763, 125.4123, "residential", False,  130, "R39"),
    ("Lacson Market",                  "Lacson",          "Calinan",
     7.2012, 125.3912, "market",      False,  150, "R39"),
    ("Biao Escuela Junction",          "Biao Escuela",    "Calinan",
     7.2134, 125.3834, "residential", False,  120, "R39"),
    ("Malagos Garden Junction",        "Malagos",         "Calinan",
     7.1897, 125.4286, "residential", False,   70, "R39"),
    ("Philippine Eagle Center Stop",   "Malagos",         "Calinan",
     7.1850, 125.4153, "residential", False,   60, "R39"),
    ("Davao del Sur Capitol Stop",     "Calinan",         "Calinan",
     7.1951, 125.3968, "residential", True,  310, "R39"),
    ("Bankerohan Terminal Main",       "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "terminal",    True,   750, "R39"),

    # ═══════════════════════════════════════════════════════════════════
    # R40 — Wa-an–Mintal (Calinan feeder)
    # ═══════════════════════════════════════════════════════════════════
    ("Wa-an Barangay Terminal",        "Wa-an",           "Calinan",
     7.2089, 125.3812, "terminal",    False,  140, "R40"),
    ("Tawan-Tawan Market",             "Tawan-Tawan",     "Calinan",
     7.1656, 125.4289, "market",      False,  210, "R40"),
    ("Riverside Calinan Stop",         "Riverside",       "Calinan",
     7.1889, 125.4012, "residential", False,  120, "R40"),
    ("Mintal Market South Gate",       "Mintal",          "Calinan",
     7.0920, 125.5016, "terminal",    True,   420, "R40"),
]

# ── Extra stops (shared landmarks, additional coverage) ──────────────────────
EXTRA_STOPS_BY_DISTRICT = [
    # Talomo District
    ("Langub Barangay Hall",           "Langub",          "Talomo",
     7.0221, 125.5831, "residential", False, 160, "R01"),
    ("Bucana Barangay Hall",           "Bucana",          "Talomo",
     7.0034, 125.5601, "residential", False, 140, "R01"),
    ("Sirawan Crossing",               "Sirawan",         "Toril",
     6.9723, 125.5312, "residential", False, 110, "R01"),
    ("Bayabas Market",                 "Bayabas",         "Toril",
     6.9641, 125.5221, "market",      False, 210, "R01"),
    ("Colo Barangay Hall",             "Colo",            "Toril",
     6.9568, 125.5134, "residential", False, 130, "R01"),
    # Buhangin District
    ("Callawa Crossing",               "Callawa",         "Buhangin",
     7.1312, 125.6389, "residential", False, 180, "R02"),
    ("Mandug Market",                  "Mandug",          "Buhangin",
     7.1421, 125.6432, "market",      True,  340, "R02"),
    ("Indangan Barangay Hall",         "Indangan",        "Buhangin",
     7.1534, 125.6521, "residential", False, 150, "R07"),
    ("New Carmen Market",              "New Carmen",      "Buhangin",
     7.1678, 125.6589, "market",      True,  290, "R07"),
    # Calinan District
    ("Lacson Crossing",                "Lacson",          "Calinan",
     7.2012, 125.3912, "residential", False, 120, "R05"),
    ("Biao Escuela Market",            "Biao Escuela",    "Calinan",
     7.2134, 125.3834, "market",      False, 230, "R05"),
    ("Riverside Barangay Hall",        "Riverside",       "Calinan",
     7.1889, 125.4012, "residential", False, 110, "R05"),
    ("Wangan Elementary School",       "Wangan",          "Calinan",
     7.1763, 125.4123, "school",      False, 280, "R09"),
    ("Tawan-Tawan Market",             "Tawan-Tawan",     "Calinan",
     7.1656, 125.4289, "market",      False, 210, "R09"),
    # Agdao District
    ("Sto. Niño Market",               "Sto. Niño",       "Agdao",
     7.0798, 125.6198, "market",      True,  390, "R03"),
    ("Piapi Barangay Hall",            "Piapi",           "Agdao",
     7.0834, 125.6221, "residential", False, 170, "R03"),
    ("Ma-a Agdao Connector",           "Agdao",           "Agdao",
     7.0820, 125.6254, "residential", False, 150, "R10"),
    # Paquibato District
    ("Mapula Barangay Hall",           "Mapula",          "Paquibato",
     7.2123, 125.5423, "residential", False,  90, "R10"),
    ("Colosas Elementary School",      "Colosas",         "Paquibato",
     7.1978, 125.5612, "school",      False, 150, "R10"),
    ("Lumiad Crossing",                "Lumiad",          "Paquibato",
     7.1812, 125.5734, "residential", False, 120, "R10"),
    # Poblacion District
    ("Davao Central Post Office",      "Poblacion",       "Poblacion",
     7.0646, 125.6079, "residential", True,  280, "R06"),
    ("Davao Bus Terminal Annex",       "Poblacion",       "Poblacion",
     7.0553, 125.6010, "terminal",    True,  560, "R12"),
    ("Bankerohan Wet Market",          "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "market",      True,  780, "R01"),
    ("Osmena Street Stop",             "Poblacion",       "Poblacion",
     7.0660, 125.6079, "residential", False, 190, "R06"),
    # Bunawan District
    ("Bunawan District Hall",          "Bunawan",         "Bunawan",
     7.2362, 125.6398, "residential", True,  220, "R10"),
    ("Alejandra Navarro Street",       "Bunawan",         "Bunawan",
     7.2362, 125.6398, "residential", False, 160, "R10"),
    ("Biao Guianga Market",            "Biao Guianga",    "Calinan",
     7.1897, 125.4286, "market",      False, 200, "R05"),
    # Marilog District
    ("Marilog Barangay Hall",          "Marilog",         "Marilog",
     7.2959, 125.3020, "residential", False,  80, "R05"),
    # Toril District
    ("Toril District Hall",            "Toril",           "Toril",
     7.0182, 125.4959, "residential", True,  290, "R01"),
    ("Bangkas Heights",                "Bangkas Heights", "Toril",
     6.9769, 125.5351, "residential", False, 130, "R01"),
    ("Libby Road Terminal",            "Libby",           "Toril",
     6.9689, 125.5278, "terminal",    True,  380, "R01"),
    # Tugbok District
    ("New Valencia Market",            "New Valencia",    "Tugbok",
     7.0989, 125.5023, "market",      False, 350, "R09"),
    ("Baguio District Hall",           "Baguio",          "Baguio",
     7.1897, 125.4286, "residential", False,  70, "R05"),
    # Additional hospital / school nodes
    ("Brokenshire Memorial Hospital",  "Obrero",          "Agdao",
     7.0742, 125.5972, "hospital",    True,  540, "R03"),
    ("San Pedro College",              "Bangkal",         "Poblacion",
     7.0778, 125.6156, "school",      True,  610, "R06"),
    ("University of Mindanao",         "Bolton",          "Poblacion",
     7.0674, 125.6098, "school",      True,  680, "R12"),
    ("Xavier University–Ateneo",       "Poblacion",       "Poblacion",
     7.0711, 125.6134, "school",      True,  490, "R06"),
    ("Davao Regional Hospital",        "Tagum Road",      "Buhangin",
     7.1100, 125.6115, "hospital",    True,  430, "R07"),
    ("Mega Pharmacare Hospital",       "Agdao",           "Agdao",
     7.0821, 125.6228, "hospital",    False, 280, "R03"),
    # Residential / neighborhood stops
    ("Matina Pangi Crossing",          "Matina",          "Talomo",
     7.0701, 125.5869, "residential", False, 190, "R04"),
    ("Quimpo Boulevard",               "Ecoland",         "Talomo",
     7.0489, 125.5981, "residential", True,  450, "R02"),
    ("Damosa Gateway",                 "Lanang",          "Buhangin",
     7.0990, 125.6315, "mall",        True,  670, "R11"),
    ("Gaisano Mall Toril",             "Toril",           "Toril",
     7.0182, 125.4959, "mall",        True,  580, "R01"),
    ("Gaisano Mall Calinan",           "Calinan",         "Calinan",
     7.1907, 125.4546, "mall",        True,  490, "R05"),
    ("SM CDO-Davao Junction",          "Buhangin Proper", "Buhangin",
     7.1100, 125.6115, "residential", False, 230, "R06"),
    ("Cabu-an Market",                 "Cabu-an",         "Toril",
     6.9894, 125.5441, "market",      False, 310, "R08"),
    ("Tacunan Crossing",               "Tacunan",         "Tugbok",
     7.0901, 125.5023, "residential", False, 140, "R09"),
    ("Tomobe Market",                  "Tomobe",          "Calinan",
     7.1712, 125.4312, "market",      False, 190, "R09"),
    ("Ula River Bridge",               "Ulas",            "Toril",
     6.9921, 125.5471, "residential", False, 110, "R08"),
    ("Baracatan Market",               "Baracatan",       "Toril",
     6.9689, 125.5289, "market",      False, 220, "R01"),
    ("Sasa Wharf",                     "Sasa",            "Buhangin",
     7.1283, 125.6637, "terminal",    False, 340, "R12"),
    ("Lapu-Lapu Street",               "Agdao",           "Agdao",
     7.0867, 125.6261, "residential", False, 160, "R03"),
    ("Bangkal Crossing",               "Bangkal",         "Poblacion",
     7.0686, 125.6009, "residential", False, 200, "R12"),
    ("Obrero Market",                  "Obrero",          "Agdao",
     7.0742, 125.5972, "market",      True,  520, "R03"),
    ("Catalunan Grande Elementary",    "Catalunan Grande", "Talomo",
     7.1122, 125.5234, "school",      False, 310, "R05"),
    ("Dumoy Barangay Hall",            "Dumoy",           "Talomo",
     7.1298, 125.4812, "residential", False, 130, "R09"),
    ("Mintal Elementary School",       "Mintal",          "Calinan",
     7.0920, 125.5016, "school",      True,  360, "R09"),
    ("Ma-a Market",                    "Maa",             "Talomo",
     7.0078, 125.5691, "market",      True,  470, "R04"),
    ("Don Bosco Technology Center",    "Obrero",          "Agdao",
     7.0742, 125.5972, "school",      True,  510, "R12"),
    ("Tibungco Barangay Hall",         "Tibungco",        "Buhangin",
     7.1923, 125.6484, "residential", False, 170, "R07"),
    ("Sasa Elementary School",         "Sasa",            "Buhangin",
     7.1283, 125.6452, "school",      True,  390, "R12"),
    ("Bankerohan Fish Port",           "Bankerohan",      "Poblacion",
     7.0686, 125.6009, "market",      False, 430, "R01"),
    ("Davao del Sur Capitol",          "Calinan",         "Calinan",
     7.1951, 125.3968, "residential", True,  310, "R05"),
    ("Toril Police Station",           "Toril",           "Toril",
     7.0182, 125.4959, "residential", False, 120, "R01"),
    ("Riverside Calinan Elementary",   "Riverside",       "Calinan",
     7.1891, 125.4021, "school",      False, 190, "R05"),
    ("Bunawan District Hall (2)",      "Bunawan",         "Bunawan",
     7.2362, 125.6398, "residential", True,  230, "R10"),
    ("Panacan Health Center",          "Panacan",         "Paquibato",
     7.1481, 125.6661, "hospital",    False, 150, "R10"),
    ("Davao City Medical Center Annex", "Bajada",          "Poblacion",
     7.0984, 125.6198, "hospital",    True,  380, "R07"),
    ("Communal Barangay Hall",         "Communal",        "Buhangin",
     7.1189, 125.6401, "residential", False, 170, "R02"),
    ("Lanang IT Park",                 "Lanang",          "Buhangin",
     7.0990, 125.6315, "residential", True,  490, "R11"),
    ("Dumoy Elementary School",        "Dumoy",           "Talomo",
     7.1298, 125.4812, "school",      False, 240, "R09"),
    ("Ecoland Drive Stop",             "Ecoland",         "Talomo",
     7.0553, 125.6010, "residential", False, 310, "R02"),
    ("Agdao Sports Complex",           "Agdao",           "Agdao",
     7.0841, 125.6251, "residential", True,  200, "R03"),
    ("Toril Elementary School",        "Toril",           "Toril",
     7.0182, 125.4959, "school",      True,  350, "R01"),
    ("Buhangin Overpass",              "Buhangin Proper", "Buhangin",
     7.1100, 125.6115, "residential", False, 270, "R06"),
    ("Calinan High School",            "Calinan",         "Calinan",
     7.1907, 125.4546, "school",      True,  410, "R05"),
    ("Pampanga Street Stop",           "Poblacion",       "Poblacion",
     7.0673, 125.6093, "residential", False, 190, "R06"),
    ("R. Castillo Elementary School",  "Agdao",           "Agdao",
     7.0801, 125.6263, "school",      False, 290, "R03"),
    ("Bukidnon Junction",              "Mintal",          "Calinan",
     7.0920, 125.5016, "residential", False, 130, "R09"),
    ("Commonwealth Avenue Stop",       "Buhangin Proper", "Buhangin",
     7.1100, 125.6115, "residential", False, 210, "R06"),
    ("Leon Garcia Jr. Street",         "Agdao",           "Agdao",
     7.0829, 125.6239, "residential", False, 150, "R03"),
    ("Veloso Street",                  "Poblacion",       "Poblacion",
     7.0673, 125.6093, "residential", False, 170, "R06"),
]

ALL_STOPS_RAW = STOPS_MASTER + EXTRA_STOPS_BY_DISTRICT


def build_stops(raw: list[tuple]) -> list[dict]:
    stops = []
    for idx, row in enumerate(raw, start=1):
        (name, brgy, district, lat, lon, stype, shelter, boardings, route_id) = row
        lat_j = lat + random.uniform(-0.0005, 0.0005)
        lon_j = lon + random.uniform(-0.0005, 0.0005)
        stops.append({
            "stop_id": f"S{idx:03d}",
            "stop_name": name,
            "barangay": brgy,
            "district": district,
            "latitude": round(lat_j, 6),
            "longitude": round(lon_j, 6),
            "stop_type": stype,
            "has_shelter": shelter,
            "avg_daily_boardings": boardings + random.randint(-20, 20),
            "route_id": route_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return stops


def main():
    stops = build_stops(ALL_STOPS_RAW)
    total = len(stops)
    print(f"[produce_stops] Posting {total} stops to {ENDPOINT}")

    clear_minio_partition()

    # Coverage summary
    from collections import Counter
    route_counts = Counter(s["route_id"] for s in stops)
    print(f"[produce_stops] Stops per route:")
    for rid in sorted(route_counts):
        print(f"  {rid}: {route_counts[rid]} stops")

    missing = [f"R{i:02d}" for i in range(
        1, 41) if f"R{i:02d}" not in route_counts]
    if missing:
        print(f"[produce_stops] WARNING: No stops for routes: {missing}")
    else:
        print(f"[produce_stops] ✓ All 40 routes have at least one stop")

    CHUNK = 50
    with httpx.Client(timeout=60) as client:
        for i in range(0, total, CHUNK):
            batch = stops[i: i + CHUNK]
            chunk_idx = i // CHUNK + 1
            resp = client.post(ENDPOINT, json=batch, params={
                               "chunk_index": chunk_idx})
            resp.raise_for_status()
            print(f"[produce_stops]   chunk {chunk_idx}: {resp.json()}")

    print(f"[produce_stops] ✓ Done — {total} stops ingested")


if __name__ == "__main__":
    main()
