"""
app.py — Davao Jeepney Route Optimization · Streamlit Data Science App
-----------------------------------------------------------------------
Landing page + sidebar navigation.

Improvements:
  - Route ridership summary chart (mart_route_summary_recent.parquet)
  - District ridership sparklines (mart_district_ridership_recent.parquet)
  - Live KPI metrics with deltas vs. prior 7-day window
  - DuckDB-powered in-process analytics (no Postgres needed for dashboard)
  - Cleaner pipeline status with file sizes + row counts
  - "About this project" expander with full stack info
  - Refresh button to clear cache

Pages:
  01_cluster_explorer.py  — K-Means cluster profiles + scatter plots
  02_ab_test_results.py   — A/B test significance charts + satisfaction lift
  03_route_map.py         — Davao route map with stop markers (Folium)
  04_route_trends.py      — Route + district ridership trends (new)
"""

import os
import json
from pathlib import Path
from datetime import datetime

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Davao Jeepney Analytics",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PARQUET_DIR = Path(os.getenv("PARQUET_DIR", "/app/parquet"))
MANIFEST = PARQUET_DIR / "manifest.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def last_refreshed() -> str:
    if MANIFEST.exists():
        try:
            with open(MANIFEST) as f:
                data = json.load(f)
            ts = datetime.fromisoformat(
                data["exported_at"].replace("Z", "+00:00"))
            return ts.strftime("%d %b %Y %H:%M UTC")
        except Exception:
            pass
    return "unknown"


def parquet_ready() -> bool:
    required = [
        "passenger_features.parquet",
        "cluster_assignments.parquet",
        "ab_test_statistics.parquet",
        "mart_commuter_clusters.parquet",
        "mart_ab_test_results.parquet",
    ]
    return all((PARQUET_DIR / f).exists() for f in required)


@st.cache_data(ttl=300)
def load_route_summary() -> pd.DataFrame:
    path = PARQUET_DIR / "mart_route_summary_recent.parquet"
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()


@st.cache_data(ttl=300)
def load_district_ridership() -> pd.DataFrame:
    path = PARQUET_DIR / "mart_district_ridership_recent.parquet"
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()


@st.cache_data(ttl=300)
def load_clusters() -> pd.DataFrame:
    path = PARQUET_DIR / "mart_commuter_clusters.parquet"
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/"
        "Flag_of_Davao_City.svg/240px-Flag_of_Davao_City.svg.png",
        width=80,
    )
    st.markdown("## 🚌 Davao Jeepney\n### Route Optimization")
    st.markdown("---")

    st.markdown(
        """
        **Navigate using the pages below:**

        | Page | Description |
        |------|-------------|
        | 🔵 Cluster Explorer | K-Means passenger segments |
        | 🧪 A/B Test Results | Express route experiment |
        | 🗺️ Route Map | Davao jeepney route map |
        | 📈 Route Trends | Ridership & revenue trends |
        """
    )

    st.markdown("---")
    st.caption(f"Data last refreshed: **{last_refreshed()}**")

    if st.button("🔄 Refresh data cache"):
        st.cache_data.clear()
        st.rerun()

    if not parquet_ready():
        st.warning(
            "⚠️ Parquet files not found. "
            "Run the full pipeline first:\n\n"
            "```\npython science/feature_engineering.py\n"
            "python science/clustering.py\n"
            "python science/ab_testing.py\n"
            "python science/export_to_parquet.py\n```"
        )


# ---------------------------------------------------------------------------
# Landing page content
# ---------------------------------------------------------------------------
st.title("🚌 Davao City Jeepney Route Optimization")
st.subheader(
    "Data Science Dashboard — Commuter Segmentation & Route Experiment")

st.markdown(
    """
    This app surfaces the outputs of a full data engineering + data science pipeline
    built on top of **1,100,000+ synthetic jeepney trip records** covering all 12 major
    Davao City routes, 182 barangays, and 5,000 passenger survey respondents.

    ---
    """
)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(
        """
        ### 🔵 Cluster Explorer
        Explore the **5 commuter segments** identified by K-Means clustering:
        - Student Commuters
        - Market Workers
        - CBD Workers
        - Underserved Riders ← A/B test target
        - Occasional Riders

        *Scatter plots, feature heatmaps, profile cards, elbow/silhouette diagnostics.*
        """
    )

with col2:
    st.markdown(
        """
        ### 🧪 A/B Test Results
        Analyze the **Matina → SM Lanang express route** experiment:
        - 8-week simulated trial on Underserved Riders
        - Two-sample Welch's t-test on satisfaction + travel time
        - Chi-square test on retention (would_use_again)
        - Cohen's d effect size + 95% confidence intervals

        *Significance charts, lift metrics, and recommendation verdict.*
        """
    )

with col3:
    st.markdown(
        """
        ### 🗺️ Route Map
        Interactive **Folium map** of Davao City's 12 jeepney routes:
        - Route corridors with color-coded overlays
        - Stop markers with ridership data + popups
        - District satisfaction heatmap circles
        - Filter by route, district, or stop type

        *Zoom into barangays, click stops for details.*
        """
    )

with col4:
    st.markdown(
        """
        ### 📈 Route Trends *(new)*
        Temporal ridership & revenue analytics:
        - Daily passenger volume by route (last 30 days)
        - Revenue trends and fare averages
        - District-level ridership breakdown
        - Top routes by boardings and load factor

        *Powered by DuckDB in-process analytics.*
        """
    )

st.markdown("---")

# ---------------------------------------------------------------------------
# Live KPI strip (from mart data)
# ---------------------------------------------------------------------------
clusters_df = load_clusters()
route_df = load_route_summary()
district_df = load_district_ridership()

if not clusters_df.empty:
    st.markdown("### 📊 Live Data Snapshot")
    k1, k2, k3, k4, k5 = st.columns(5)

    total_pax = len(clusters_df)
    avg_sat = clusters_df["satisfaction_score"].mean()
    avg_fare = clusters_df["avg_fare_paid_php"].mean()
    avg_wait = clusters_df["wait_time_min"].mean()
    underserved = (clusters_df["cluster_id"] == 3).sum()

    k1.metric("Total Passengers", f"{total_pax:,}")
    k2.metric("Avg Satisfaction", f"{avg_sat:.2f} / 5")
    k3.metric("Avg Fare (₱)", f"₱{avg_fare:.2f}")
    k4.metric("Avg Wait Time", f"{avg_wait:.1f} min")
    k5.metric("Underserved Riders", f"{underserved:,}",
              delta=f"{100*underserved/total_pax:.1f}% of total",
              delta_color="inverse")

    st.markdown("---")

# ---------------------------------------------------------------------------
# Route summary chart (if available)
# ---------------------------------------------------------------------------
if not route_df.empty:
    st.markdown("### 🚌 Recent Route Performance (Last 30 Days)")
    rc1, rc2 = st.columns(2)

    with rc1:
        # Total boardings by route
        route_agg = (
            route_df.groupby("route_id")["total_passengers"]
            .sum()
            .reset_index()
            .sort_values("total_passengers", ascending=False)
            .head(12)
        )
        fig_route = px.bar(
            route_agg,
            x="route_id",
            y="total_passengers",
            title="Total Boardings by Route",
            labels={"route_id": "Route",
                    "total_passengers": "Total Passengers"},
            color="total_passengers",
            color_continuous_scale="Blues",
        )
        fig_route.update_layout(
            height=350, showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_route, width='content')

    with rc2:
        # Daily trend (top 5 routes)
        if "trip_date" in route_df.columns:
            top5_routes = (
                route_df.groupby("route_id")["total_passengers"]
                .sum()
                .nlargest(5)
                .index.tolist()
            )
            trend_df = route_df[route_df["route_id"].isin(top5_routes)].copy()
            trend_df["trip_date"] = pd.to_datetime(trend_df["trip_date"])
            fig_trend = px.line(
                trend_df,
                x="trip_date",
                y="total_passengers",
                color="route_id",
                title="Daily Ridership Trend (Top 5 Routes)",
                labels={"trip_date": "Date",
                        "total_passengers": "Passengers", "route_id": "Route"},
            )
            fig_trend.update_layout(height=350)
            st.plotly_chart(fig_trend, width='content')

    st.markdown("---")

# ---------------------------------------------------------------------------
# District ridership (if available)
# ---------------------------------------------------------------------------

if not district_df.empty and "district" in district_df.columns:
    st.markdown("### 🏘️ District Ridership Breakdown")
    dist_agg = (
        district_df.groupby("district")["total_boardings"]
        .sum()
        .reset_index()
        .sort_values("total_boardings", ascending=True)
    )
    fig_dist = px.bar(
        dist_agg,
        x="total_boardings",
        y="district",
        orientation="h",
        title="Total Passengers by District (Last 30 Days)",
        labels={"total_boardings": "Total Passengers", "district": "District"},
        color="total_boardings",
        color_continuous_scale="Teal",
    )
    fig_dist.update_layout(height=400, coloraxis_showscale=False)
    st.plotly_chart(fig_dist, width='stretch')
    st.markdown("---")

# ---------------------------------------------------------------------------
# Pipeline status
# ---------------------------------------------------------------------------
st.markdown("### 📦 Pipeline Status")

files_to_check = {
    "passenger_features.parquet":         "Feature matrix (clustering input)",
    "cluster_assignments.parquet":        "Cluster labels (K-Means output)",
    "elbow_scores.parquet":               "Elbow diagnostics",
    "silhouette_scores.parquet":          "Silhouette diagnostics",
    "ab_test_statistics.parquet":         "A/B test statistics",
    "mart_commuter_clusters.parquet":     "Commuter cluster mart",
    "mart_ab_test_results.parquet":       "A/B test results mart",
    "mart_route_summary_recent.parquet":  "Route summary (last 30 days)",
    "mart_district_ridership_recent.parquet": "District ridership (last 30 days)",
}

status_rows = []
for fname, desc in files_to_check.items():
    path = PARQUET_DIR / fname
    exists = path.exists()
    size_kb = round(path.stat().st_size / 1024, 1) if exists else None
    row_count = None
    if exists:
        try:
            row_count = duckdb.query(
                f"SELECT COUNT(*) AS n FROM read_parquet('{path}')"
            ).fetchone()[0]
        except Exception:
            pass
    status_rows.append({
        "File": fname,
        "Description": desc,
        "Status": "✅ Ready" if exists else "❌ Missing",
        "Size (KB)": size_kb or "—",
        "Rows": f"{row_count:,}" if row_count is not None else "—",
    })

st.dataframe(pd.DataFrame(status_rows), width='stretch', hide_index=True)

# ---------------------------------------------------------------------------
# About the project
# ---------------------------------------------------------------------------
with st.expander("ℹ️ About this project"):
    st.markdown(
        """
        **Davao City Jeepney Route Optimization** is a full data engineering + data science
        portfolio project demonstrating an end-to-end analytics pipeline.

        | Layer | Tool |
        |-------|------|
        | Object storage (Bronze) | MinIO |
        | Warehouse (Silver / Gold) | PostgreSQL 15 |
        | Ingestion API | FastAPI + Pydantic v2 |
        | Transformation | dbt-core 1.7 |
        | Orchestration | Apache Airflow 3.2.1 |
        | BI dashboards | Apache Superset 3.0 |
        | DS app | Streamlit |
        | ML | scikit-learn (K-Means, DBSCAN) + scipy |
        | Query engine | DuckDB |

        **Data:** 1.1M+ synthetic trip records · 5,000 passenger surveys · 12 routes · 182 barangays  
        **Domain:** Davao City Public Transportation · Jeepney Route Optimization
        """
    )
