"""
produce_stops.py
----------------
Generates ~180 real Davao City jeepney stops (landmarks, markets, schools,
hospitals, malls, terminals) and POSTs them to POST /ingest/stops.

GPS bounds: lat 6.8–7.5, lon 125.0–126.0 (actual Davao City range)
Core CBD stops cluster near lat 7.06–7.12, lon 125.60–125.65

FK dependencies: routes (R01–R12) must exist first
"""

import random
from datetime import datetime, timezone

import httpx

API_BASE = "http://fastapi:8000"
ENDPOINT = f"{API_BASE}/ingest/stops"

SEED = 42
random.seed(SEED)

# stop_type ENUM from data model
STOP_TYPES = ["terminal", "market", "school", "hospital", "mall", "residential"]

# (stop_name, barangay, district, lat, lon, stop_type, has_shelter, avg_daily_boardings, route_id)
# Real Davao landmarks with approximate GPS coordinates
STOPS_MASTER = [
    # ── R01 Bankerohan–Toril ──────────────────────────────────────────────────
    ("Bankerohan Market Terminal",     "Bankerohan",      "Poblacion",  7.0614, 125.6090, "terminal",    True,  1200, "R01"),
    ("Ramon Magsaysay Park",           "Davao City Proper","Poblacion", 7.0647, 125.6123, "residential", False,  320, "R01"),
    ("Ateneo de Davao University",     "Loyola Heights",  "Poblacion",  7.0736, 125.6131, "school",      True,   580, "R01"),
    ("Victoria Plaza Mall",            "Bajada",          "Poblacion",  7.0831, 125.6140, "mall",        True,   750, "R01"),
    ("San Pedro Cathedral Stop",       "San Pedro",       "Poblacion",  7.0625, 125.6095, "residential", False,  210, "R01"),
    ("Catitipan Market",               "Catitipan",       "Talomo",     7.0422, 125.5997, "market",      False,  390, "R01"),
    ("Matina Aplaya Barangay Hall",    "Matina Aplaya",   "Talomo",     7.0311, 125.5903, "residential", False,  260, "R01"),
    ("Talomo Public Market",           "Talomo",          "Talomo",     7.0156, 125.5762, "market",      True,   610, "R01"),
    ("Maa Crossing",                   "Maa",             "Talomo",     7.0071, 125.5681, "residential", False,  340, "R01"),
    ("Bago Oshiro Market",             "Bago Oshiro",     "Talomo",     6.9988, 125.5592, "market",      False,  290, "R01"),
    ("Toril Bridge",                   "Toril",           "Toril",      6.9834, 125.5421, "residential", False,  180, "R01"),
    ("Toril Public Market",            "Toril",           "Toril",      6.9812, 125.5398, "terminal",    True,   820, "R01"),

    # ── R02 Ecoland–SM Lanang ─────────────────────────────────────────────────
    ("Ecoland Bus Terminal",           "Ecoland",         "Talomo",     7.0444, 125.5962, "terminal",    True,  1500, "R02"),
    ("NCCC Mall Bajada",               "Bajada",          "Poblacion",  7.0837, 125.6145, "mall",        True,   880, "R02"),
    ("Southern Philippines Medical Center","Bajada",      "Poblacion",  7.0869, 125.6163, "hospital",    True,   670, "R02"),
    ("Pelayo Street",                  "Davao City Proper","Poblacion", 7.0673, 125.6110, "residential", False,  220, "R02"),
    ("Davao City Hall",                "San Pedro",       "Poblacion",  7.0644, 125.6127, "residential", True,   490, "R02"),
    ("Bankerohan Bridge",              "Bankerohan",      "Poblacion",  7.0631, 125.6093, "residential", False,  310, "R02"),
    ("Rizal Park",                     "Poblacion",       "Poblacion",  7.0651, 125.6117, "residential", False,  250, "R02"),
    ("Jacinto Extension",              "Poblacion",       "Poblacion",  7.0693, 125.6134, "residential", False,  180, "R02"),
    ("Buhangin District Hall",         "Buhangin Proper", "Buhangin",   7.1012, 125.6278, "residential", True,   390, "R02"),
    ("Davao International Airport",    "Sasa",            "Buhangin",   7.1255, 125.6457, "terminal",    True,   920, "R02"),
    ("SM City Lanang",                 "Lanang",          "Buhangin",   7.1189, 125.6532, "mall",        True,  1100, "R02"),

    # ── R03 Agdao Loop ────────────────────────────────────────────────────────
    ("Agdao Public Market",            "Agdao",           "Agdao",      7.0812, 125.6232, "terminal",    True,  1050, "R03"),
    ("Leon Garcia Street",             "Agdao",           "Agdao",      7.0834, 125.6248, "residential", False,  270, "R03"),
    ("R. Castillo Street",             "Agdao",           "Agdao",      7.0798, 125.6261, "residential", False,  230, "R03"),
    ("Agdao Health Center",            "Agdao",           "Agdao",      7.0821, 125.6219, "hospital",    True,   310, "R03"),
    ("Wilfredo Aquino Avenue",         "Agdao",           "Agdao",      7.0856, 125.6203, "residential", False,  190, "R03"),
    ("Agdao Elementary School",        "Agdao",           "Agdao",      7.0869, 125.6234, "school",      True,   420, "R03"),

    # ── R04 Matina–Davao Medical Center ──────────────────────────────────────
    ("Matina Town Square",             "Matina",          "Talomo",     7.0633, 125.5977, "terminal",    True,   980, "R04"),
    ("Matina Crossing",                "Matina",          "Talomo",     7.0621, 125.5964, "residential", False,  380, "R04"),
    ("University of the Immaculate Conception","Matina",  "Talomo",     7.0598, 125.5941, "school",      True,   720, "R04"),
    ("Matina Market",                  "Matina",          "Talomo",     7.0582, 125.5923, "market",      True,   540, "R04"),
    ("Juna Subdivision",               "Matina",          "Talomo",     7.0551, 125.5901, "residential", False,  260, "R04"),
    ("Davao Doctors Hospital",         "Bajada",          "Poblacion",  7.0856, 125.6128, "hospital",    True,   630, "R04"),
    ("Davao Medical Center",           "Maa",             "Talomo",     7.0082, 125.5679, "hospital",    True,   890, "R04"),

    # ── R05 Calinan–Bankerohan ────────────────────────────────────────────────
    ("Calinan Market Terminal",        "Calinan",         "Calinan",    7.1934, 125.3987, "terminal",    True,   760, "R05"),
    ("Calinan Elementary School",      "Calinan",         "Calinan",    7.1923, 125.3972, "school",      True,   380, "R05"),
    ("Sirib Crossing",                 "Sirib",           "Calinan",    7.1812, 125.4103, "residential", False,  190, "R05"),
    ("Mintal Market",                  "Mintal",          "Calinan",    7.1543, 125.4421, "market",      True,   520, "R05"),
    ("Catalunan Grande Market",        "Catalunan Grande","Talomo",     7.1122, 125.5234, "market",      True,   440, "R05"),
    ("Catalunan Pequeño Hall",         "Catalunan Pequeño","Talomo",    7.0978, 125.5412, "residential", False,  230, "R05"),
    ("Matina Pangi",                   "Matina",          "Talomo",     7.0711, 125.5841, "residential", False,  170, "R05"),

    # ── R06 Poblacion–Buhangin ────────────────────────────────────────────────
    ("Poblacion District Hall",        "Poblacion",       "Poblacion",  7.0641, 125.6103, "terminal",    True,   690, "R06"),
    ("Davao Crocodile Park",           "Sasa",            "Buhangin",   7.1156, 125.6418, "residential", False,  140, "R06"),
    ("Gem-Ver",                        "Poblacion",       "Poblacion",  7.0688, 125.6122, "residential", False,  160, "R06"),
    ("Pichon Street",                  "Poblacion",       "Poblacion",  7.0701, 125.6134, "residential", False,  140, "R06"),
    ("Buhangin Public Market",         "Buhangin Proper", "Buhangin",   7.1023, 125.6289, "market",      True,   680, "R06"),
    ("Buhangin District Terminal",     "Buhangin Proper", "Buhangin",   7.1039, 125.6301, "terminal",    True,   720, "R06"),

    # ── R07 Bajada–Tibungco ───────────────────────────────────────────────────
    ("Bajada Terminal",                "Bajada",          "Poblacion",  7.0841, 125.6148, "terminal",    True,   870, "R07"),
    ("Lanang Business Park",           "Lanang",          "Buhangin",   7.1167, 125.6498, "residential", True,   420, "R07"),
    ("Agdao Overpass",                 "Agdao",           "Agdao",      7.0823, 125.6241, "residential", False,  230, "R07"),
    ("Panacan Market",                 "Panacan",         "Paquibato",  7.1489, 125.6682, "market",      True,   590, "R07"),
    ("Tibungco Market",                "Tibungco",        "Buhangin",   7.1621, 125.6721, "terminal",    True,   740, "R07"),

    # ── R08 Talomo–Ulas Loop ──────────────────────────────────────────────────
    ("Talomo District Hall",           "Talomo",          "Talomo",     7.0141, 125.5749, "residential", True,   290, "R08"),
    ("Ulas Elementary School",         "Ulas",            "Toril",      6.9934, 125.5581, "school",      False,  370, "R08"),
    ("Ulas Market",                    "Ulas",            "Toril",      6.9912, 125.5562, "market",      True,   450, "R08"),
    ("Ulas Barangay Hall",             "Ulas",            "Toril",      6.9898, 125.5548, "residential", False,  210, "R08"),

    # ── R09 Mintal–Bankerohan ─────────────────────────────────────────────────
    ("Mintal Crossing",                "Mintal",          "Calinan",    7.1561, 125.4398, "residential", False,  330, "R09"),
    ("Dumoy Market",                   "Dumoy",           "Talomo",     7.1298, 125.4812, "market",      True,   410, "R09"),
    ("Tugbok District Hall",           "Tugbok",          "Tugbok",     7.1102, 125.5123, "residential", True,   280, "R09"),
    ("Ma-a Junction",                  "Maa",             "Talomo",     7.0089, 125.5698, "residential", False,  310, "R09"),

    # ── R10 Panacan–Agdao ────────────────────────────────────────────────────
    ("Panacan Wharf Terminal",         "Panacan",         "Paquibato",  7.1502, 125.6701, "terminal",    True,   620, "R10"),
    ("Bunawan Public Market",          "Bunawan",         "Bunawan",    7.1312, 125.6534, "market",      True,   580, "R10"),
    ("Lasang Market",                  "Lasang",          "Bunawan",    7.1423, 125.6589, "market",      False,  320, "R10"),
    ("Tagum Road Junction",            "Panacan",         "Paquibato",  7.1476, 125.6644, "residential", False,  240, "R10"),

    # ── R11 Matina–SM Lanang Express ─────────────────────────────────────────
    ("Matina Town Square Express Bay", "Matina",          "Talomo",     7.0638, 125.5981, "terminal",    True,   760, "R11"),
    ("Quirino Avenue",                 "Poblacion",       "Poblacion",  7.0712, 125.6143, "residential", False,  390, "R11"),
    ("Ilustre Avenue",                 "Poblacion",       "Poblacion",  7.0731, 125.6152, "residential", False,  280, "R11"),
    ("Arco",                           "Lanang",          "Buhangin",   7.1143, 125.6512, "residential", False,  310, "R11"),
    ("SM City Lanang Express Bay",     "Lanang",          "Buhangin",   7.1193, 125.6539, "terminal",    True,  1250, "R11"),

    # ── R12 Sasa–Davao City Hall ──────────────────────────────────────────────
    ("Sasa Port Terminal",             "Sasa",            "Buhangin",   7.1289, 125.6471, "terminal",    True,   710, "R12"),
    ("Sasa Market",                    "Sasa",            "Buhangin",   7.1267, 125.6452, "market",      True,   530, "R12"),
    ("Agdao Market Extension",         "Agdao",           "Agdao",      7.0811, 125.6229, "market",      False,  280, "R12"),
    ("City Engineering Office",        "Poblacion",       "Poblacion",  7.0659, 125.6119, "residential", True,   190, "R12"),
    ("Davao City Hall",                "San Pedro",       "Poblacion",  7.0644, 125.6127, "residential", True,   620, "R12"),
]

# Fill remaining stops to reach ~180 total by adding more residential/barangay stops
EXTRA_STOPS_BY_DISTRICT = [
    # Talomo District
    ("Langub Barangay Hall",           "Langub",          "Talomo",     7.0221, 125.5831, "residential", False, 160, "R01"),
    ("Bucana Barangay Hall",           "Bucana",          "Talomo",     7.0034, 125.5601, "residential", False, 140, "R01"),
    ("Sirawan Crossing",               "Sirawan",         "Toril",      6.9723, 125.5312, "residential", False, 110, "R01"),
    ("Bayabas Market",                 "Bayabas",         "Toril",      6.9641, 125.5221, "market",      False, 210, "R01"),
    ("Colo Barangay Hall",             "Colo",            "Toril",      6.9568, 125.5134, "residential", False, 130, "R01"),
    # Buhangin District
    ("Callawa Crossing",               "Callawa",         "Buhangin",   7.1312, 125.6389, "residential", False, 180, "R02"),
    ("Mandug Market",                  "Mandug",          "Buhangin",   7.1421, 125.6432, "market",      True,  340, "R02"),
    ("Indangan Barangay Hall",         "Indangan",        "Buhangin",   7.1534, 125.6521, "residential", False, 150, "R07"),
    ("New Carmen Market",              "New Carmen",      "Buhangin",   7.1678, 125.6589, "market",      True,  290, "R07"),
    # Calinan District
    ("Lacson Crossing",                "Lacson",          "Calinan",    7.2012, 125.3912, "residential", False, 120, "R05"),
    ("Biao Escuela Market",            "Biao Escuela",    "Calinan",    7.2134, 125.3834, "market",      False, 230, "R05"),
    ("Riverside Barangay Hall",        "Riverside",       "Calinan",    7.1889, 125.4012, "residential", False, 110, "R05"),
    ("Wangan Elementary School",       "Wangan",          "Calinan",    7.1763, 125.4123, "school",      False, 280, "R09"),
    ("Tawan-Tawan Market",             "Tawan-Tawan",     "Calinan",    7.1656, 125.4289, "market",      False, 210, "R09"),
    # Agdao District
    ("Sto. Niño Market",               "Sto. Niño",       "Agdao",      7.0798, 125.6198, "market",      True,  390, "R03"),
    ("Piapi Barangay Hall",            "Piapi",           "Agdao",      7.0834, 125.6221, "residential", False, 170, "R03"),
    ("Ma-a Agdao Connector",           "Agdao",           "Agdao",      7.0812, 125.6254, "residential", False, 150, "R10"),
    # Paquibato District
    ("Mapula Barangay Hall",           "Mapula",          "Paquibato",  7.2123, 125.5423, "residential", False, 90,  "R10"),
    ("Colosas Elementary School",      "Colosas",         "Paquibato",  7.1978, 125.5612, "school",      False, 150, "R10"),
    ("Lumiad Crossing",                "Lumiad",          "Paquibato",  7.1812, 125.5734, "residential", False, 120, "R10"),
    # Poblacion District
    ("Davao Central Post Office",      "Poblacion",       "Poblacion",  7.0641, 125.6108, "residential", True,  280, "R06"),
    ("Davao Bus Terminal Annex",       "Poblacion",       "Poblacion",  7.0628, 125.6088, "terminal",    True,  560, "R12"),
    ("Bankerohan Wet Market",          "Bankerohan",      "Poblacion",  7.0618, 125.6082, "market",      True,  780, "R01"),
    ("Osmena Street Stop",             "Poblacion",       "Poblacion",  7.0659, 125.6113, "residential", False, 190, "R06"),
    # Bunawan District
    ("Bunawan District Hall",          "Bunawan",         "Bunawan",    7.1334, 125.6512, "residential", True,  220, "R10"),
    ("Alejandra Navarro Street",       "Bunawan",         "Bunawan",    7.1356, 125.6534, "residential", False, 160, "R10"),
    ("Biao Guianga Market",            "Biao Guianga",    "Calinan",    7.2289, 125.3723, "market",      False, 200, "R05"),
    # Marilog District
    ("Marilog Barangay Hall",          "Marilog",         "Marilog",    7.3412, 125.3212, "residential", False, 80,  "R05"),
    # Toril District
    ("Toril District Hall",            "Toril",           "Toril",      6.9834, 125.5409, "residential", True,  290, "R01"),
    ("Bangkas Heights",                "Bangkas Heights", "Toril",      6.9769, 125.5351, "residential", False, 130, "R01"),
    ("Libby Road Terminal",            "Libby",           "Toril",      6.9689, 125.5278, "terminal",    True,  380, "R01"),
    # Tugbok District
    ("Tugbok Public Market",           "Tugbok",          "Tugbok",     7.1091, 125.5109, "market",      True,  470, "R09"),
    ("New Valencia Market",            "New Valencia",    "Tugbok",     7.0989, 125.5023, "market",      False, 350, "R09"),
    ("Baguio District Hall",           "Baguio",          "Baguio",     7.3123, 125.5412, "residential", False, 70,  "R05"),
    # Additional hospital / school nodes
    ("Brokenshire Memorial Hospital",  "Obrero",          "Agdao",      7.0912, 125.6123, "hospital",    True,  540, "R03"),
    ("San Pedro College",              "Bangkal",         "Poblacion",  7.0634, 125.6101, "school",      True,  610, "R06"),
    ("University of Mindanao",         "Bolton",          "Poblacion",  7.0681, 125.6131, "school",      True,  680, "R12"),
    ("Xavier University–Ateneo",       "Poblacion",       "Poblacion",  7.0756, 125.6141, "school",      True,  490, "R06"),
    ("Davao Regional Hospital",        "Tagum Road",      "Buhangin",   7.1089, 125.6312, "hospital",    True,  430, "R07"),
    ("Mega Pharmacare Hospital",       "Agdao",           "Agdao",      7.0821, 125.6228, "hospital",    False, 280, "R03"),
    # Residential/neighborhood stops
    ("Matina Pangi Crossing",          "Matina",          "Talomo",     7.0701, 125.5869, "residential", False, 190, "R04"),
    ("JP Laurel Junction",             "Agdao",           "Agdao",      7.0843, 125.6244, "residential", False, 270, "R07"),
    ("Quimpo Boulevard",               "Ecoland",         "Talomo",     7.0468, 125.5982, "residential", True,  450, "R02"),
    ("Damosa Gateway",                 "Lanang",          "Buhangin",   7.1201, 125.6521, "mall",        True,  670, "R11"),
    ("Gaisano Mall Toril",             "Toril",           "Toril",      6.9841, 125.5402, "mall",        True,  580, "R01"),
    ("Gaisano Mall Calinan",           "Calinan",         "Calinan",    7.1942, 125.3961, "mall",        True,  490, "R05"),
    ("SM CDO-Davao Junction",          "Buhangin Proper", "Buhangin",   7.1045, 125.6298, "residential", False, 230, "R06"),
    ("Cabu-an Market",                 "Cabu-an",         "Toril",      6.9901, 125.5549, "market",      False, 310, "R08"),
    # More to round up to 180
    ("Tacunan Crossing",               "Tacunan",         "Tugbok",     7.0901, 125.5023, "residential", False, 140, "R09"),
    ("Tomobe Market",                  "Tomobe",          "Calinan",    7.1712, 125.4312, "market",      False, 190, "R09"),
    ("Ula River Bridge",               "Ulas",            "Toril",      6.9921, 125.5571, "residential", False, 110, "R08"),
    ("Baracatan Market",               "Baracatan",       "Toril",      6.9689, 125.5289, "market",      False, 220, "R01"),
    ("Sasa Wharf",                     "Sasa",            "Buhangin",   7.1298, 125.6482, "terminal",    False, 340, "R12"),
    ("Panacan Police Station",         "Panacan",         "Paquibato",  7.1476, 125.6671, "residential", False, 120, "R10"),
    ("Lapu-Lapu Street",               "Agdao",           "Agdao",      7.0867, 125.6261, "residential", False, 160, "R03"),
    ("Bangkal Crossing",               "Bangkal",         "Poblacion",  7.0631, 125.6099, "residential", False, 200, "R12"),
    ("Obrero Market",                  "Obrero",          "Agdao",      7.0912, 125.6131, "market",      True,  520, "R03"),
    ("Catalunan Grande Elementary",    "Catalunan Grande","Talomo",     7.1134, 125.5218, "school",      False, 310, "R05"),
    ("Dumoy Barangay Hall",            "Dumoy",           "Talomo",     7.1312, 125.4823, "residential", False, 130, "R09"),
    ("Mintal Elementary School",       "Mintal",          "Calinan",    7.1554, 125.4411, "school",      True,  360, "R09"),
    ("Ma-a Market",                    "Maa",             "Talomo",     7.0078, 125.5691, "market",      True,  470, "R04"),
    ("Daliaon Plantation",             "Daliaon Plantation","Marilog",  7.3234, 125.3312, "residential", False, 60,  "R05"),
    ("Mt. Apo View Crossing",          "Lubogan",         "Toril",      6.9412, 125.5012, "residential", False, 80,  "R01"),
    ("Magtuod Market",                 "Magtuod",         "Bunawan",    7.1634, 125.6623, "market",      False, 240, "R07"),
    ("Puan Barangay Hall",             "Puan",            "Toril",      6.9534, 125.5123, "residential", False, 100, "R01"),
    ("Gatungan Market",                "Gatungan",        "Bunawan",    7.1712, 125.6712, "market",      False, 280, "R07"),
    ("Calinan Police Station",         "Calinan",         "Calinan",    7.1928, 125.3978, "residential", False, 110, "R05"),
    ("Darong Elementary School",       "Darong",          "Toril",      6.9223, 125.4823, "school",      False, 190, "R01"),
    ("Tugbok Barangay Hall",           "Tugbok",          "Tugbok",     7.1098, 125.5112, "residential", False, 150, "R09"),
    ("Lasang Elementary School",       "Lasang",          "Bunawan",    7.1434, 125.6601, "school",      False, 230, "R10"),
    ("New Visayas Crossing",           "New Visayas",     "Paquibato",  7.2012, 125.6012, "residential", False, 90,  "R10"),
    ("GSIS Heights Subdivision",       "Matina",          "Talomo",     7.0589, 125.5949, "residential", False, 220, "R04"),
    ("Veloso Street",                  "Poblacion",       "Poblacion",  7.0698, 125.6139, "residential", False, 170, "R06"),
    ("Leon Garcia Jr. Street",         "Agdao",           "Agdao",      7.0829, 125.6239, "residential", False, 150, "R03"),
    ("Commonwealth Avenue Stop",       "Buhangin Proper", "Buhangin",   7.1056, 125.6311, "residential", False, 210, "R06"),
    ("Communal Market",                "Communal",        "Buhangin",   7.1189, 125.6401, "market",      True,  390, "R07"),
    ("Calapan Street",                 "Agdao",           "Agdao",      7.0845, 125.6255, "residential", False, 130, "R10"),
    ("R. Castillo Elementary School",  "Agdao",           "Agdao",      7.0801, 125.6263, "school",      False, 290, "R03"),
    ("Malagos Garden Resort Junction", "Malagos",         "Calinan",    7.2378, 125.3698, "residential", False, 70,  "R05"),
    ("Philippine Eagle Center Entry",  "Malagos",         "Calinan",    7.2389, 125.3712, "residential", False, 60,  "R05"),
    ("Bukidnon Junction",              "Mintal",          "Calinan",    7.1567, 125.4389, "residential", False, 130, "R09"),
    ("Don Bosco Technology Center",    "Obrero",          "Agdao",      7.0923, 125.6112, "school",      True,  510, "R12"),
    ("Tibungco Barangay Hall",         "Tibungco",        "Buhangin",   7.1634, 125.6712, "residential", False, 170, "R07"),
    ("Sasa Elementary School",         "Sasa",            "Buhangin",   7.1278, 125.6463, "school",      True,  390, "R12"),
    ("Bankerohan Fish Port",           "Bankerohan",      "Poblacion",  7.0609, 125.6085, "market",      False, 430, "R01"),
    # ── Extra stops to reach ~180 ─────────────────────────────────────────────
    ("Davao del Sur Capitol",          "Calinan",         "Calinan",    7.1951, 125.3968, "residential", True,  310, "R05"),
    ("Shrine Hills Chapel Stop",       "Matina",          "Talomo",     7.0531, 125.5912, "residential", False, 140, "R04"),
    ("McArthur Highway Junction",      "Maa",             "Talomo",     7.0061, 125.5671, "residential", False, 220, "R01"),
    ("Toril Police Station",           "Toril",           "Toril",      6.9819, 125.5391, "residential", False, 120, "R01"),
    ("Riverside Calinan Elementary",   "Riverside",       "Calinan",    7.1891, 125.4021, "school",      False, 190, "R05"),
    ("Bunawan District Hall",          "Bunawan",         "Bunawan",    7.1341, 125.6519, "residential", True,  230, "R10"),
    ("Panacan Health Center",          "Panacan",         "Paquibato",  7.1481, 125.6661, "hospital",    False, 150, "R10"),
    ("Matina Gym Stop",                "Matina",          "Talomo",     7.0612, 125.5971, "residential", False, 260, "R11"),
    ("Davao City Medical Center Annex","Bajada",          "Poblacion",  7.0861, 125.6151, "hospital",    True,  380, "R07"),
    ("Communal Barangay Hall",         "Communal",        "Buhangin",   7.1181, 125.6391, "residential", False, 170, "R02"),
    ("Lanang IT Park",                 "Lanang",          "Buhangin",   7.1211, 125.6541, "residential", True,  490, "R11"),
    ("Dumoy Elementary School",        "Dumoy",           "Talomo",     7.1301, 125.4819, "school",      False, 240, "R09"),
    ("Ecoland Drive Stop",             "Ecoland",         "Talomo",     7.0451, 125.5971, "residential", False, 310, "R02"),
    ("Agdao Sports Complex",           "Agdao",           "Agdao",      7.0841, 125.6251, "residential", True,  200, "R03"),
    ("Toril Elementary School",        "Toril",           "Toril",      6.9821, 125.5401, "school",      True,  350, "R01"),
    ("Buhangin Overpass",              "Buhangin Proper", "Buhangin",   7.1031, 125.6281, "residential", False, 270, "R06"),
    ("Calinan High School",            "Calinan",         "Calinan",    7.1941, 125.3981, "school",      True,  410, "R05"),
    ("Talomo River Bridge",            "Talomo",          "Talomo",     7.0148, 125.5751, "residential", False, 160, "R08"),
    ("Pampanga Street Stop",           "Poblacion",       "Poblacion",  7.0671, 125.6121, "residential", False, 190, "R06"),
]

ALL_STOPS_RAW = STOPS_MASTER + EXTRA_STOPS_BY_DISTRICT


def build_stops(raw: list[tuple]) -> list[dict]:
    stops = []
    for idx, row in enumerate(raw, start=1):
        (name, brgy, district, lat, lon, stype, shelter, boardings, route_id) = row
        # Add small random jitter to avoid perfect duplicates in GPS
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
    print(f"[produce_stops] Posting {len(stops)} stops to {ENDPOINT}")

    CHUNK = 50
    with httpx.Client(timeout=60) as client:
        for i in range(0, len(stops), CHUNK):
            batch = stops[i : i + CHUNK]
            resp = client.post(ENDPOINT, json=batch)
            resp.raise_for_status()
            print(f"[produce_stops]   chunk {i//CHUNK + 1}: {resp.json()}")

    print(f"[produce_stops] ✓ Done — {len(stops)} stops ingested")


if __name__ == "__main__":
    main()
