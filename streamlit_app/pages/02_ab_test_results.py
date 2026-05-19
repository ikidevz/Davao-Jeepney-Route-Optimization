"""
02_ab_test_results.py
---------------------
A/B Test Results page — Matina → SM Lanang express route experiment analysis.

Sections:
  1. Experiment summary banner
  2. Statistical test results (t-test + chi-square)
  3. Satisfaction lift chart (control vs treatment, by week)
  4. Travel time comparison violin/box
  5. Confidence interval chart
  6. Recommendation verdict
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="A/B Test Results · Davao Jeepney", page_icon="🧪", layout="wide")

PARQUET_DIR = Path(os.getenv("PARQUET_DIR", "/app/parquet"))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_ab_results() -> pd.DataFrame:
    path = PARQUET_DIR / "mart_ab_test_results.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


@st.cache_data(ttl=300)
def load_statistics() -> pd.DataFrame:
    path = PARQUET_DIR / "ab_test_statistics.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def get_stat(stats_df: pd.DataFrame, metric: str) -> dict:
    """Safely extract a single metric row as a dict; returns {} if not found."""
    rows = stats_df[stats_df["metric"] == metric]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.title("🧪 A/B Test Results")
st.caption("Matina → SM Lanang Express Route Experiment — 8-Week Simulated Trial")

df    = load_ab_results()
stats = load_statistics()

if df.empty or stats.empty:
    st.error(
        "A/B test data not found. Run `science/ab_testing.py` then `science/export_to_parquet.py` first."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Experiment summary banner
# ---------------------------------------------------------------------------
ctrl = df[df["group"] == "control"]
trt  = df[df["group"] == "treatment"]

n_ctrl = ctrl["passenger_id"].nunique()
n_trt  = trt["passenger_id"].nunique()

sat_stat  = get_stat(stats, "satisfaction_score")
time_stat = get_stat(stats, "simulated_travel_time_min")
chi_stat  = get_stat(stats, "would_use_again")

is_sig = bool(sat_stat.get("is_significant", False))
verdict_color  = "green" if is_sig else "orange"
verdict_symbol = "✅" if is_sig else "⚠️"
verdict_text   = (
    "Express route SIGNIFICANTLY improves commuter satisfaction (p < 0.05)"
    if is_sig
    else "No statistically significant improvement detected at α = 0.05"
)

st.markdown(
    f"""
    <div style="background:#1e293b;padding:20px;border-radius:10px;border-left:5px solid {verdict_color};">
    <h3 style="color:white;margin:0">{verdict_symbol} Experiment Verdict</h3>
    <p style="color:#cbd5e1;margin:8px 0 0 0;font-size:1.1em">{verdict_text}</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Control (A) size",    f"{n_ctrl} passengers")
k2.metric("Treatment (B) size",  f"{n_trt} passengers")
k3.metric("Trial duration",      "8 weeks")
k4.metric("p-value (satisfaction)",
          f"{sat_stat['p_value']:.4f}" if sat_stat else "N/A")
k5.metric("Cohen's d",
          f"{sat_stat['effect_size']:.3f}" if sat_stat else "N/A")

st.markdown("---")

# ---------------------------------------------------------------------------
# Experiment design info
# ---------------------------------------------------------------------------
with st.expander("📋 Experiment Design", expanded=False):
    st.markdown(
        """
        | Parameter | Value |
        |-----------|-------|
        | **Hypothesis** | Adding a direct Matina → SM Lanang express route reduces travel time and improves satisfaction for Underserved Riders (Cluster 3) |
        | **Control (A)** | Current route — 2 transfers, avg 55 min travel time |
        | **Treatment (B)** | Express direct route — 0 transfers, avg 35 min travel time |
        | **Target segment** | Cluster 3 — Underserved Riders (lowest satisfaction) |
        | **Split** | 50 / 50 random assignment |
        | **Duration** | 8 simulated weeks |
        | **Primary metric** | `satisfaction_score` (1–5 scale) — two-sample t-test |
        | **Secondary metric** | `would_use_again` (boolean) — chi-square test |
        | **Significance level** | α = 0.05, target power = 0.80 |
        """
    )

# ---------------------------------------------------------------------------
# Statistical test results table
# ---------------------------------------------------------------------------
st.subheader("Statistical Test Results")

display_stats = []
for _, row in stats.iterrows():
    metric = row.get("metric", "")
    if metric == "would_use_again":
        display_stats.append({
            "Metric":         "Would Use Again",
            "Test":           "Chi-Square",
            "Control":        f"{100*float(row.get('control_pct_yes', 0)):.1f}%",
            "Treatment":      f"{100*float(row.get('treatment_pct_yes', 0)):.1f}%",
            "Statistic":      f"χ²={float(row.get('chi2_statistic', 0)):.3f}",
            "p-value":        f"{float(row.get('p_value', 1)):.4f}",
            "Significant":    "✅ Yes" if row.get("is_significant") else "❌ No",
        })
    else:
        label = "Satisfaction Score" if metric == "satisfaction_score" else "Travel Time (min)"
        display_stats.append({
            "Metric":         label,
            "Test":           "Welch's t-test",
            "Control":        f"{float(row.get('control_mean', 0)):.3f}",
            "Treatment":      f"{float(row.get('treatment_mean', 0)):.3f}",
            "Statistic":      f"t={float(row.get('t_statistic', 0)):.3f}",
            "p-value":        f"{float(row.get('p_value', 1)):.4f}",
            "Significant":    "✅ Yes" if row.get("is_significant") else "❌ No",
        })

st.dataframe(pd.DataFrame(display_stats), use_container_width=True, hide_index=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Weekly satisfaction trend
# ---------------------------------------------------------------------------
st.subheader("Satisfaction Score by Week — Control vs Treatment")

weekly = (
    df.groupby(["test_week", "group"])["satisfaction_score"]
    .mean()
    .reset_index()
)
weekly["group_label"] = weekly["group"].map({"control": "Control (A) — Current Route",
                                              "treatment": "Treatment (B) — Express Route"})

fig_weekly = px.line(
    weekly,
    x="test_week",
    y="satisfaction_score",
    color="group_label",
    markers=True,
    color_discrete_map={
        "Control (A) — Current Route":    "#94a3b8",
        "Treatment (B) — Express Route":  "#3B82F6",
    },
    labels={"test_week": "Experiment Week", "satisfaction_score": "Avg Satisfaction Score",
             "group_label": "Group"},
    title="Weekly Average Satisfaction Score",
)
fig_weekly.update_layout(height=380, yaxis_range=[1, 5])
fig_weekly.add_hline(y=3, line_dash="dot", line_color="gray", annotation_text="Neutral (3.0)")
st.plotly_chart(fig_weekly, use_container_width=True)

# ---------------------------------------------------------------------------
# Distribution comparison
# ---------------------------------------------------------------------------
dist_col1, dist_col2 = st.columns(2)

with dist_col1:
    st.subheader("Satisfaction Distribution")
    fig_sat = px.histogram(
        df,
        x="satisfaction_score",
        color="group",
        barmode="overlay",
        nbins=5,
        color_discrete_map={"control": "#94a3b8", "treatment": "#3B82F6"},
        labels={"group": "Group", "satisfaction_score": "Satisfaction Score"},
        title="Satisfaction Score Distribution",
        opacity=0.75,
    )
    fig_sat.update_layout(height=350)
    st.plotly_chart(fig_sat, use_container_width=True)

with dist_col2:
    st.subheader("Travel Time Distribution")
    fig_time = px.box(
        df,
        x="group",
        y="simulated_travel_time_min",
        color="group",
        color_discrete_map={"control": "#94a3b8", "treatment": "#3B82F6"},
        labels={"group": "Group", "simulated_travel_time_min": "Travel Time (min)"},
        title="Travel Time by Group",
        points="outliers",
    )
    fig_time.update_layout(height=350, showlegend=False)
    st.plotly_chart(fig_time, use_container_width=True)

# ---------------------------------------------------------------------------
# Confidence interval chart
# ---------------------------------------------------------------------------
st.subheader("Mean Difference & 95% Confidence Intervals (Treatment − Control)")

ci_rows = []
for _, row in stats.iterrows():
    metric = row.get("metric")
    if metric == "would_use_again":
        continue
    label = "Satisfaction Score" if metric == "satisfaction_score" else "Travel Time (min)"
    ci_rows.append({
        "Metric":   label,
        "diff":     float(row.get("mean_diff", 0)),
        "ci_low":   float(row.get("ci_low_95", 0)),
        "ci_high":  float(row.get("ci_high_95", 0)),
        "p_value":  float(row.get("p_value", 1)),
        "is_sig":   bool(row.get("is_significant", False)),
    })

if ci_rows:
    ci_df = pd.DataFrame(ci_rows)

    fig_ci = go.Figure()
    for i, r in ci_df.iterrows():
        color = "#3B82F6" if r["is_sig"] else "#94a3b8"
        fig_ci.add_trace(go.Scatter(
            x=[r["ci_low"], r["diff"], r["ci_high"]],
            y=[r["Metric"]] * 3,
            mode="lines+markers",
            marker=dict(size=[8, 14, 8], color=color, symbol=["line-ew", "circle", "line-ew"]),
            line=dict(color=color, width=3),
            name=r["Metric"],
            showlegend=False,
        ))

    fig_ci.add_vline(x=0, line_dash="dash", line_color="gray", annotation_text="No effect")
    fig_ci.update_layout(
        title="95% CI of Mean Difference (Treatment − Control)",
        xaxis_title="Difference in Mean",
        height=250,
        yaxis=dict(tickfont=dict(size=13)),
    )
    st.plotly_chart(fig_ci, use_container_width=True)

# ---------------------------------------------------------------------------
# Retention (would_use_again)
# ---------------------------------------------------------------------------
st.subheader("Retention — Would Use Express Route Again?")

retention = (
    df.groupby("group")["would_use_again"]
    .agg(["sum", "count"])
    .reset_index()
)
retention["pct_yes"] = 100 * retention["sum"] / retention["count"]
retention["group_label"] = retention["group"].map(
    {"control": "Control (A)", "treatment": "Treatment (B)"}
)

fig_ret = px.bar(
    retention,
    x="group_label",
    y="pct_yes",
    color="group",
    color_discrete_map={"control": "#94a3b8", "treatment": "#3B82F6"},
    labels={"group_label": "Group", "pct_yes": "% Would Use Again"},
    title="Retention Rate by Group",
    text_auto=".1f",
)
fig_ret.update_traces(texttemplate="%{y:.1f}%", textposition="outside")
fig_ret.update_layout(height=350, showlegend=False, yaxis_range=[0, 110])
st.plotly_chart(fig_ret, use_container_width=True)

# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("📌 Recommendation")

p_val = float(sat_stat.get("p_value", 1))
d_val = float(sat_stat.get("effect_size", 0))
ctrl_sat  = float(sat_stat.get("control_mean", 0))
trt_sat   = float(sat_stat.get("treatment_mean", 0))
ctrl_time = float(time_stat.get("control_mean", 0))
trt_time  = float(time_stat.get("treatment_mean", 0))

if is_sig:
    st.success(
        f"**Adopt the Matina → SM Lanang Express Route.**\n\n"
        f"The experiment demonstrates a statistically significant improvement in commuter satisfaction "
        f"(p = {p_val:.4f}, Cohen's d = {d_val:.3f}). "
        f"Treatment group satisfaction rose from {ctrl_sat:.2f} to {trt_sat:.2f} on a 5-point scale. "
        f"Average travel time fell from {ctrl_time:.0f} min to {trt_time:.0f} min — a "
        f"{abs(ctrl_time - trt_time):.0f}-minute reduction. "
        f"Recommend full rollout with 6-month monitoring of ridership and load factor."
    )
else:
    st.warning(
        f"**Further investigation needed before route adoption.**\n\n"
        f"No statistically significant satisfaction improvement was detected (p = {p_val:.4f}). "
        f"Consider extending the trial period, increasing sample size, or redesigning the route "
        f"based on qualitative commuter feedback from Cluster 3 interviews."
    )

st.caption(f"Statistical tests: Welch's t-test (satisfaction, travel time) + Chi-square (would_use_again). α = 0.05.")
