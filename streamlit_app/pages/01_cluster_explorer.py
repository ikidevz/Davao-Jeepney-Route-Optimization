"""
01_cluster_explorer.py
-----------------------
Cluster Explorer page — K-Means passenger segmentation results.

Sections:
  1. Cluster overview (distribution pie + bar)
  2. Feature heatmap (avg per cluster vs overall)
  3. Interactive scatter plot (2D projection of feature space)
  4. Per-cluster profile cards
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Cluster Explorer · Davao Jeepney", page_icon="🔵", layout="wide")

PARQUET_DIR = Path(os.getenv("PARQUET_DIR", "/app/parquet"))

# ---------------------------------------------------------------------------
# Cluster metadata
# ---------------------------------------------------------------------------
CLUSTER_META = {
    0: {"label": "Student Commuters",  "emoji": "🎓", "color": "#3B82F6",
        "desc": "High-frequency, low-fare riders heading to schools in Matina and Buhangin. "
                "Very price-sensitive. Peak demand during school hours."},
    1: {"label": "Market Workers",     "emoji": "🛒", "color": "#10B981",
        "desc": "Early morning commuters from Toril and Calinan travelling to Bankerohan Market. "
                "AM-peak dominated. Multiple routes used."},
    2: {"label": "CBD Workers",        "emoji": "💼", "color": "#8B5CF6",
        "desc": "Daily commuters to Poblacion, Bajada, and Lanang business districts. "
                "Higher willingness to pay. Low transfer tolerance."},
    3: {"label": "Underserved Riders", "emoji": "⚠️", "color": "#EF4444",
        "desc": "Passengers requiring 2+ transfers, long waits, and reporting lowest satisfaction. "
                "Primary target of the Matina→SM Lanang express route A/B experiment."},
    4: {"label": "Occasional Riders",  "emoji": "🛍️", "color": "#F59E0B",
        "desc": "Low-frequency users making mall, hospital, or errand trips. "
                "Not daily commuters. Trip purpose varies."},
}

FEATURE_DISPLAY = {
    "trips_per_week":    "Trips / Week",
    "avg_fare_paid_php": "Avg Fare (₱)",
    "transfers_required":"Transfers",
    "wait_time_min":     "Wait Time (min)",
    "travel_time_min":   "Travel Time (min)",
    "satisfaction_score":"Satisfaction (1–5)",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_clusters() -> pd.DataFrame:
    path = PARQUET_DIR / "mart_commuter_clusters.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=300)
def load_features() -> pd.DataFrame:
    path = PARQUET_DIR / "passenger_features.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=300)
def load_elbow() -> pd.DataFrame:
    path = PARQUET_DIR / "elbow_scores.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=300)
def load_silhouette() -> pd.DataFrame:
    path = PARQUET_DIR / "silhouette_scores.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.title("🔵 Commuter Cluster Explorer")
st.caption("K-Means segmentation of 5,000 Davao City jeepney passengers")

df = load_clusters()

if df.empty:
    st.error(
        "Cluster data not found. Run `science/clustering.py` then `science/export_to_parquet.py` first."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    selected_clusters = st.multiselect(
        "Show clusters:",
        options=sorted(df["cluster_id"].unique()),
        default=sorted(df["cluster_id"].unique()),
        format_func=lambda x: f"{CLUSTER_META[x]['emoji']} {CLUSTER_META[x]['label']}",
    )
    selected_districts = st.multiselect(
        "Origin district:",
        options=sorted(df["origin_district"].dropna().unique()),
        default=[],
        placeholder="All districts",
    )
    selected_purposes = st.multiselect(
        "Trip purpose:",
        options=sorted(df["trip_purpose"].dropna().unique()),
        default=[],
        placeholder="All purposes",
    )

mask = df["cluster_id"].isin(selected_clusters)
if selected_districts:
    mask &= df["origin_district"].isin(selected_districts)
if selected_purposes:
    mask &= df["trip_purpose"].isin(selected_purposes)

filtered = df[mask].copy()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Passengers", f"{len(filtered):,}")
col2.metric("Clusters Shown", len(filtered["cluster_id"].unique()))
col3.metric("Avg Satisfaction", f"{filtered['satisfaction_score'].mean():.2f} / 5")
col4.metric("Avg Transfers", f"{filtered['transfers_required'].mean():.2f}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Distribution: pie + bar
# ---------------------------------------------------------------------------
st.subheader("Cluster Distribution")
dist_col1, dist_col2 = st.columns(2)

cluster_counts = (
    filtered.groupby(["cluster_id", "cluster_label"])
    .size()
    .reset_index(name="count")
)
cluster_counts["color"] = cluster_counts["cluster_id"].map(lambda x: CLUSTER_META[x]["color"])
cluster_counts["emoji_label"] = cluster_counts["cluster_id"].map(
    lambda x: f"{CLUSTER_META[x]['emoji']} {CLUSTER_META[x]['label']}"
)

with dist_col1:
    fig_pie = px.pie(
        cluster_counts,
        names="emoji_label",
        values="count",
        color="emoji_label",
        color_discrete_map={
            f"{CLUSTER_META[c]['emoji']} {CLUSTER_META[c]['label']}": CLUSTER_META[c]["color"]
            for c in CLUSTER_META
        },
        title="Passenger Share by Cluster",
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(showlegend=False, height=380)
    st.plotly_chart(fig_pie, use_container_width=True)

with dist_col2:
    fig_bar = px.bar(
        cluster_counts.sort_values("cluster_id"),
        x="emoji_label",
        y="count",
        color="emoji_label",
        color_discrete_map={
            f"{CLUSTER_META[c]['emoji']} {CLUSTER_META[c]['label']}": CLUSTER_META[c]["color"]
            for c in CLUSTER_META
        },
        title="Passenger Count per Cluster",
        labels={"emoji_label": "Cluster", "count": "Passengers"},
    )
    fig_bar.update_layout(showlegend=False, height=380, xaxis_tickangle=-20)
    st.plotly_chart(fig_bar, use_container_width=True)

# ---------------------------------------------------------------------------
# Feature heatmap
# ---------------------------------------------------------------------------
st.subheader("Cluster Feature Profiles (Avg vs Overall)")

feature_cols = list(FEATURE_DISPLAY.keys())
agg = filtered.groupby("cluster_id")[feature_cols].mean()
overall = filtered[feature_cols].mean()

# Normalize: % deviation from overall mean; fill inf/nan (zero-mean features) with 0
norm = ((agg - overall) / overall.replace(0, np.nan)).fillna(0)
norm.columns = list(FEATURE_DISPLAY.values())
norm.index = [f"{CLUSTER_META[c]['emoji']} {CLUSTER_META[c]['label']}" for c in norm.index]

fig_heat = px.imshow(
    norm,
    color_continuous_scale="RdBu_r",
    color_continuous_midpoint=0,
    title="Feature Deviation from Overall Mean (red = above avg, blue = below avg)",
    aspect="auto",
    text_auto=".2f",
)
fig_heat.update_layout(height=320, coloraxis_colorbar_title="Δ from mean")
st.plotly_chart(fig_heat, use_container_width=True)

# ---------------------------------------------------------------------------
# Scatter plot (2 feature axes)
# ---------------------------------------------------------------------------
st.subheader("Interactive Scatter Plot")
sc_col1, sc_col2 = st.columns(2)
with sc_col1:
    x_axis = st.selectbox("X axis:", list(FEATURE_DISPLAY.keys()),
                          index=0,
                          format_func=lambda c: FEATURE_DISPLAY[c])
with sc_col2:
    y_axis = st.selectbox("Y axis:", list(FEATURE_DISPLAY.keys()),
                          index=3,
                          format_func=lambda c: FEATURE_DISPLAY[c])

filtered["cluster_display"] = filtered["cluster_id"].map(
    lambda x: f"{CLUSTER_META[x]['emoji']} {CLUSTER_META[x]['label']}"
)

if filtered.empty:
    st.info("No passengers match the current filter selection. Adjust the sidebar filters.")
else:
    fig_scatter = px.scatter(
        filtered.sample(min(2000, len(filtered)), random_state=42),
        x=x_axis,
        y=y_axis,
        color="cluster_display",
        color_discrete_map={
            f"{CLUSTER_META[c]['emoji']} {CLUSTER_META[c]['label']}": CLUSTER_META[c]["color"]
            for c in CLUSTER_META
        },
        hover_data=["passenger_id", "origin_district", "satisfaction_score"],
        labels={
            x_axis: FEATURE_DISPLAY[x_axis],
            y_axis: FEATURE_DISPLAY[y_axis],
            "cluster_display": "Cluster",
        },
        title=f"{FEATURE_DISPLAY[x_axis]} vs {FEATURE_DISPLAY[y_axis]}",
        opacity=0.65,
    )
    fig_scatter.update_layout(height=450, legend_title_text="Cluster")
    st.plotly_chart(fig_scatter, use_container_width=True)

# ---------------------------------------------------------------------------
# Cluster profile cards
# ---------------------------------------------------------------------------
st.subheader("Cluster Profile Cards")

for cluster_id in sorted(CLUSTER_META.keys()):
    if cluster_id not in selected_clusters:
        continue

    meta = CLUSTER_META[cluster_id]
    cluster_df = filtered[filtered["cluster_id"] == cluster_id]

    if cluster_df.empty:
        continue

    with st.expander(
        f"{meta['emoji']} Cluster {cluster_id} — {meta['label']}  "
        f"({len(cluster_df):,} passengers, {100*len(cluster_df)/len(filtered):.1f}%)",
        expanded=(cluster_id == 3),
    ):
        c1, c2, c3 = st.columns(3)
        c1.metric("Avg Satisfaction", f"{cluster_df['satisfaction_score'].mean():.2f}")
        c2.metric("Avg Transfers",    f"{cluster_df['transfers_required'].mean():.2f}")
        c3.metric("Avg Wait (min)",   f"{cluster_df['wait_time_min'].mean():.1f}")

        d1, d2, d3 = st.columns(3)
        d1.metric("Trips / Week",      f"{cluster_df['trips_per_week'].mean():.1f}")
        d2.metric("Avg Fare (₱)",      f"₱{cluster_df['avg_fare_paid_php'].mean():.2f}")
        d3.metric("Avg Travel (min)",  f"{cluster_df['travel_time_min'].mean():.1f}")

        st.markdown(f"**Description:** {meta['desc']}")

        if cluster_id == 3:
            st.info(
                "⚠️ **A/B Test Target** — These passengers are enrolled in the "
                "Matina → SM Lanang express route experiment. "
                "See the A/B Test Results page for significance analysis."
            )

        top_districts = (
            cluster_df["origin_district"]
            .value_counts()
            .head(5)
            .reset_index()
            .rename(columns={"origin_district": "District", "count": "Passengers"})
        )
        st.markdown("**Top Origin Districts:**")
        st.dataframe(top_districts, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Elbow & Silhouette diagnostics
# ---------------------------------------------------------------------------
with st.expander("📊 Model Diagnostics — Elbow & Silhouette Scores"):
    el_col, sil_col = st.columns(2)

    elbow_df = load_elbow()
    silhouette_df = load_silhouette()

    if not elbow_df.empty:
        with el_col:
            fig_elbow = px.line(elbow_df, x="k", y="wss", markers=True,
                                title="Elbow Method — Within-Cluster Sum of Squares",
                                labels={"k": "Number of Clusters (K)", "wss": "WSS"})
            fig_elbow.add_vline(x=5, line_dash="dash", line_color="red",
                                annotation_text="K=5 selected")
            st.plotly_chart(fig_elbow, use_container_width=True)

    if not silhouette_df.empty:
        with sil_col:
            fig_sil = px.line(silhouette_df, x="k", y="silhouette_score", markers=True,
                              title="Silhouette Score by K",
                              labels={"k": "K", "silhouette_score": "Silhouette Score"})
            fig_sil.add_vline(x=5, line_dash="dash", line_color="red",
                              annotation_text="K=5 selected")
            st.plotly_chart(fig_sil, use_container_width=True)
