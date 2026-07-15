"""
dashboard.py
-------------
Interactive Streamlit dashboard for the Most Visited Pages Finder.

Visual identity: a "mission control" telemetry console, grounded in the
project's own subject matter (NASA Kennedy Space Center server logs) and its
six-stage pipeline. The pipeline-stage strip under the header is not
decorative -- it names the six real stages the data just passed through.

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
import textwrap

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from log_parser import parse_log_file
from pipeline import clean_records, to_dataframe, frequency_analysis

st.set_page_config(
    page_title="Most Visited Pages Finder",
    page_icon="🛰️",
    layout="wide",
)

# =============================================================================
# DESIGN TOKENS -- mission-control console palette & type
# =============================================================================
BG = "#0A0E16"
BG_PANEL = "#121A28"
BORDER = "#232E42"
TEXT = "#E8ECF3"
TEXT_MUTED = "#7C8AA0"
ACCENT = "#FF9A44"       # console amber -- primary signal color
ACCENT_2 = "#3FDCC5"     # telemetry teal -- secondary signal color
ACCENT_DIM = "#5A4530"   # dimmed amber for inactive states

FONT_MONO = "'IBM Plex Mono', 'SFMono-Regular', Consolas, monospace"
FONT_SANS = "'IBM Plex Sans', -apple-system, sans-serif"

PLOTLY_LAYOUT = dict(
    paper_bgcolor=BG_PANEL,
    plot_bgcolor=BG_PANEL,
    font=dict(family=FONT_MONO, color=TEXT, size=12),
    title=dict(font=dict(family=FONT_MONO, color=TEXT, size=14)),
    xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, color=TEXT_MUTED),
    yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, color=TEXT_MUTED),
    colorway=[ACCENT, ACCENT_2, "#6B8CFF", "#FF6B6B", "#B98BFF"],
    margin=dict(t=40, b=10, l=10, r=10),
)
AMBER_SCALE = [[0, "#2A2013"], [0.5, "#8A5A22"], [1, ACCENT]]
TEAL_SCALE = [[0, "#122421"], [0.5, "#1F6B60"], [1, ACCENT_2]]


def inject_css():
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

    html, body, [class*="css"] {{
        font-family: {FONT_SANS};
    }}
    .stApp {{
        background-color: {BG};
    }}
    section[data-testid="stSidebar"] {{
        background-color: {BG_PANEL};
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] label {{
        color: {TEXT_MUTED};
        font-family: {FONT_MONO};
        font-size: 0.78rem;
        letter-spacing: 0.04em;
    }}

    /* -- eyebrow / section label pattern -------------------------------- */
    .console-eyebrow {{
        font-family: {FONT_MONO};
        font-size: 0.72rem;
        letter-spacing: 0.18em;
        color: {ACCENT_2};
        text-transform: uppercase;
        margin-bottom: 0.2rem;
    }}
    .console-heading {{
        font-family: {FONT_MONO};
        font-weight: 600;
        font-size: 1.05rem;
        color: {TEXT};
        letter-spacing: 0.02em;
        margin: 0 0 0.6rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid {BORDER};
    }}

    /* -- hero header ------------------------------------------------------ */
    .console-hero-eyebrow {{
        font-family: {FONT_MONO};
        font-size: 0.78rem;
        letter-spacing: 0.25em;
        color: {ACCENT};
        text-transform: uppercase;
        margin-bottom: 0.3rem;
    }}
    .console-hero-title {{
        font-family: {FONT_MONO};
        font-weight: 700;
        font-size: 2.1rem;
        color: {TEXT};
        letter-spacing: 0.01em;
        margin: 0 0 0.3rem 0;
        line-height: 1.15;
    }}
    .console-hero-sub {{
        font-family: {FONT_SANS};
        font-size: 0.92rem;
        color: {TEXT_MUTED};
        margin-bottom: 1.4rem;
    }}

    /* -- pipeline stage strip (signature element) -------------------------- */
    .stage-strip {{
        display: flex;
        align-items: center;
        background: {BG_PANEL};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 0.9rem 1.2rem;
        margin-bottom: 1.6rem;
        overflow-x: auto;
    }}
    .stage-node {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-shrink: 0;
    }}
    .stage-dot {{
        width: 9px;
        height: 9px;
        border-radius: 2px;
        background: {ACCENT};
        box-shadow: 0 0 8px {ACCENT};
        flex-shrink: 0;
    }}
    .stage-node:last-child .stage-dot {{
        animation: pulse 1.8s ease-in-out infinite;
    }}
    @media (prefers-reduced-motion: reduce) {{
        .stage-node:last-child .stage-dot {{ animation: none; }}
    }}
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.35; }}
    }}
    .stage-label {{
        font-family: {FONT_MONO};
        font-size: 0.74rem;
        letter-spacing: 0.1em;
        color: {TEXT};
        text-transform: uppercase;
        white-space: nowrap;
    }}
    .stage-num {{
        color: {TEXT_MUTED};
        margin-right: 0.15rem;
    }}
    .stage-line {{
        flex: 1 0 28px;
        height: 1px;
        background: repeating-linear-gradient(90deg, {ACCENT_DIM} 0, {ACCENT_DIM} 4px, transparent 4px, transparent 8px);
        margin: 0 0.7rem;
        min-width: 20px;
    }}

    /* -- readout cards (KPIs) -------------------------------------------- */
    .readout-row {{ display: flex; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 1.2rem; }}
    .readout-card {{
        flex: 1 1 140px;
        background: {BG_PANEL};
        border: 1px solid {BORDER};
        border-left: 2px solid {ACCENT};
        border-radius: 4px;
        padding: 0.65rem 0.9rem;
    }}
    .readout-label {{
        font-family: {FONT_MONO};
        font-size: 0.66rem;
        letter-spacing: 0.08em;
        color: {TEXT_MUTED};
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }}
    .readout-value {{
        font-family: {FONT_MONO};
        font-size: 1.35rem;
        font-weight: 600;
        color: {TEXT};
        line-height: 1.1;
    }}
    .readout-delta {{
        font-family: {FONT_MONO};
        font-size: 0.68rem;
        color: {ACCENT_2};
        margin-top: 0.2rem;
    }}

    /* -- dataframe / buttons / misc ---------------------------------------- */
    [data-testid="stDataFrame"] {{
        border: 1px solid {BORDER};
        border-radius: 4px;
    }}
    .stButton button, .stDownloadButton button {{
        font-family: {FONT_MONO};
        background-color: transparent;
        color: {ACCENT};
        border: 1px solid {ACCENT};
        border-radius: 4px;
        letter-spacing: 0.04em;
    }}
    .stButton button:hover, .stDownloadButton button:hover {{
        background-color: {ACCENT};
        color: {BG};
    }}
    .stTextInput input {{
        font-family: {FONT_MONO};
        background-color: {BG_PANEL};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 4px;
    }}
    .stTextInput input:focus {{
        border-color: {ACCENT};
        box-shadow: 0 0 0 1px {ACCENT};
    }}
    hr {{ border-color: {BORDER} !important; }}
    </style>
    """
    st.markdown(textwrap.dedent(css), unsafe_allow_html=True)


def eyebrow_heading(eyebrow, heading):
    st.markdown(
        f'<div class="console-eyebrow">{eyebrow}</div><div class="console-heading">{heading}</div>',
        unsafe_allow_html=True,
    )


def readout_row(items):
    """items: list of (label, value, delta_or_None)"""
    cards = ""
    for label, value, delta in items:
        delta_html = f'<div class="readout-delta">{delta}</div>' if delta else ""
        cards += (
            f'<div class="readout-card">'
            f'<div class="readout-label">{label}</div>'
            f'<div class="readout-value">{value}</div>'
            f'{delta_html}'
            f'</div>'
        )
    st.markdown(f'<div class="readout-row">{cards}</div>', unsafe_allow_html=True)


def stage_strip(stages):
    nodes = ""
    for i, name in enumerate(stages, start=1):
        nodes += (
            f'<div class="stage-node">'
            f'<div class="stage-dot"></div>'
            f'<div class="stage-label"><span class="stage-num">{i:02d}</span>{name}</div>'
            f'</div>'
        )
        if i < len(stages):
            nodes += '<div class="stage-line"></div>'
    st.markdown(f'<div class="stage-strip">{nodes}</div>', unsafe_allow_html=True)


def style_fig(fig, height=350, **layout_kwargs):
    fig.update_layout(**PLOTLY_LAYOUT, height=height)
    fig.update_layout(**layout_kwargs)
    return fig


inject_css()

# =============================================================================
# SIDEBAR
# =============================================================================
st.sidebar.markdown(
    f'<div style="font-family:{FONT_MONO};font-weight:700;font-size:1.05rem;color:{TEXT};'
    f'letter-spacing:0.04em;">🛰️ MISSION CONSOLE</div>'
    f'<div style="font-family:{FONT_MONO};font-size:0.7rem;color:{TEXT_MUTED};'
    f'letter-spacing:0.06em;margin-bottom:1rem;">MOST VISITED PAGES FINDER</div>',
    unsafe_allow_html=True,
)

st.sidebar.markdown('<div class="console-eyebrow">// Source</div>', unsafe_allow_html=True)
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

st.sidebar.markdown('<div class="console-eyebrow" style="margin-top:1rem;">// Settings</div>', unsafe_allow_html=True)
top_n = st.sidebar.slider("Number of top pages to show", min_value=5, max_value=30, value=10)

st.sidebar.markdown("---")
st.sidebar.caption("Guided by Binju Saju · CSE-DS · 2024-28")
st.sidebar.caption("Amruth Krishnan J · Chrison Roy · Rithin Ratheesh")

# =============================================================================
# HERO HEADER + SIGNATURE STAGE STRIP
# =============================================================================
st.markdown('<div class="console-hero-eyebrow">Web Usage Mining · Session Log Analysis</div>', unsafe_allow_html=True)
st.markdown('<div class="console-hero-title">MOST VISITED PAGES FINDER</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="console-hero-sub">Identifying and ranking frequently accessed webpages from web server access logs</div>',
    unsafe_allow_html=True,
)

if log_path is None or not os.path.exists(log_path):
    st.info("👈 Choose or upload an access log from the sidebar to get started.")
    st.stop()

stage_strip(["Collect", "Preprocess", "Clean", "Store", "Analyze", "Rank"])


@st.cache_data(show_spinner=False)
def run_full_pipeline(path):
    records, n_malformed = parse_log_file(path)
    cleaned, stats = clean_records(records)
    df = to_dataframe(cleaned)
    counter = frequency_analysis(df)
    ranked = counter.most_common()  # full ranking, every page -- not limited to Top-N
    full_ranked_df = pd.DataFrame(ranked, columns=["Page URL", "Visits"])
    full_ranked_df.insert(0, "Rank", range(1, len(full_ranked_df) + 1))
    stats["raw_lines_parsed"] = len(records)
    stats["malformed_lines_discarded"] = n_malformed
    stats["unique_pages"] = len(counter)
    return stats, full_ranked_df, df


with st.spinner("Running the six-stage pipeline..."):
    stats, full_ranked_df, df = run_full_pipeline(log_path)

report_df = full_ranked_df.head(top_n).reset_index(drop=True)

# =============================================================================
# KPI READOUTS
# =============================================================================
eyebrow_heading("// 01\u201303", "Pipeline Overview")
readout_row([
    ("Collected", f"{stats['raw_lines_parsed'] + stats['malformed_lines_discarded']:,}", None),
    ("Parsed OK", f"{stats['raw_lines_parsed']:,}", f"-{stats['malformed_lines_discarded']} malformed"),
    ("After Bot Filter", f"{stats['after_removing_bots']:,}", None),
    ("After De-dup", f"{stats['after_removing_duplicates']:,}", None),
    ("After 2xx Filter", f"{stats['after_keeping_2xx_only']:,}", None),
    ("Unique Pages", f"{stats['unique_pages']:,}", None),
])

funnel_df = pd.DataFrame({
    "Stage": ["Parsed", "After bot removal", "After de-duplication", "After 2xx filter"],
    "Records": [
        stats["raw_lines_parsed"],
        stats["after_removing_bots"],
        stats["after_removing_duplicates"],
        stats["after_keeping_2xx_only"],
    ],
})
fig_funnel = px.funnel(funnel_df, x="Records", y="Stage", color_discrete_sequence=[ACCENT])
style_fig(fig_funnel, height=280, title="Data Cleaning Funnel")
st.plotly_chart(fig_funnel, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# RANKING & FREQUENCY CHART
# =============================================================================
left, right = st.columns([2, 3])

with left:
    eyebrow_heading("// 05\u201306", f"Top {top_n} Pages")
    st.dataframe(report_df, use_container_width=True, hide_index=True)
    csv_bytes = report_df.to_csv(index=False).encode("utf-8")
    st.download_button("\u2193 DOWNLOAD REPORT (CSV)", csv_bytes, "top_pages.csv", "text/csv")

with right:
    eyebrow_heading("// 06", "Visit Frequency")
    fig_bar = px.bar(
        report_df.sort_values("Visits"),
        x="Visits",
        y="Page URL",
        orientation="h",
        color="Visits",
        color_continuous_scale=AMBER_SCALE,
        text="Visits",
    )
    style_fig(fig_bar, height=420, coloraxis_showscale=False)
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# PAGE LOOKUP -- search any URL for its rank & visit count (not limited to Top-N)
# =============================================================================
eyebrow_heading("// Lookup", "Check a Specific Page")
st.caption("Search for any page path to see its rank and visit count, even if it falls outside the Top-N shown above.")

query = st.text_input(
    "Search",
    placeholder="e.g. /shuttle/countdown/ or apollo",
    label_visibility="collapsed",
)

if query.strip():
    matches = full_ranked_df[full_ranked_df["Page URL"].str.contains(query.strip(), case=False, na=False, regex=False)]
    total_pages = len(full_ranked_df)

    if matches.empty:
        st.markdown(
            f'<div class="readout-card" style="border-left-color:{TEXT_MUTED};">'
            f'<div class="readout-label">No match</div>'
            f'<div class="readout-value" style="font-size:1rem;">No page URL contains "{query.strip()}"</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        for _, row in matches.head(10).iterrows():
            in_top_n = row["Rank"] <= top_n
            badge_color = ACCENT_2 if in_top_n else TEXT_MUTED
            badge_text = f"IN TOP {top_n}" if in_top_n else "OUTSIDE CURRENT TOP-N"
            percentile = 100 * (1 - (row["Rank"] - 1) / total_pages)
            st.markdown(
                f'<div class="readout-card" style="border-left-color:{ACCENT};margin-bottom:0.6rem;">'
                f'<div class="readout-label">{row["Page URL"]}</div>'
                f'<div class="readout-value">Rank #{row["Rank"]} of {total_pages} &nbsp;·&nbsp; {row["Visits"]:,} visits</div>'
                f'<div class="readout-delta" style="color:{badge_color};">{badge_text} &nbsp;·&nbsp; top {percentile:.0f}% of all pages</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        if len(matches) > 10:
            st.caption(f"Showing 10 of {len(matches)} matching pages -- refine your search to narrow further.")

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# STATUS CODE BREAKDOWN & REQUESTS OVER TIME
# =============================================================================
c1, c2 = st.columns(2)

with c1:
    eyebrow_heading("// Telemetry", "HTTP Status Code Breakdown")
    if not df.empty:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status Code", "Count"]
        fig_status = px.pie(
            status_counts, names="Status Code", values="Count", hole=0.55,
            color_discrete_sequence=[ACCENT, ACCENT_2, "#6B8CFF", "#FF6B6B", "#B98BFF"],
        )
        style_fig(fig_status, height=340)
        st.plotly_chart(fig_status, use_container_width=True)

with c2:
    eyebrow_heading("// Telemetry", "Requests Over Time")
    if not df.empty and df["timestamp"].notna().any():
        ts = df.dropna(subset=["timestamp"]).set_index("timestamp").resample("1h").size().reset_index()
        ts.columns = ["Time", "Requests"]
        fig_ts = px.line(ts, x="Time", y="Requests", color_discrete_sequence=[ACCENT_2])
        style_fig(fig_ts, height=340)
        fig_ts.update_traces(line=dict(width=2))
        st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.caption("No parsable timestamps to plot.")

st.markdown("<br>", unsafe_allow_html=True)

# =============================================================================
# TIME-BASED ANALYSIS: WHEN IS THE SITE BUSIEST?
# =============================================================================
eyebrow_heading("// Temporal Patterns", "Time-Based Analysis")
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

    readout_row([
        ("Busiest Hour", f"{busiest_hour:02d}:00\u2013{busiest_hour:02d}:59", f"{busiest_hour_count:,} requests"),
        ("Busiest Day", busiest_day, f"{busiest_day_count:,} requests"),
    ])

    t1, t2 = st.columns(2)
    with t1:
        fig_hour = px.bar(hourly, x="Hour", y="Requests", color="Requests", color_continuous_scale=AMBER_SCALE)
        style_fig(fig_hour, height=360, title="Requests by Hour of Day", coloraxis_showscale=False)
        fig_hour.update_xaxes(dtick=1)
        st.plotly_chart(fig_hour, use_container_width=True)
    with t2:
        fig_day = px.bar(daily, x="Day", y="Requests", color="Requests", color_continuous_scale=TEAL_SCALE)
        style_fig(fig_day, height=360, title="Requests by Day of Week", coloraxis_showscale=False)
        st.plotly_chart(fig_day, use_container_width=True)
else:
    st.caption("No parsable timestamps available for time-based analysis.")

# Clean up temp upload
if tmp_file is not None:
    try:
        os.unlink(tmp_file.name)
    except OSError:
        pass
