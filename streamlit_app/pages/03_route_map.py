"""
03_route_map.py
---------------
Davao City Jeepney Route Map page — interactive Folium map.

Features:
  - 12 jeepney route corridors (color-coded polylines)
  - Stop markers with ridership + type info (popup on click)
  - Cluster distribution overlay by district (choropleth-style circles)
  - Sidebar filters: route, district, stop type
  - A/B experiment route highlighted (Matina → SM Lanang)
"""

import os
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="Route Map · Davao Jeepney", page_icon="🗺️", layout="wide")

PARQUET_DIR = Path(os.getenv("PARQUET_DIR", "/app/parquet"))

# ---------------------------------------------------------------------------
# Davao City map data (static reference — real coordinates)
# ---------------------------------------------------------------------------
DAVAO_CENTER = [7.0709, 125.6087]

ROUTES = [
    {"route_id": "R01", "name": "Bankerohan–Toril",       "color": "#3B82F6",
     "coords": [[7.0709, 125.6087], [7.0500, 125.5900], [7.0200, 125.5700], [6.9900, 125.5500]]},
    {"route_id": "R02", "name": "Ecoland–SM City",         "color": "#10B981",
     "coords": [[7.0600, 125.5950], [7.0709, 125.6087], [7.0850, 125.6200], [7.0920, 125.6120]]},
    {"route_id": "R03", "name": "Agdao Loop",              "color": "#F59E0B",
     "coords": [[7.0709, 125.6087], [7.0900, 125.6300], [7.1000, 125.6200], [7.0800, 125.6050]]},
    {"route_id": "R04", "name": "Calinan–Bankerohan",     "color": "#EF4444",
     "coords": [[7.1800, 125.4700], [7.1500, 125.5200], [7.1200, 125.5700], [7.0709, 125.6087]]},
    {"route_id": "R05", "name": "Buhangin–Lanang",        "color": "#8B5CF6",
     "coords": [[7.1100, 125.6300], [7.1000, 125.6200], [7.0800, 125.6150], [7.0700, 125.6180]]},
    {"route_id": "R06", "name": "Matina–Ulas",            "color": "#EC4899",
     "coords": [[7.0500, 125.5950], [7.0600, 125.6000], [7.0650, 125.6050], [7.0700, 125.6200]]},
    {"route_id": "R07", "name": "Talomo–Davao Proper",    "color": "#06B6D4",
     "coords": [[7.0100, 125.5600], [7.0300, 125.5800], [7.0500, 125.5950], [7.0709, 125.6087]]},
    {"route_id": "R08", "name": "Mintal–Bankerohan",      "color": "#84CC16",
     "coords": [[7.1400, 125.5100], [7.1100, 125.5400], [7.0900, 125.5700], [7.0709, 125.6087]]},
    {"route_id": "R09", "name": "Panacan–Bankerohan",     "color": "#F97316",
     "coords": [[7.1300, 125.6500], [7.1100, 125.6300], [7.0900, 125.6150], [7.0709, 125.6087]]},
    {"route_id": "R10", "name": "Toril–Sta. Ana Wharf",  "color": "#64748B",
     "coords": [[6.9900, 125.5500], [7.0100, 125.5600], [7.0400, 125.5850], [7.0550, 125.6050]]},
    {"route_id": "R11", "name": "Sasa–Bajada",            "color": "#A78BFA",
     "coords": [[7.1050, 125.6400], [7.0900, 125.6280], [7.0750, 125.6150], [7.0650, 125.6050]]},
    {"route_id": "R12", "name": "Matina–SM Lanang Express","color": "#DC2626",
     "coords": [[7.0500, 125.5950], [7.0600, 125.6050], [7.0750, 125.6100], [7.0800, 125.6150],
                [7.0850, 125.6200], [7.0920, 125.6120]],
     "is_ab_route": True},
]

STOPS = [
    # Terminals and major landmarks (real Davao locations)
    {"stop_id": "S001", "name": "Bankerohan Market Terminal", "lat": 7.0709, "lng": 125.6087,
     "type": "terminal", "district": "Poblacion", "avg_boardings": 2800, "routes": "R01,R03,R04,R08"},
    {"stop_id": "S002", "name": "Toril Terminal",             "lat": 6.9900, "lng": 125.5500,
     "type": "terminal", "district": "Toril", "avg_boardings": 1200, "routes": "R01,R10"},
    {"stop_id": "S003", "name": "SM City Davao",              "lat": 7.0920, "lng": 125.6120,
     "type": "mall",     "district": "Buhangin", "avg_boardings": 3200, "routes": "R02,R05"},
    {"stop_id": "S004", "name": "Ecoland Terminal",           "lat": 7.0600, "lng": 125.5950,
     "type": "terminal", "district": "Talomo", "avg_boardings": 1800, "routes": "R02,R06,R07"},
    {"stop_id": "S005", "name": "Agdao Public Market",        "lat": 7.0900, "lng": 125.6300,
     "type": "market",   "district": "Agdao", "avg_boardings": 1500, "routes": "R03,R09"},
    {"stop_id": "S006", "name": "Matina Crossing",            "lat": 7.0500, "lng": 125.5950,
     "type": "residential","district": "Talomo", "avg_boardings": 900, "routes": "R06,R12"},
    {"stop_id": "S007", "name": "Lanang Business Park",       "lat": 7.0700, "lng": 125.6180,
     "type": "mall",     "district": "Buhangin", "avg_boardings": 2100, "routes": "R05"},
    {"stop_id": "S008", "name": "Davao Medical Center",       "lat": 7.0650, "lng": 125.6020,
     "type": "hospital", "district": "Poblacion", "avg_boardings": 750, "routes": "R06,R07"},
    {"stop_id": "S009", "name": "Ateneo de Davao University", "lat": 7.0720, "lng": 125.6120,
     "type": "school",   "district": "Poblacion", "avg_boardings": 1100, "routes": "R03"},
    {"stop_id": "S010", "name": "SM Lanang Premier",          "lat": 7.0850, "lng": 125.6200,
     "type": "mall",     "district": "Lanang", "avg_boardings": 2900, "routes": "R05,R12"},
    {"stop_id": "S011", "name": "Calinan Terminal",           "lat": 7.1800, "lng": 125.4700,
     "type": "terminal", "district": "Calinan", "avg_boardings": 680, "routes": "R04"},
    {"stop_id": "S012", "name": "Buhangin Crossing",          "lat": 7.1100, "lng": 125.6300,
     "type": "residential","district": "Buhangin", "avg_boardings": 820, "routes": "R05,R09"},
    {"stop_id": "S013", "name": "Panacan Terminal",           "lat": 7.1300, "lng": 125.6500,
     "type": "terminal", "district": "Panacan", "avg_boardings": 590, "routes": "R09"},
    {"stop_id": "S014", "name": "Bajada Terminal",            "lat": 7.0750, "lng": 125.6150,
     "type": "terminal", "district": "Poblacion", "avg_boardings": 1350, "routes": "R11"},
    {"stop_id": "S015", "name": "Sasa Terminal",              "lat": 7.1050, "lng": 125.6400,
     "type": "terminal", "district": "Sasa", "avg_boardings": 720, "routes": "R11"},
]

STOP_TYPE_ICONS = {
    "terminal":    ("transfer",    "darkblue"),
    "market":      ("shopping-cart","orange"),
    "school":      ("education",   "green"),
    "hospital":    ("plus-sign",   "red"),
    "mall":        ("tag",         "purple"),
    "residential": ("home",        "gray"),
}

DISTRICTS = sorted(set(s["district"] for s in STOPS))
STOP_TYPES = sorted(set(s["type"] for s in STOPS))
ALL_ROUTES = {r["route_id"]: r["name"] for r in ROUTES}


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.title("🗺️ Davao City Jeepney Route Map")
st.caption("12 major routes · Key terminals and landmarks · A/B experiment corridor highlighted")

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Map Filters")

    selected_routes = st.multiselect(
        "Show routes:",
        options=[r["route_id"] for r in ROUTES],
        default=[r["route_id"] for r in ROUTES],
        format_func=lambda rid: f"{rid} — {ALL_ROUTES[rid]}",
    )

    selected_stop_types = st.multiselect(
        "Stop types:",
        options=STOP_TYPES,
        default=STOP_TYPES,
    )

    selected_districts = st.multiselect(
        "Districts:",
        options=DISTRICTS,
        default=[],
        placeholder="All districts",
    )

    show_ab_corridor = st.toggle("Highlight A/B experiment corridor", value=True)
    show_cluster_heatmap = st.toggle("Show district satisfaction circles", value=True)

    st.markdown("---")
    st.markdown(
        """
        **Legend**
        - 🔴 A/B experiment route (R12)
        - 🟦 Other jeepney routes
        - 🚌 Terminal
        - 🛒 Market
        - 🎓 School
        - ➕ Hospital
        - 🛍️ Mall
        - 🏠 Residential
        """
    )


# ---------------------------------------------------------------------------
# Build Folium map
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_cluster_data() -> pd.DataFrame:
    path = PARQUET_DIR / "mart_commuter_clusters.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


cluster_df = load_cluster_data()

m = folium.Map(
    location=DAVAO_CENTER,
    zoom_start=12,
    tiles="CartoDB positron",
)

# District satisfaction circles (if data available)
if show_cluster_heatmap and not cluster_df.empty:
    district_stats = (
        cluster_df.groupby("origin_district")["satisfaction_score"]
        .mean()
        .reset_index()
        .rename(columns={"satisfaction_score": "avg_satisfaction"})
    )

    # Approximate district centroids
    DISTRICT_CENTROIDS = {
        "Poblacion":  [7.0709, 125.6087],
        "Buhangin":   [7.1050, 125.6250],
        "Agdao":      [7.0900, 125.6300],
        "Talomo":     [7.0500, 125.5900],
        "Toril":      [6.9900, 125.5500],
        "Calinan":    [7.1800, 125.4700],
        "Baguio":     [7.1300, 125.5500],
        "Lanang":     [7.0850, 125.6200],
        "Panacan":    [7.1300, 125.6500],
        "Sasa":       [7.1050, 125.6400],
        "Mintal":     [7.1400, 125.5100],
    }

    for _, row in district_stats.iterrows():
        district = row["origin_district"]
        sat = row["avg_satisfaction"]
        if district not in DISTRICT_CENTROIDS:
            continue
        # Color: red = low sat, green = high sat
        red   = int(255 * (1 - (sat - 1) / 4))
        green = int(255 * ((sat - 1) / 4))
        color_hex = f"#{red:02x}{green:02x}40"

        folium.Circle(
            location=DISTRICT_CENTROIDS[district],
            radius=600,
            color=color_hex,
            fill=True,
            fill_color=color_hex,
            fill_opacity=0.35,
            tooltip=f"{district}: Avg Satisfaction {sat:.2f} / 5",
        ).add_to(m)

# Draw routes
for route in ROUTES:
    if route["route_id"] not in selected_routes:
        continue

    is_ab = route.get("is_ab_route", False)
    if is_ab and not show_ab_corridor:
        continue

    weight    = 6 if is_ab else 4
    dash_arr  = None if is_ab else "10"
    tooltip   = (
        f"🔴 A/B EXPERIMENT ROUTE — {route['name']} (R12)\nMatina → SM Lanang Express"
        if is_ab
        else f"{route['route_id']} — {route['name']}"
    )

    folium.PolyLine(
        locations=route["coords"],
        color=route["color"],
        weight=weight,
        dash_array=dash_arr,
        tooltip=tooltip,
        opacity=0.85 if is_ab else 0.70,
    ).add_to(m)

    # Route label marker at midpoint
    mid_idx = len(route["coords"]) // 2
    mid = route["coords"][mid_idx]
    folium.Marker(
        location=mid,
        icon=folium.DivIcon(
            html=f'<div style="font-size:10px;color:{route["color"]};'
                 f'font-weight:bold;white-space:nowrap;">{route["route_id"]}</div>',
            icon_size=(40, 20),
            icon_anchor=(20, 10),
        ),
    ).add_to(m)

# Draw stop markers
for stop in STOPS:
    if stop["type"] not in selected_stop_types:
        continue
    if selected_districts and stop["district"] not in selected_districts:
        continue

    icon_name, icon_color = STOP_TYPE_ICONS.get(stop["type"], ("info-sign", "blue"))

    popup_html = f"""
        <b>{stop['name']}</b><br>
        Type: {stop['type'].title()}<br>
        District: {stop['district']}<br>
        Avg daily boardings: <b>{stop['avg_boardings']:,}</b><br>
        Routes: {stop['routes']}
    """

    folium.Marker(
        location=[stop["lat"], stop["lng"]],
        popup=folium.Popup(popup_html, max_width=220),
        tooltip=f"{stop['name']} ({stop['avg_boardings']:,} boardings/day)",
        icon=folium.Icon(color=icon_color, icon=icon_name, prefix="glyphicon"),
    ).add_to(m)

# A/B experiment: special marker for proposed express route endpoints
if show_ab_corridor:
    folium.Marker(
        location=[7.0500, 125.5950],
        popup="<b>Matina Crossing</b><br>Express Route Origin (A/B Experiment)",
        tooltip="🧪 Express Route: Matina START",
        icon=folium.Icon(color="red", icon="flag", prefix="glyphicon"),
    ).add_to(m)
    folium.Marker(
        location=[7.0920, 125.6120],
        popup="<b>SM Lanang Premier</b><br>Express Route Destination (A/B Experiment)",
        tooltip="🧪 Express Route: SM Lanang END",
        icon=folium.Icon(color="red", icon="flag", prefix="glyphicon"),
    ).add_to(m)

# ---------------------------------------------------------------------------
# Render map
# ---------------------------------------------------------------------------
map_data = st_folium(m, width=None, height=600, returned_objects=[])

# ---------------------------------------------------------------------------
# Stop reference table
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Stop Reference Table")

filtered_stops = [
    s for s in STOPS
    if s["type"] in selected_stop_types
    and (not selected_districts or s["district"] in selected_districts)
]

stop_df = pd.DataFrame(filtered_stops)[
    ["stop_id", "name", "district", "type", "avg_boardings", "routes"]
].rename(columns={
    "stop_id":       "Stop ID",
    "name":          "Stop Name",
    "district":      "District",
    "type":          "Type",
    "avg_boardings": "Avg Daily Boardings",
    "routes":        "Routes Served",
}).sort_values("Avg Daily Boardings", ascending=False)

st.dataframe(stop_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Route legend table
# ---------------------------------------------------------------------------
with st.expander("📋 Full Route List"):
    route_df = pd.DataFrame([
        {
            "Route ID": r["route_id"],
            "Name":     r["name"],
            "A/B Route": "🔴 Yes" if r.get("is_ab_route") else "No",
        }
        for r in ROUTES
        if r["route_id"] in selected_routes
    ])
    st.dataframe(route_df, use_container_width=True, hide_index=True)
