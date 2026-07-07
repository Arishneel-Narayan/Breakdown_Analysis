import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- 1. SETUP & DATA LOADING ---
st.set_page_config(page_title="Breakdown Analysis Dashboard", layout="wide")

@st.cache_data
def load_data(file_path):
    df = pd.read_csv(file_path)
    # Clean and format data
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
    df['Duration (mins)'] = pd.to_numeric(df['Duration (mins)'], errors='coerce').fillna(0)
    return df

# Initialize data (Replace with your actual file path)
try:
    df = load_data('breakdown_data.csv')
except FileNotFoundError:
    st.error("Data file 'breakdown_data.csv' not found. Please ensure it is in the directory.")
    st.stop()

# --- 2. SIDEBAR FILTERING ---
st.sidebar.header("Dashboard Filters")
entity_list = ["All"] + df['Entity'].dropna().unique().tolist()
selected_entity = st.sidebar.selectbox("Select Entity", entity_list)

if selected_entity != "All":
    filtered_df = df[df['Entity'] == selected_entity]
else:
    filtered_df = df.copy()

st.title("🏭 Plant Breakdown & Downtime Analysis")

# --- 3. KPIs ---
col1, col2, col3 = st.columns(3)
total_downtime = filtered_df['Duration (mins)'].sum()
total_incidents = len(filtered_df)
avg_downtime = total_downtime / total_incidents if total_incidents > 0 else 0

col1.metric("Total Downtime (mins)", f"{total_downtime:,.0f}")
col2.metric("Total Breakdown Incidents", f"{total_incidents}")
col3.metric("Avg Duration per Incident", f"{avg_downtime:,.1f} mins")
st.markdown("---")

# --- 4. PARETO ANALYSIS ---
st.subheader("Pareto Analysis by Process")

# Pareto Calculation
pareto_df = filtered_df.groupby('Process')['Duration (mins)'].sum().reset_index()
pareto_df = pareto_df.sort_values(by='Duration (mins)', ascending=False)
pareto_df['Cumulative Percentage'] = 100 * pareto_df['Duration (mins)'].cumsum() / pareto_df['Duration (mins)'].sum()

# Pareto Chart Generation
fig_pareto = go.Figure()
fig_pareto.add_trace(go.Bar(
    x=pareto_df['Process'], 
    y=pareto_df['Duration (mins)'],
    name='Downtime (mins)',
    marker_color='steelblue'
))
fig_pareto.add_trace(go.Scatter(
    x=pareto_df['Process'], 
    y=pareto_df['Cumulative Percentage'],
    name='Cumulative %',
    yaxis='y2',
    mode='lines+markers',
    line=dict(color='red', width=2)
))
fig_pareto.update_layout(
    yaxis=dict(title='Duration (mins)'),
    yaxis2=dict(title='Cumulative %', overlaying='y', side='right', range=[0, 105]),
    hovermode='x unified',
    margin=dict(l=0, r=0, t=30, b=0)
)
st.plotly_chart(fig_pareto, use_container_width=True)

st.markdown("""
**Purpose and Insights:**
* **Identify Critical Bottlenecks:** Highlights the 20% of processes causing 80% of your total downtime.
* **Resource Allocation:** Directs maintenance teams to focus on the highest-impact processes first (the tallest bars on the left).
* **ROI Justification:** Provides quantitative backing for requesting capital expenditure to upgrade specific problematic machine centers.
""")
st.markdown("---")

# --- 5. DOWNTIME TRENDS ---
st.subheader("Downtime Trend Analysis")

# Trend Calculation
trend_df = filtered_df.groupby('Date')['Duration (mins)'].sum().reset_index()
trend_df = trend_df.sort_values('Date')

# Trend Chart Generation
fig_trend = px.line(
    trend_df, x='Date', y='Duration (mins)', 
    markers=True, 
    line_shape='spline',
    title="Daily Total Downtime"
)
fig_trend.update_traces(line_color='darkorange')
st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("""
**Purpose and Insights:**
* **Monitor Stability:** Shows whether plant reliability is improving or degrading over time.
* **Identify Patterns:** Helps spot cyclical breakdown trends (e.g., higher breakdown rates following a specific shift schedule or raw material batch change).
* **Evaluate Interventions:** Allows you to see if recent preventive maintenance or process optimizations successfully reduced daily downtime spikes.
""")
st.markdown("---")

# --- 6. CATEGORICAL BREAKDOWN ---
st.subheader("Root Cause Category Distribution")

# Category Calculation
cat_df = filtered_df.groupby('Category')['Duration (mins)'].sum().reset_index()

# Category Chart Generation
fig_cat = px.pie(
    cat_df, values='Duration (mins)', names='Category', hole=0.4,
    color_discrete_sequence=px.colors.sequential.Teal
)
fig_cat.update_traces(textposition='inside', textinfo='percent+label')
st.plotly_chart(fig_cat, use_container_width=True)

st.markdown("""
**Purpose and Insights:**
* **Skill Gap Identification:** Reveals if the majority of issues are Electrical vs. Mechanical, dictating which type of specialized technician is needed on shift.
* **Maintenance Strategy:** A high percentage of mechanical issues might indicate a lack of lubrication or worn parts (predictive maintenance needed), while electrical issues might point to sensor failures or power quality problems.
""")
