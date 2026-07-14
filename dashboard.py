"""
dashboard.py
-------------
Interactive Streamlit dashboard for the Most Visited Pages Finder.

Lets you:
  - Use the bundled sample log or upload your own access log
  - Watch the record count shrink through each cleaning step
  - Explore the Top-N most visited pages with an adjustable N
  - Download the ranked report as CSV
  - See time-based analysis: busiest hour of day and busiest day of week

Run with:
    streamlit run src/dashboard.py
"""

import os
import sys
import tempfile

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from log_parser import parse_log_file
from pipeline import clean_records, to_dataframe, frequency_analysis

st.set_page_config(
    page_title="Most Visited Pages Finder",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------- Sidebar --
st.sidebar.title("📊 Most Visited Pages Finder")
st.sidebar.caption("Web Usage Mining — Data Analytics Project")

st.sidebar.markdown("### 1. Choose a log source")
source = st.sidebar.radio(
    "Log file", ["Use bundled sample log", "Upload my own log"], label_visibility="collapsed"
)

log_path = None
tmp_file = None

if source == "Use bundled sample log":
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "sample_access.log"),                 # flat layout (file next to dashboard.py)
        os.path.join(here, "data", "sample_access.log"),          # dashboard.py at repo root, data/ subfolder
        os.path.join(here, "..", "data", "sample_access.log"),    # nested layout: src/dashboard.py, ../data/
    ]
    default_path = next((p for p in candidates if os.path.exists(p)), candidates[0])
    log_path = default_path
    st.sidebar.success(f"Using {os.path.basename(default_path)}")
else:
    uploaded = st.sidebar.file_uploader("Upload an access log (.log/.txt)", type=["log", "txt"])
    if uploaded is not None:
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".log")
        tmp_file.write(uploaded.read())
        tmp_file.close()
        log_path = tmp_file.name
        st.sidebar.success(f"Loaded {uploaded.name}")

st.sidebar.markdown("### 2. Report settings")
top_n = st.sidebar.slider("Number of top pages to show", min_value=5, max_value=30, value=10)

st.sidebar.markdown("---")
st.sidebar.caption("Guided by Binju Saju · CSE-DS · 2024-28")
st.sidebar.caption("Amruth Krishnan J · Chrison Roy · Rithin Ratheesh")

# ---------------------------------------------------------------- Main -----
st.title("Most Visited Pages Finder")
st.caption("Identifying and ranking frequently accessed webpages from web server access logs")

if log_path is None or not os.path.exists(log_path):
    st.info("👈 Choose or upload an access log from the sidebar to get started.")
    st.stop()


@st.cache_data(show_spinner=False)
def run_full_pipeline(path, n_top):
    records, n_malformed = parse_log_file(path)
    cleaned, stats = clean_records(records)
    df = to_dataframe(cleaned)
    counter = frequency_analysis(df)
    ranked = counter.most_common(n_top)
    report_df = pd.DataFrame(ranked, columns=["Page URL", "Visits"])
    report_df.insert(0, "Rank", range(1, len(report_df) + 1))
    stats["raw_lines_parsed"] = len(records)
    stats["malformed_lines_discarded"] = n_malformed
    stats["unique_pages"] = len(counter)
    return stats, report_df, df


with st.spinner("Running the six-stage pipeline..."):
    stats, report_df, df = run_full_pipeline(log_path, top_n)

# ---- Stage progress / KPIs -------------------------------------------------
st.subheader("Pipeline Overview")
cols = st.columns(6)
cols[0].metric("1. Collected", f"{stats['raw_lines_parsed'] + stats['malformed_lines_discarded']:,}")
cols[1].metric("2. Parsed OK", f"{stats['raw_lines_parsed']:,}", delta=f"-{stats['malformed_lines_discarded']} malformed", delta_color="inverse")
cols[2].metric("3a. After bot removal", f"{stats['after_removing_bots']:,}")
cols[3].metric("3b. After de-dup", f"{stats['after_removing_duplicates']:,}")
cols[4].metric("3c. After 2xx filter", f"{stats['after_keeping_2xx_only']:,}")
cols[5].metric("5. Unique pages", f"{stats['unique_pages']:,}")

# Funnel showing records shrinking through the cleaning stages
funnel_df = pd.DataFrame({
    "Stage": ["Parsed", "After bot removal", "After de-duplication", "After 2xx filter"],
    "Records": [
        stats["raw_lines_parsed"],
        stats["after_removing_bots"],
        stats["after_removing_duplicates"],
        stats["after_keeping_2xx_only"],
    ],
})
fig_funnel = px.funnel(funnel_df, x="Records", y="Stage", title="Data Cleaning Funnel")
fig_funnel.update_layout(height=320, margin=dict(t=50, b=10))
st.plotly_chart(fig_funnel, use_container_width=True)

st.markdown("---")

# ---- Ranking & chart --------------------------------------------------------
left, right = st.columns([2, 3])

with left:
    st.subheader(f"Top {top_n} Pages")
    st.dataframe(report_df, use_container_width=True, hide_index=True)
    csv_bytes = report_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download report as CSV", csv_bytes, "top_pages.csv", "text/csv")

with right:
    st.subheader("Visit Frequency")
    fig_bar = px.bar(
        report_df.sort_values("Visits"),
        x="Visits",
        y="Page URL",
        orientation="h",
        color="Visits",
        color_continuous_scale="Viridis",
        text="Visits",
    )
    fig_bar.update_layout(height=420, coloraxis_showscale=False, margin=dict(t=10, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# ---- Status code breakdown & timeline --------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("HTTP Status Code Breakdown")
    if not df.empty:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status Code", "Count"]
        fig_status = px.pie(status_counts, names="Status Code", values="Count", hole=0.45)
        fig_status.update_layout(height=350, margin=dict(t=10, b=10))
        st.plotly_chart(fig_status, use_container_width=True)

with c2:
    st.subheader("Requests Over Time")
    if not df.empty and df["timestamp"].notna().any():
        ts = df.dropna(subset=["timestamp"]).set_index("timestamp").resample("1h").size().reset_index()
        ts.columns = ["Time", "Requests"]
        fig_ts = px.line(ts, x="Time", y="Requests")
        fig_ts.update_layout(height=350, margin=dict(t=10, b=10))
        st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.caption("No parsable timestamps to plot.")

st.markdown("---")

# ---- Time-based analysis: when is the site busiest? ------------------------
st.subheader("Time-Based Analysis")
st.caption("Complements the frequency ranking above by showing *when* traffic peaks, not just *what* pages are popular.")

if not df.empty and df["timestamp"].notna().any():
    ts_df = df.dropna(subset=["timestamp"]).copy()
    ts_df["hour"] = ts_df["timestamp"].dt.hour
    ts_df["day_of_week"] = ts_df["timestamp"].dt.day_name()

    hourly = ts_df.groupby("hour").size().reindex(range(24), fill_value=0).reset_index()
    hourly.columns = ["Hour", "Requests"]

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily = ts_df.groupby("day_of_week").size().reindex(day_order, fill_value=0).reset_index()
    daily.columns = ["Day", "Requests"]

    busiest_hour = int(hourly.loc[hourly["Requests"].idxmax(), "Hour"])
    busiest_hour_count = int(hourly["Requests"].max())
    busiest_day = daily.loc[daily["Requests"].idxmax(), "Day"]
    busiest_day_count = int(daily["Requests"].max())

    m1, m2 = st.columns(2)
    m1.metric("Busiest hour", f"{busiest_hour:02d}:00–{busiest_hour:02d}:59", f"{busiest_hour_count:,} requests")
    m2.metric("Busiest day", busiest_day, f"{busiest_day_count:,} requests")

    t1, t2 = st.columns(2)
    with t1:
        fig_hour = px.bar(hourly, x="Hour", y="Requests", color="Requests", color_continuous_scale="Mako")
        fig_hour.update_layout(title="Requests by Hour of Day", height=380, coloraxis_showscale=False, margin=dict(t=40, b=10))
        fig_hour.update_xaxes(dtick=1)
        st.plotly_chart(fig_hour, use_container_width=True)
    with t2:
        fig_day = px.bar(daily, x="Day", y="Requests", color="Requests", color_continuous_scale="Sunset")
        fig_day.update_layout(title="Requests by Day of Week", height=380, coloraxis_showscale=False, margin=dict(t=40, b=10))
        st.plotly_chart(fig_day, use_container_width=True)
else:
    st.caption("No parsable timestamps available for time-based analysis.")

# Clean up temp upload
if tmp_file is not None:
    try:
        os.unlink(tmp_file.name)
    except OSError:
        pass
