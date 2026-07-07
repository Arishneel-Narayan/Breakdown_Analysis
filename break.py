import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- SETUP & DATA LOADING ---
st.set_page_config(page_title="Breakdown Analysis Dashboard", layout="wide")

@st.cache_data
def load_data(file):
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    elif file.name.endswith(('.xls', '.xlsx')):
        df = pd.read_excel(file)
    else:
        st.error("Unsupported file format.")
        st.stop()
        
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Duration (mins)'] = pd.to_numeric(df['Duration (mins)'], errors='coerce').fillna(0)
    return df

# --- FILE UPLOAD ---
st.sidebar.header("Data Input")
uploaded_file = st.sidebar.file_uploader("Upload Breakdown Data", type=['csv', 'xlsx', 'xls'])

if uploaded_file is None:
    st.info("Please upload a data file (CSV or Excel) to generate the dashboard.")
    st.stop()

df = load_data(uploaded_file)
entity_list = ["All"] + df['Entity'].dropna().unique().tolist()

st.title("🏭 Plant Breakdown & Downtime Analysis")

# --- GLOBAL DATE FILTER (TOP) ---
st.markdown("### Report Parameters")
min_date = df['Date'].min().date()
max_date = df['Date'].max().date()

date_range = st.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

if len(date_range) == 2:
    start_date, end_date = date_range
    mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
    base_df = df.loc[mask]
else:
    base_df = df.copy()

st.markdown("---")

# --- KPIs ---
col1, col2, col3 = st.columns(3)
total_downtime_mins = base_df['Duration (mins)'].sum()
total_downtime_hours = total_downtime_mins / 60
total_incidents = len(base_df)
avg_downtime_mins = total_downtime_mins / total_incidents if total_incidents > 0 else 0

col1.metric("Total Downtime (Hours)", f"{total_downtime_hours:,.1f}")
col2.metric("Total Breakdown Incidents", f"{total_incidents}")
col3.metric("Avg Duration per Incident", f"{avg_downtime_mins:,.1f} mins")
st.markdown("---")

# --- PARETO ANALYSIS ---
st.subheader("Pareto Analysis by Process")
pareto_container = st.empty()
pareto_entity = st.selectbox("Filter Entity for Pareto Chart:", entity_list, key="pareto_entity")

pareto_df = base_df if pareto_entity == "All" else base_df[base_df['Entity'] == pareto_entity]
p_calc_df = pareto_df.groupby('Process')['Duration (mins)'].sum().reset_index()
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
pareto_container.plotly_chart(fig_pareto, use_container_width=True)

st.markdown("""
**Purpose and Insights:**
* **Identify Critical Bottlenecks:** Highlights the 20% of processes causing 80% of total downtime.
* **Resource Allocation:** Directs maintenance teams to focus on the highest-impact processes first.
* **ROI Justification:** Provides quantitative backing for requesting capital expenditure to upgrade specific problematic machine centers.
""")
st.markdown("---")

# --- DOWNTIME TRENDS ---
st.subheader("Downtime Trend Analysis")
trend_container = st.empty()
trend_entity = st.selectbox("Filter Entity for Trend Chart:", entity_list, key="trend_entity")

trend_df_filtered = base_df if trend_entity == "All" else base_df[base_df['Entity'] == trend_entity]
trend_calc_df = trend_df_filtered.groupby('Date')['Duration (mins)'].sum().reset_index().sort_values('Date')

fig_trend = px.line(
    trend_calc_df, x='Date', y='Duration (mins)', 
    markers=True, line_shape='spline'
)
fig_trend.update_traces(line_color='#009688', line_width=3, marker=dict(size=8))
fig_trend.update_layout(margin=dict(l=0, r=0, t=30, b=0))
trend_container.plotly_chart(fig_trend, use_container_width=True)

st.markdown("""
**Purpose and Insights:**
* **Monitor Stability:** Shows whether plant reliability is improving or degrading over time.
* **Identify Patterns:** Helps spot cyclical breakdown trends regarding operating schedules.
* **Evaluate Interventions:** Allows evaluation of whether recent preventive maintenance optimizations successfully reduced daily downtime spikes.
""")
st.markdown("---")

# --- CATEGORICAL BREAKDOWN ---
st.subheader("Root Cause Category Distribution")
cat_container = st.empty()
cat_entity = st.selectbox("Filter Entity for Category Chart:", entity_list, key="cat_entity")

cat_df_filtered = base_df if cat_entity == "All" else base_df[base_df['Entity'] == cat_entity]
cat_calc_df = cat_df_filtered.groupby('Category')['Duration (mins)'].sum().reset_index()

fig_cat = px.pie(
    cat_calc_df, values='Duration (mins)', names='Category', hole=0.4,
    color_discrete_sequence=px.colors.qualitative.Safe
)
fig_cat.update_traces(textposition='inside', textinfo='percent+label')
fig_cat.update_layout(margin=dict(l=0, r=0, t=30, b=0))
cat_container.plotly_chart(fig_cat, use_container_width=True)

st.markdown("""
**Purpose and Insights:**
* **Skill Gap Identification:** Reveals if the majority of issues are Electrical vs. Mechanical, dictating which type of specialized technician is required on shift.
* **Maintenance Strategy:** A high percentage of mechanical issues indicates a potential lack of lubrication or worn parts, while electrical issues point to sensor failures or power quality problems.
""")
