"""
01_cluster_explorer.py
-----------------------
Cluster Explorer page — K-Means passenger segmentation results.
"""

import io
import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Cluster Explorer · Davao Jeepney",
                   page_icon="🔵", layout="wide")

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
    "transfers_required": "Transfers",
    "wait_time_min":     "Wait Time (min)",
    "travel_time_min":   "Travel Time (min)",
    "satisfaction_score": "Satisfaction (1–5)",
}


# ---------------------------------------------------------------------------
# Data loading (DuckDB)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_clusters() -> pd.DataFrame:
    path = PARQUET_DIR / "mart_commuter_clusters.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()
    # Guard: exclude DBSCAN noise if present
    return df[df["cluster_id"] >= 0].copy()


@st.cache_data(ttl=300)
def load_elbow() -> pd.DataFrame:
    path = PARQUET_DIR / "elbow_scores.parquet"
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()


@st.cache_data(ttl=300)
def load_silhouette() -> pd.DataFrame:
    path = PARQUET_DIR / "silhouette_scores.parquet"
    if not path.exists():
        return pd.DataFrame()
    return duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()


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

    # Show cluster badges with counts
    cluster_counts_all = df["cluster_id"].value_counts().to_dict()
    selected_clusters = st.multiselect(
        "Show clusters:",
        options=sorted(df["cluster_id"].unique()),
        default=sorted(df["cluster_id"].unique()),
        format_func=lambda x: (
            f"{CLUSTER_META[x]['emoji']} {CLUSTER_META[x]['label']} "
            f"({cluster_counts_all.get(x, 0):,})"
        ),
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
    selected_income = st.multiselect(
        "Income bracket:",
        options=sorted(df["income_bracket"].dropna().unique()),
        default=[],
        placeholder="All brackets",
    )

    st.markdown("---")
    # CSV export
    mask_all = df["cluster_id"].isin(selected_clusters)
    if selected_districts:
        mask_all &= df["origin_district"].isin(selected_districts)
    if selected_purposes:
        mask_all &= df["trip_purpose"].isin(selected_purposes)
    if selected_income:
        mask_all &= df["income_bracket"].isin(selected_income)

    export_df = df[mask_all]
    csv_buf = io.BytesIO()
    export_df.to_csv(csv_buf, index=False)
    st.download_button(
        "📥 Export filtered data (CSV)",
        data=csv_buf.getvalue(),
        file_name="cluster_data.csv",
        mime="text/csv",
    )

mask = mask_all
filtered = export_df.copy()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Passengers", f"{len(filtered):,}")
col2.metric("Clusters Shown", len(filtered["cluster_id"].unique()))
col3.metric("Avg Satisfaction",
            f"{filtered['satisfaction_score'].mean():.2f} / 5")
col4.metric("Avg Transfers", f"{filtered['transfers_required'].mean():.2f}")
col5.metric("Avg Wait (min)", f"{filtered['wait_time_min'].mean():.1f}")

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
cluster_counts["color"] = cluster_counts["cluster_id"].map(
    lambda x: CLUSTER_META[x]["color"])
cluster_counts["emoji_label"] = cluster_counts["cluster_id"].map(
    lambda x: f"{CLUSTER_META[x]['emoji']} {CLUSTER_META[x]['label']}"
)

color_map = {
    f"{CLUSTER_META[c]['emoji']} {CLUSTER_META[c]['label']}": CLUSTER_META[c]["color"]
    for c in CLUSTER_META
}

with dist_col1:
    fig_pie = px.pie(
        cluster_counts,
        names="emoji_label",
        values="count",
        color="emoji_label",
        color_discrete_map=color_map,
        title="Passenger Share by Cluster",
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(showlegend=False, height=380)
    st.plotly_chart(fig_pie, width='content')

with dist_col2:
    fig_bar = px.bar(
        cluster_counts.sort_values("cluster_id"),
        x="emoji_label",
        y="count",
        color="emoji_label",
        color_discrete_map=color_map,
        title="Passenger Count per Cluster",
        labels={"emoji_label": "Cluster", "count": "Passengers"},
    )
    fig_bar.update_layout(showlegend=False, height=380, xaxis_tickangle=-20)
    st.plotly_chart(fig_bar, width='content')

# ---------------------------------------------------------------------------
# Feature heatmap
# ---------------------------------------------------------------------------
st.subheader("Cluster Feature Profiles (Avg vs Overall)")

feature_cols = list(FEATURE_DISPLAY.keys())
agg = filtered.groupby("cluster_id")[feature_cols].mean()
overall = filtered[feature_cols].mean()

norm = ((agg - overall) / overall.replace(0, np.nan)).fillna(0)
norm.columns = list(FEATURE_DISPLAY.values())
norm.index = [
    f"{CLUSTER_META[c]['emoji']} {CLUSTER_META[c]['label']}" for c in norm.index]

fig_heat = px.imshow(
    norm,
    color_continuous_scale="RdBu_r",
    color_continuous_midpoint=0,
    title="Feature Deviation from Overall Mean (red = above avg, blue = below avg)",
    aspect="auto",
    text_auto=".2f",
)
fig_heat.update_layout(height=320, coloraxis_colorbar_title="Δ from mean")
st.plotly_chart(fig_heat, width='content')

# ---------------------------------------------------------------------------
# Radar chart — cluster profiles
# ---------------------------------------------------------------------------
st.subheader("Cluster Radar Profiles")

radar_agg = filtered.groupby("cluster_id")[feature_cols].mean()
# Normalize each feature to [0, 1] for radar
radar_norm = (radar_agg - radar_agg.min()) / \
    (radar_agg.max() - radar_agg.min()).replace(0, 1)
radar_labels = list(FEATURE_DISPLAY.values())

fig_radar = go.Figure()
for cluster_id in sorted(CLUSTER_META.keys()):
    if cluster_id not in selected_clusters:
        continue
    if cluster_id not in radar_norm.index:
        continue
    vals = radar_norm.loc[cluster_id].tolist()
    vals += vals[:1]  # close the polygon
    meta = CLUSTER_META[cluster_id]
    fig_radar.add_trace(go.Scatterpolar(
        r=vals,
        theta=radar_labels + radar_labels[:1],
        name=f"{meta['emoji']} {meta['label']}",
        line=dict(color=meta["color"], width=2),
        fill="toself",
        fillcolor=meta["color"],
        opacity=0.15,
    ))

fig_radar.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
    showlegend=True,
    height=420,
    title="Normalised Feature Radar by Cluster (higher = more of that feature)",
)
st.plotly_chart(fig_radar, width='content')

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
    st.info(
        "No passengers match the current filter selection. Adjust the sidebar filters.")
else:
    sample_size = min(2000, len(filtered))
    fig_scatter = px.scatter(
        filtered.sample(sample_size, random_state=42),
        x=x_axis,
        y=y_axis,
        color="cluster_display",
        color_discrete_map=color_map,
        hover_data=["passenger_id", "origin_district", "satisfaction_score"],
        labels={
            x_axis: FEATURE_DISPLAY[x_axis],
            y_axis: FEATURE_DISPLAY[y_axis],
            "cluster_display": "Cluster",
        },
        title=f"{FEATURE_DISPLAY[x_axis]} vs {FEATURE_DISPLAY[y_axis]} (sample of {sample_size:,})",
        opacity=0.65,
    )
    fig_scatter.update_layout(height=450, legend_title_text="Cluster")
    st.plotly_chart(fig_scatter, width='content')

# ---------------------------------------------------------------------------
# Income + Trip purpose breakdown
# ---------------------------------------------------------------------------
st.subheader("Demographic Breakdown by Cluster")
demo_col1, demo_col2 = st.columns(2)

with demo_col1:
    if "income_bracket" in filtered.columns:
        income_counts = (
            filtered.groupby(["cluster_id", "income_bracket"])
            .size()
            .reset_index(name="count")
        )
        income_counts["cluster_label"] = income_counts["cluster_id"].map(
            lambda x: f"{CLUSTER_META[x]['emoji']} {CLUSTER_META[x]['label']}"
        )
        fig_income = px.bar(
            income_counts,
            x="cluster_label",
            y="count",
            color="income_bracket",
            barmode="stack",
            title="Income Bracket Distribution by Cluster",
            labels={"cluster_label": "Cluster",
                    "count": "Passengers", "income_bracket": "Income"},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_income.update_layout(height=350, xaxis_tickangle=-20)
        st.plotly_chart(fig_income, width='content')

with demo_col2:
    if "trip_purpose" in filtered.columns:
        purpose_counts = (
            filtered.groupby(["cluster_id", "trip_purpose"])
            .size()
            .reset_index(name="count")
        )
        purpose_counts["cluster_label"] = purpose_counts["cluster_id"].map(
            lambda x: f"{CLUSTER_META[x]['emoji']} {CLUSTER_META[x]['label']}"
        )
        fig_purpose = px.bar(
            purpose_counts,
            x="cluster_label",
            y="count",
            color="trip_purpose",
            barmode="stack",
            title="Trip Purpose by Cluster",
            labels={"cluster_label": "Cluster",
                    "count": "Passengers", "trip_purpose": "Purpose"},
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig_purpose.update_layout(height=350, xaxis_tickangle=-20)
        st.plotly_chart(fig_purpose, width='content')

# ---------------------------------------------------------------------------
# Compare two clusters side by side
# ---------------------------------------------------------------------------
st.subheader("Compare Two Clusters")
cc1, cc2 = st.columns(2)
with cc1:
    cluster_a = st.selectbox(
        "Cluster A:",
        options=sorted(CLUSTER_META.keys()),
        index=2,
        format_func=lambda x: f"{CLUSTER_META[x]['emoji']} {CLUSTER_META[x]['label']}",
        key="cmp_a",
    )
with cc2:
    cluster_b = st.selectbox(
        "Cluster B:",
        options=sorted(CLUSTER_META.keys()),
        index=3,
        format_func=lambda x: f"{CLUSTER_META[x]['emoji']} {CLUSTER_META[x]['label']}",
        key="cmp_b",
    )

cmp_a = df[df["cluster_id"] == cluster_a]
cmp_b = df[df["cluster_id"] == cluster_b]

if not cmp_a.empty and not cmp_b.empty:
    cmp_rows = []
    for col, label in FEATURE_DISPLAY.items():
        a_mean = cmp_a[col].mean()
        b_mean = cmp_b[col].mean()
        cmp_rows.append({
            "Feature": label,
            f"{CLUSTER_META[cluster_a]['emoji']} {CLUSTER_META[cluster_a]['label']}": round(a_mean, 2),
            f"{CLUSTER_META[cluster_b]['emoji']} {CLUSTER_META[cluster_b]['label']}": round(b_mean, 2),
            "Δ (B − A)": round(b_mean - a_mean, 2),
        })
    st.dataframe(pd.DataFrame(cmp_rows),
                 width='content', hide_index=True)

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
        c1.metric("Avg Satisfaction",
                  f"{cluster_df['satisfaction_score'].mean():.2f}")
        c2.metric("Avg Transfers",
                  f"{cluster_df['transfers_required'].mean():.2f}")
        c3.metric("Avg Wait (min)",
                  f"{cluster_df['wait_time_min'].mean():.1f}")

        d1, d2, d3 = st.columns(3)
        d1.metric("Trips / Week",
                  f"{cluster_df['trips_per_week'].mean():.1f}")
        d2.metric("Avg Fare (₱)",
                  f"₱{cluster_df['avg_fare_paid_php'].mean():.2f}")
        d3.metric("Avg Travel (min)",
                  f"{cluster_df['travel_time_min'].mean():.1f}")

        st.markdown(f"**Description:** {meta['desc']}")

        if cluster_id == 3:
            st.info(
                "⚠️ **A/B Test Target** — These passengers are enrolled in the "
                "Matina → SM Lanang express route experiment. "
                "See the A/B Test Results page for significance analysis."
            )

        col_left, col_right = st.columns(2)

        with col_left:
            top_districts = (
                cluster_df["origin_district"]
                .value_counts()
                .head(5)
                .reset_index()
                .rename(columns={"origin_district": "District", "count": "Passengers"})
            )
            st.markdown("**Top Origin Districts:**")
            st.dataframe(top_districts, width='content',
                         hide_index=True)

        with col_right:
            if "prefers_aircon" in cluster_df.columns:
                aircon_rate = cluster_df["prefers_aircon"].mean() * 100
                st.metric("Prefers Aircon", f"{aircon_rate:.1f}%")

            if "trip_purpose" in cluster_df.columns:
                top_purpose = cluster_df["trip_purpose"].value_counts(
                ).idxmax()
                st.metric("Top Trip Purpose", top_purpose)

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
            st.plotly_chart(fig_elbow, width='content')

    if not silhouette_df.empty:
        with sil_col:
            fig_sil = px.line(silhouette_df, x="k", y="silhouette_score", markers=True,
                              title="Silhouette Score by K",
                              labels={"k": "K", "silhouette_score": "Silhouette Score"})
            fig_sil.add_vline(x=5, line_dash="dash", line_color="red",
                              annotation_text="K=5 selected")
            st.plotly_chart(fig_sil, width='content')

    # Best K annotation
    if not silhouette_df.empty:
        best_k = int(
            silhouette_df.loc[silhouette_df["silhouette_score"].idxmax(), "k"])
        best_score = silhouette_df["silhouette_score"].max()
        st.info(
            f"**Auto-selected K** (highest silhouette): **K={best_k}** "
            f"(score = {best_score:.4f}). Blueprint target: K=5."
        )
