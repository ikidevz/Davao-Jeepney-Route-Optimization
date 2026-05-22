"""
04_route_trends.py  *** NEW PAGE ***
-------------------------------------
Route & District Ridership Trends — powered by DuckDB in-process analytics
on mart_route_summary_recent.parquet and mart_district_ridership_recent.parquet.

Sections:
  1. KPI header: total trips / avg load / avg revenue in selected window
  2. Daily ridership trend (line chart, multi-route)
  3. Revenue trend (bar + line combo)
  4. Heatmap: ridership by route × day-of-week
  5. District ridership area chart
  6. Top/Bottom 3 routes table
  7. Raw data explorer (filterable, downloadable)
"""

import io
import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Route Trends · Davao Jeepney",
                   page_icon="📈", layout="wide")

PARQUET_DIR = Path(os.getenv("PARQUET_DIR", "/app/parquet"))

ROUTE_NAMES = {
    "R01": "Bankerohan–Toril",
    "R02": "Ecoland–SM City",
    "R03": "Agdao Loop",
    "R04": "Calinan–Bankerohan",
    "R05": "Buhangin–Lanang",
    "R06": "Matina–Ulas",
    "R07": "Talomo–Davao Proper",
    "R08": "Mintal–Bankerohan",
    "R09": "Panacan–Bankerohan",
    "R10": "Toril–Sta. Ana Wharf",
    "R11": "Sasa–Bajada",
    "R12": "Matina–SM Lanang Express ⚗️",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_route_summary() -> pd.DataFrame:
    path = PARQUET_DIR / "mart_route_summary_recent.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()
    if "trip_date" in df.columns:
        df["trip_date"] = pd.to_datetime(df["trip_date"])
    return df


@st.cache_data(ttl=300)
def load_district_ridership() -> pd.DataFrame:
    path = PARQUET_DIR / "mart_district_ridership_recent.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = duckdb.query(f"SELECT * FROM read_parquet('{path}')").df()
    if "trip_date" in df.columns:
        df["trip_date"] = pd.to_datetime(df["trip_date"])
    return df


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.title("📈 Route & District Ridership Trends")
st.caption("DuckDB in-process analytics on mart_route_summary and mart_district_ridership (last 30 days)")

route_df = load_route_summary()
district_df = load_district_ridership()

if route_df.empty and district_df.empty:
    st.error(
        "Trend data not found. Run `science/export_to_parquet.py` to generate "
        "`mart_route_summary_recent.parquet` and `mart_district_ridership_recent.parquet`."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")

    if not route_df.empty and "route_id" in route_df.columns:
        all_routes = sorted(route_df["route_id"].unique())
        selected_routes = st.multiselect(
            "Routes:",
            options=all_routes,
            default=all_routes,
            format_func=lambda r: f"{r} — {ROUTE_NAMES.get(r, r)}",
        )
    else:
        selected_routes = []

    if not route_df.empty and "trip_date" in route_df.columns:
        min_date = route_df["trip_date"].min().date()
        max_date = route_df["trip_date"].max().date()
        date_range = st.date_input(
            "Date range:",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date, end_date = None, None

    smooth = st.slider("Rolling average (days):",
                       min_value=1, max_value=7, value=1)

# ---------------------------------------------------------------------------
# Filter data
# ---------------------------------------------------------------------------
if not route_df.empty:
    mask = pd.Series(True, index=route_df.index)
    if selected_routes:
        mask &= route_df["route_id"].isin(selected_routes)
    if start_date and end_date and "trip_date" in route_df.columns:
        mask &= route_df["trip_date"].dt.date.between(start_date, end_date)
    filtered_route = route_df[mask].copy()
else:
    filtered_route = pd.DataFrame()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
if not filtered_route.empty:
    st.markdown("### Key Metrics (Filtered Period)")
    k1, k2, k3, k4 = st.columns(4)

    total_pax = filtered_route["total_passengers"].sum(
    ) if "total_passengers" in filtered_route else 0
    avg_load = filtered_route["avg_load_factor"].mean(
    ) if "avg_load_factor" in filtered_route else None
    avg_rev = filtered_route["total_revenue_php"].sum(
    ) if "total_revenue_php" in filtered_route else None
    n_days = filtered_route["trip_date"].nunique(
    ) if "trip_date" in filtered_route else 0

    k1.metric("Total Passengers", f"{total_pax:,.0f}")
    k2.metric("Days of Data", f"{n_days}")
    k3.metric("Avg Load Factor",
              f"{avg_load:.1%}" if avg_load is not None else "—")
    k4.metric("Total Revenue (₱)",
              f"₱{avg_rev:,.0f}" if avg_rev is not None else "—")

    st.markdown("---")

# ---------------------------------------------------------------------------
# Daily ridership trend
# ---------------------------------------------------------------------------
if not filtered_route.empty and "trip_date" in filtered_route.columns and "total_passengers" in filtered_route.columns:
    st.subheader("Daily Ridership Trend by Route")

    trend = filtered_route.sort_values(["route_id", "trip_date"]).copy()
    trend["route_label"] = trend["route_id"].map(
        lambda r: f"{r} — {ROUTE_NAMES.get(r, r)}")

    if smooth > 1:
        trend["total_passengers"] = (
            trend.groupby("route_id")["total_passengers"]
            .transform(lambda x: x.rolling(smooth, min_periods=1).mean())
        )

    fig_trend = px.line(
        trend,
        x="trip_date",
        y="total_passengers",
        color="route_label",
        title=f"Daily Passengers by Route" +
        (f" ({smooth}-day rolling avg)" if smooth > 1 else ""),
        labels={"trip_date": "Date",
                "total_passengers": "Passengers", "route_label": "Route"},
    )
    fig_trend.update_layout(height=420, legend_title="Route")
    st.plotly_chart(fig_trend, use_container_width=True)

# ---------------------------------------------------------------------------
# Revenue trend (if available)
# ---------------------------------------------------------------------------
if not filtered_route.empty and "total_revenue_php" in filtered_route.columns:
    st.subheader("Daily Revenue Trend (₱)")

    rev_trend = (
        filtered_route.groupby("trip_date")["total_revenue_php"]
        .sum()
        .reset_index()
        .sort_values("trip_date")
    )
    if smooth > 1:
        rev_trend["total_revenue_php"] = rev_trend["total_revenue_php"].rolling(
            smooth, min_periods=1).mean()

    fig_rev = go.Figure()
    fig_rev.add_trace(go.Bar(
        x=rev_trend["trip_date"],
        y=rev_trend["total_revenue_php"],
        name="Daily Revenue",
        marker_color="#3B82F6",
        opacity=0.6,
    ))
    fig_rev.add_trace(go.Scatter(
        x=rev_trend["trip_date"],
        y=rev_trend["total_revenue_php"].rolling(7, min_periods=1).mean(),
        name="7-day avg",
        line=dict(color="#EF4444", width=2),
        mode="lines",
    ))
    fig_rev.update_layout(
        title="Total Daily Revenue (₱) — All Selected Routes",
        xaxis_title="Date",
        yaxis_title="Revenue (₱)",
        height=380,
        legend=dict(orientation="h"),
    )
    st.plotly_chart(fig_rev, use_container_width=True)

# ---------------------------------------------------------------------------
# Heatmap: ridership by route x day-of-week
# ---------------------------------------------------------------------------
if not filtered_route.empty and "trip_date" in filtered_route.columns:
    st.subheader("Ridership Heatmap — Route × Day of Week")

    hm = filtered_route.copy()
    hm["day_of_week"] = hm["trip_date"].dt.day_name()
    day_order = ["Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday", "Sunday"]

    hm_agg = (
        hm.groupby(["route_id", "day_of_week"])["total_passengers"]
        .mean()
        .reset_index()
    )
    hm_pivot = hm_agg.pivot(
        index="route_id", columns="day_of_week", values="total_passengers")
    hm_pivot = hm_pivot.reindex(
        columns=[d for d in day_order if d in hm_pivot.columns])
    hm_pivot.index = [f"{r} — {ROUTE_NAMES.get(r, r)}" for r in hm_pivot.index]

    fig_hm = px.imshow(
        hm_pivot,
        color_continuous_scale="Blues",
        title="Avg Daily Passengers by Route × Day of Week",
        aspect="auto",
        text_auto=".0f",
    )
    fig_hm.update_layout(height=400, coloraxis_colorbar_title="Avg Pax")
    st.plotly_chart(fig_hm, use_container_width=True)

# ---------------------------------------------------------------------------
# District ridership area chart
# ---------------------------------------------------------------------------
if not district_df.empty and "trip_date" in district_df.columns and "district" in district_df.columns:
    st.subheader("District Ridership Over Time")

    dist_filtered = district_df.copy()
    if start_date and end_date:
        dist_filtered = dist_filtered[
            dist_filtered["trip_date"].dt.date.between(start_date, end_date)
        ]

    if "total_passengers" in dist_filtered.columns:
        fig_dist = px.area(
            dist_filtered.sort_values("trip_date"),
            x="trip_date",
            y="total_passengers",
            color="district",
            title="Daily Ridership by District",
            labels={"trip_date": "Date",
                    "total_passengers": "Passengers", "district": "District"},
        )
        fig_dist.update_layout(height=420, legend_title="District")
        st.plotly_chart(fig_dist, use_container_width=True)

# ---------------------------------------------------------------------------
# Top / Bottom routes
# ---------------------------------------------------------------------------
if not filtered_route.empty and "total_passengers" in filtered_route.columns:
    st.subheader("Route Performance Summary")
    top_col, bot_col = st.columns(2)

    route_perf = (
        filtered_route.groupby("route_id")["total_passengers"]
        .sum()
        .reset_index()
        .sort_values("total_passengers", ascending=False)
    )
    route_perf["Route"] = route_perf["route_id"].map(
        lambda r: f"{r} — {ROUTE_NAMES.get(r, r)}"
    )
    route_perf["Total Passengers"] = route_perf["total_passengers"].map(
        "{:,.0f}".format)

    with top_col:
        st.markdown("**🏆 Top 3 Routes by Ridership**")
        st.dataframe(
            route_perf.head(3)[["Route", "Total Passengers"]],
            use_container_width=True,
            hide_index=True,
        )

    with bot_col:
        st.markdown("**📉 Bottom 3 Routes by Ridership**")
        st.dataframe(
            route_perf.tail(3)[["Route", "Total Passengers"]
                               ].sort_values("Total Passengers"),
            use_container_width=True,
            hide_index=True,
        )

# ---------------------------------------------------------------------------
# Raw data explorer
# ---------------------------------------------------------------------------
with st.expander("🔍 Raw Route Summary Data"):
    if not filtered_route.empty:
        st.dataframe(filtered_route.head(500),
                     use_container_width=True, hide_index=True)
        csv_buf = io.BytesIO()
        filtered_route.to_csv(csv_buf, index=False)
        st.download_button(
            "📥 Export route summary (CSV)",
            data=csv_buf.getvalue(),
            file_name="route_summary.csv",
            mime="text/csv",
        )
    else:
        st.info("No route summary data available.")

with st.expander("🔍 Raw District Ridership Data"):
    if not district_df.empty:
        st.dataframe(district_df.head(500),
                     use_container_width=True, hide_index=True)
        csv_buf2 = io.BytesIO()
        district_df.to_csv(csv_buf2, index=False)
        st.download_button(
            "📥 Export district ridership (CSV)",
            data=csv_buf2.getvalue(),
            file_name="district_ridership.csv",
            mime="text/csv",
        )
    else:
        st.info("No district ridership data available.")
