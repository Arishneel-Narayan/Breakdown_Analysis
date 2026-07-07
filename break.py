import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import base64
import io
from weasyprint import HTML

import matplotlib
matplotlib.use("Agg")  # headless backend, no display/subprocess needed
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# --- 1. SETUP & DATA LOADING ---
st.set_page_config(page_title="Breakdown Analysis Dashboard", layout="wide")

@st.cache_data
def load_data(file):
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    elif file.name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file)
    else:
        st.error("Unsupported file format. Please upload a CSV or Excel file.")
        st.stop()

    # Drop fully blank rows (common with trailing empty rows in Excel exports)
    df = df.dropna(how='all')

    # Clean up text columns: strip stray whitespace and normalize missing values
    # so " Electrical" and "Electrical" aren't treated as different categories,
    # and blank cells don't get read back in as the literal string "nan"
    for col in ['Entity', 'Process', 'Category']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace({'nan': pd.NA, 'None': pd.NA, '': pd.NA})

    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Duration (mins)'] = pd.to_numeric(df['Duration (mins)'], errors='coerce')

    # A row missing any of these fields isn't a usable breakdown record —
    # drop it instead of silently filling it with 0, which was creating
    # fake zero-duration "incidents" (e.g. the "nan - nan" rows)
    required_cols = [c for c in ['Date', 'Process', 'Category', 'Duration (mins)'] if c in df.columns]
    rows_before = len(df)
    df = df.dropna(subset=required_cols)
    dropped = rows_before - len(df)

    df = df.reset_index(drop=True)
    if dropped > 0:
        st.sidebar.caption(f"Cleaned data: removed {dropped} incomplete row(s).")

    return df

# --- 2. SIDEBAR: FILE UPLOAD ONLY ---
st.sidebar.header("Data Input")
uploaded_file = st.sidebar.file_uploader("Upload Breakdown Data", type=['csv', 'xlsx', 'xls'])

if uploaded_file is None:
    st.info("Please upload a data file (CSV or Excel) to generate the dashboard.")
    st.stop()

df = load_data(uploaded_file)
entity_list = ["All"] + sorted(df['Entity'].dropna().unique().tolist())

st.title("🏭 Plant Breakdown & Downtime Analysis")

# --- 3. GLOBAL FILTERS (MAIN AREA, NOT SIDEBAR) ---
st.markdown("### Report Parameters")
min_date = df['Date'].min().date()
max_date = df['Date'].max().date()

filter_col1, filter_col2 = st.columns([2, 1])

with filter_col1:
    date_range = st.date_input(
        "Select Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY"
    )

with filter_col2:
    selected_entity = st.selectbox("Filter Entity (applies to everything below)", entity_list, key="global_entity")

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

date_mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
base_df = df.loc[date_mask]

if selected_entity != "All":
    base_df = base_df[base_df['Entity'] == selected_entity]

start_date_str = pd.Timestamp(start_date).strftime('%d/%m/%Y')
end_date_str = pd.Timestamp(end_date).strftime('%d/%m/%Y')

# --- 4. FAST CHART RENDERING (matplotlib, no subprocess) ---
PALETTE = ["#005B96", "#FF9800", "#009688", "#8E44AD", "#E74C3C", "#2ECC71", "#95A5A6"]

def render_pie_png(cat_df):
    fig, ax = plt.subplots(figsize=(4, 3.5), dpi=150)
    ax.pie(
        cat_df['Duration (mins)'],
        labels=cat_df['Category'],
        autopct='%1.0f%%',
        pctdistance=0.8,
        colors=PALETTE,
        wedgeprops=dict(width=0.4)
    )
    ax.set_aspect('equal')
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

def render_trend_png(trend_df):
    fig, ax = plt.subplots(figsize=(8, 2.5), dpi=150)
    ax.plot(trend_df['Date'], trend_df['Duration (mins)'], color='#009688', linewidth=2.5)
    ax.set_ylabel('Duration (mins)')
    ax.spines[['top', 'right']].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %d %B'))
    fig.autofmt_xdate()
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

# --- 5. PDF GENERATION LOGIC ---
def generate_pdf(filtered_df, start_d_str, end_d_str, entity_filter):
    tot_mins = filtered_df['Duration (mins)'].sum()
    tot_hrs = tot_mins / 60
    tot_inc = len(filtered_df)
    avg_dur = tot_mins / tot_inc if tot_inc > 0 else 0

    top_10 = filtered_df.sort_values(by='Duration (mins)', ascending=False).head(10)
    top_10_html = "".join([
        f"<tr><td>{i+1}</td><td>{row['Process']} - {row['Category']}</td><td>{row['Duration (mins)'] / 60:.1f}</td></tr>"
        for i, row in enumerate(top_10.to_dict('records'))
    ])

    cat_df = filtered_df.groupby('Category')['Duration (mins)'].sum().reset_index()
    pie_img = render_pie_png(cat_df)

    trend_df = filtered_df.groupby('Date')['Duration (mins)'].sum().reset_index().sort_values('Date')
    trend_img = render_trend_png(trend_df)

    html_template = f"""
    <html>
    <head>
    <style>
        @page {{ size: A4; margin: 15mm 15mm; }}
        body {{ font-family: 'Helvetica', sans-serif; color: #333; }}
        .header {{ text-align: center; border-bottom: 2px solid #005B96; padding-bottom: 10px; margin-bottom: 20px; }}
        table.layout {{ width: 100%; table-layout: fixed; margin-bottom: 20px; border-collapse: collapse; }}
        table.layout td {{ vertical-align: top; padding: 10px; }}
        .section-title {{ font-size: 14pt; color: #005B96; font-weight: bold; border-bottom: 1px solid #eee; margin-bottom: 10px; padding-bottom: 5px; }}
        .img-container {{ text-align: center; }}
        .data-table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
        .data-table th, .data-table td {{ border-bottom: 1px solid #eee; padding: 6px; text-align: left; }}
        .data-table th {{ background-color: #005B96; color: white; }}
        .stats-table {{ width: 100%; text-align: center; margin-top: 20px; border-collapse: separate; border-spacing: 10px 0; }}
        .stats-table td {{ border: 1px solid #ddd; padding: 15px; width: 33.33%; border-radius: 5px; background-color: #f9f9f9; }}
        .val {{ font-size: 18pt; font-weight: bold; color: #FF9800; display: block; margin-top: 5px; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1 style="color: #005B96; margin: 0; text-transform: uppercase;">Breakdown Analysis Report</h1>
            <p style="margin: 5px 0 0 0; color: #555;">Entity: {entity_filter} | Date Range: {start_d_str} to {end_d_str}</p>
        </div>
        <table class="layout">
            <tr>
                <td style="width: 45%; border-right: 1px solid #eee;">
                    <div class="section-title">Downtime Distribution</div>
                    <div class="img-container"><img src="data:image/png;base64,{pie_img}" style="max-width: 100%;"></div>
                </td>
                <td style="width: 55%;">
                    <div class="section-title">Top Breakdowns</div>
                    <table class="data-table">
                        <tr><th>Rank</th><th>Process</th><th>Hours</th></tr>
                        {top_10_html}
                    </table>
                </td>
            </tr>
        </table>
        <div class="section-title">Downtime Trend</div>
        <div class="img-container"><img src="data:image/png;base64,{trend_img}" style="max-width: 100%;"></div>
        <table class="stats-table">
            <tr>
                <td>Total Downtime (Hrs)<span class="val">{tot_hrs:,.1f}</span></td>
                <td>Total Incidents<span class="val">{tot_inc}</span></td>
                <td>Avg Duration (mins)<span class="val">{avg_dur:,.1f}</span></td>
            </tr>
        </table>
    </body>
    </html>
    """

    return HTML(string=html_template).write_pdf()

st.markdown("---")
if st.button("Generate 1-Pager PDF"):
    with st.spinner("Compiling report..."):
        pdf_bytes = generate_pdf(base_df, start_date_str, end_date_str, selected_entity)
        st.download_button(
            label="Download PDF",
            data=pdf_bytes,
            file_name="Breakdown_Report_1Pager.pdf",
            mime="application/pdf"
        )

st.markdown("---")

# --- 6. KPIs ---
col1, col2, col3 = st.columns(3)
total_downtime_mins = base_df['Duration (mins)'].sum()
total_downtime_hours = total_downtime_mins / 60
total_incidents = len(base_df)
avg_downtime_mins = total_downtime_mins / total_incidents if total_incidents > 0 else 0

col1.metric("Total Downtime (Hours)", f"{total_downtime_hours:,.1f}")
col2.metric("Total Breakdown Incidents", f"{total_incidents}")
col3.metric("Avg Duration per Incident", f"{avg_downtime_mins:,.1f} mins")
st.markdown("---")

# --- 7. PARETO ANALYSIS ---
st.subheader("Pareto Analysis by Process")

p_calc_df = base_df.groupby('Process')['Duration (mins)'].sum().reset_index()
p_calc_df = p_calc_df.sort_values(by='Duration (mins)', ascending=False)
p_calc_df['Cumulative Percentage'] = 100 * p_calc_df['Duration (mins)'].cumsum() / p_calc_df['Duration (mins)'].sum()

fig_pareto = go.Figure()
fig_pareto.add_trace(go.Bar(
    x=p_calc_df['Process'], y=p_calc_df['Duration (mins)'],
    name='Downtime (mins)', marker_color='#005B96'
))
fig_pareto.add_trace(go.Scatter(
    x=p_calc_df['Process'], y=p_calc_df['Cumulative Percentage'],
    name='Cumulative %', yaxis='y2', mode='lines+markers',
    line=dict(color='#FF9800', width=3)
))
fig_pareto.update_layout(
    yaxis=dict(title='Duration (mins)'),
    yaxis2=dict(title='Cumulative %', overlaying='y', side='right', range=[0, 105]),
    hovermode='x unified', margin=dict(l=0, r=0, t=30, b=0)
)
st.plotly_chart(fig_pareto, use_container_width=True)

st.markdown("""
**Purpose and Insights:**
* **Identify Critical Bottlenecks:** Highlights the 20% of processes causing 80% of total downtime.
* **Resource Allocation:** Directs maintenance teams to focus on the highest-impact processes first.
* **ROI Justification:** Provides quantitative backing for requesting capital expenditure to upgrade specific problematic machine centers.
""")
st.markdown("---")

# --- 8. DOWNTIME TRENDS ---
st.subheader("Downtime Trend Analysis")

trend_calc_df = base_df.groupby('Date')['Duration (mins)'].sum().reset_index().sort_values('Date')

fig_trend = px.line(
    trend_calc_df, x='Date', y='Duration (mins)',
    markers=True, line_shape='spline'
)
fig_trend.update_traces(line_color='#009688', line_width=3, marker=dict(size=8))
fig_trend.update_layout(margin=dict(l=0, r=0, t=30, b=0))
fig_trend.update_xaxes(tickformat="%a %d %B")
st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("""
**Purpose and Insights:**
* **Monitor Stability:** Shows whether plant reliability is improving or degrading over time.
* **Identify Patterns:** Helps spot cyclical breakdown trends regarding operating schedules.
* **Evaluate Interventions:** Allows evaluation of whether recent preventive maintenance optimizations successfully reduced daily downtime spikes.
""")
st.markdown("---")

# --- 9. CATEGORICAL BREAKDOWN ---
st.subheader("Root Cause Category Distribution")

cat_calc_df = base_df.groupby('Category')['Duration (mins)'].sum().reset_index()

fig_cat = px.pie(
    cat_calc_df, values='Duration (mins)', names='Category', hole=0.4,
    color_discrete_sequence=px.colors.qualitative.Safe
)
fig_cat.update_traces(textposition='inside', textinfo='percent+label')
fig_cat.update_layout(margin=dict(l=0, r=0, t=30, b=0))
st.plotly_chart(fig_cat, use_container_width=True)

st.markdown("""
**Purpose and Insights:**
* **Skill Gap Identification:** Reveals if the majority of issues are Electrical vs. Mechanical, dictating which type of specialized technician is required on shift.
* **Maintenance Strategy:** A high percentage of mechanical issues indicates a potential lack of lubrication or worn parts, while electrical issues point to sensor failures or power quality problems.
""")
