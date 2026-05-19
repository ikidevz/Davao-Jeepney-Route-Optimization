"""
app.py — Davao Jeepney Route Optimization · Streamlit Data Science App
-----------------------------------------------------------------------
Landing page + sidebar navigation.

Pages:
  01_cluster_explorer.py  — K-Means cluster profiles + scatter plots
  02_ab_test_results.py   — A/B test significance charts + satisfaction lift
  03_route_map.py         — Davao route map with stop markers (Folium)
"""

import os
import json
from pathlib import Path
from datetime import datetime

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
MANIFEST    = PARQUET_DIR / "manifest.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def last_refreshed() -> str:
    if MANIFEST.exists():
        try:
            with open(MANIFEST) as f:
                data = json.load(f)
            ts = datetime.fromisoformat(data["exported_at"].replace("Z", "+00:00"))
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
        """
    )

    st.markdown("---")
    st.caption(f"Data last refreshed: **{last_refreshed()}**")

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
st.subheader("Data Science Dashboard — Commuter Segmentation & Route Experiment")

st.markdown(
    """
    This app surfaces the outputs of a full data engineering + data science pipeline
    built on top of **500,000+ synthetic jeepney trip records** covering all 12 major
    Davao City routes, 182 barangays, and 5,000 passenger survey respondents.

    ---
    """
)

col1, col2, col3 = st.columns(3)

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

        *Interactive scatter plots, feature heatmaps, and cluster profile cards.*
        """
    )

with col2:
    st.markdown(
        """
        ### 🧪 A/B Test Results
        Analyze the **Matina → SM Lanang express route** experiment:
        - 8-week simulated trial on Underserved Riders
        - Two-sample t-test on satisfaction + travel time
        - Chi-square test on retention (would_use_again)
        - Cohen's d effect size + 95% confidence intervals

        *Statistical significance charts, lift metrics, and recommendation.*
        """
    )

with col3:
    st.markdown(
        """
        ### 🗺️ Route Map
        Interactive **Folium map** of Davao City's 12 jeepney routes:
        - Route corridors with color-coded overlays
        - Stop markers with ridership data
        - District boundaries and key landmarks
        - Filter by route, district, or stop type

        *Zoom into barangays, click stops for details.*
        """
    )

st.markdown("---")

# Pipeline status
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
}

status_rows = []
for fname, desc in files_to_check.items():
    path = PARQUET_DIR / fname
    exists = path.exists()
    size_kb = round(path.stat().st_size / 1024, 1) if exists else None
    status_rows.append({
        "File": fname,
        "Description": desc,
        "Status": "✅ Ready" if exists else "❌ Missing",
        "Size (KB)": size_kb or "—",
    })

import pandas as pd
st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

st.markdown(
    """
    ---
    **Stack:** FastAPI · MinIO · PostgreSQL · dbt · Apache Airflow · Streamlit · DuckDB  
    **Domain:** Davao City Public Transportation · Jeepney Route Optimization  
    **Data:** 500K synthetic trip records · 5,000 passenger surveys · 12 routes · 182 barangays
    """
)
