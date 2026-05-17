import streamlit as st
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. THE RE-OPTIMIZED CORE PHYSICS ENGINE ---
class SolarPVArray:
    def __init__(self, p_nom, alpha=-0.004):
        self.p_nom = p_nom
        self.alpha = alpha

    def get_power(self, g, t_c):
        return max(0, self.p_nom * (g / 1000) * (1 + self.alpha * (t_c - 25)))

class BatteryStorage:
    def __init__(self, capacity_wh):
        self.capacity_wh = capacity_wh
        self.current_charge_wh = capacity_wh * 0.3  # Starts at 30% baseline buffer

    def charge(self, power_in):
        self.current_charge_wh = min(self.capacity_wh, self.current_charge_wh + power_in)

    def discharge(self, power_needed):
        provided = min(power_needed, self.current_charge_wh)
        self.current_charge_wh -= provided
        return provided

# --- 2. PREMIUM HIGH-CONTRAST DASHBOARD ---
st.set_page_config(page_title="AI Smart Microgrid Optimization", layout="wide")

# High-contrast UI theme for extreme text and graph visibility
st.markdown("""
    <style>
    div[data-testid="stMetricValue"] {
        color: #00ff88 !important;
        font-weight: 700 !important;
        font-size: 2.2rem !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
    }
    div[data-testid="stMetric"] {
        background-color: #1e2630 !important;
        padding: 20px !important;
        border-radius: 12px !important;
        border: 2px solid #343d4c !important;
        box-shadow: 0 6px 12px rgba(0,0,0,0.4) !important;
    }
    h1 { color: #ffffff !important; font-weight: 700 !important; }
    p, span { color: #cbd5e1 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚡ AI-Driven Smart Microgrid Dashboard")
st.markdown("### Predictive Orchestration Engine utilizing Machine Learning heuristics for optimal power flow.")

# Sidebar Control Panel
st.sidebar.header("⚙️ Grid Parameters")
sol_cap = st.sidebar.slider("Solar PV Capacity (Watts)", 1000, 10000, 5000, 500)
bat_cap = st.sidebar.slider("Battery Storage Capacity (Wh)", 2000, 20000, 10000, 1000)

@st.cache_data 
def fetch_grid_weather(lat, lon):
    res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,shortwave_radiation&timezone=auto&forecast_days=2").json()
    return (np.array(res['hourly']['shortwave_radiation'][:24]), np.array(res['hourly']['temperature_2m'][:24]),
            np.array(res['hourly']['shortwave_radiation'][24:48]), np.array(res['hourly']['temperature_2m'][24:48]))

# Live data for Kolkata Region
g_today, t_today, g_tomorrow, t_tomorrow = fetch_grid_weather(22.5726, 88.3639)

# --- 3. DYNAMIC PREDICTIVE AI LOGIC ---
nominal_daily_generation = sol_cap * 5
total_solar_today = sum([SolarPVArray(sol_cap).get_power(g_today[i], t_today[i]) for i in range(24)])
predicted_tomorrow_solar = sum([SolarPVArray(sol_cap).get_power(g_tomorrow[i], t_tomorrow[i]) for i in range(24)])

# AI optimization threshold adjustments
if predicted_tomorrow_solar < (0.4 * nominal_daily_generation):
    ai_report = "Aggressive Conservation Mode Activated"
    target_h2_power = 1200  # Throttled operation to safeguard the grid buffer
    status_color = "orange"
else:
    ai_report = "Optimal Dispatch System Running"
    target_h2_power = 2400  # Standard continuous load allocation
    status_color = "green"

# Simulation Variables
bat = BatteryStorage(bat_cap)
logs = {"solar": [], "h2": [], "bat": []}

# Power Routing Simulation Loop
for i in range(24):
    p_sun = SolarPVArray(sol_cap).get_power(g_today[i], t_today[i])
    logs["solar"].append(p_sun)
    
    # Priority 1: Meet target industrial load directly from solar or battery asset
    available_power = p_sun
    p_h2_actual = 0
    
    if available_power >= target_h2_power:
        p_h2_actual = target_h2_power
        available_power -= target_h2_power
    else:
        # Solar deficit, draw remaining dispatch from battery buffer
        deficit = target_h2_power - available_power
        battery_support = bat.discharge(deficit)
        p_h2_actual = available_power + battery_support
        available_power = 0
        
    logs["h2"].append(p_h2_actual)
    
    # Priority 2: Charge excess remaining solar power into battery storage
    if available_power > 0:
        bat.charge(available_power)
    logs["bat"].append(bat.current_charge_wh)

# Commodity Mass Calculation (Faraday Equivalent Conversion Metric)
total_h2_kg = sum(logs["h2"]) * 0.000268 

# Render High Contrast Performance Metrics
st.markdown("<br>", unsafe_allow_html=True)
c1, c2 = st.columns(2)
c1.metric("🔮 Tomorrow's AI Prediction Report", ai_report)
c2.metric("🔋 Total Green Hydrogen Produced Today", f"{total_h2_kg:.3f} kg")
st.markdown("<br>", unsafe_allow_html=True)

# --- 4. THE INDUSTRIAL DUAL-AXIS GRAPH (CLEAN & FILL DESIGN) ---
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Left Axis (Power): Solar and Hydrogen Curves
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["solar"], name="Raw Solar Power (W)", line=dict(color='#FFA500', width=3, dash='dash')), secondary_y=False)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["h2"], name=f"AI Managed Power ({target_h2_power} W Target)", fill='tozeroy', line=dict(color='#00FF88', width=3), fillcolor='rgba(0, 255, 136, 0.15)'), secondary_y=False)

# Right Axis (Energy): Independent Battery Scaling (Clean area fill)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["bat"], name="Battery Charge Level (Wh)", line=dict(color='#BF40BF', width=4), fill='tozeroy', fillcolor='rgba(191, 64, 191, 0.08)'), secondary_y=True)

# Design layout adjustments for extreme scannability
fig.update_layout(
    title=dict(text="⚡ 24-Hour Microgrid Power & Storage Performance Mapping", font=dict(size=18, color='#ffffff')),
    template="plotly_dark", 
    height=550, 
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=60, r=60, t=80, b=60),
    plot_bgcolor='#0e1117',
    paper_bgcolor='#0e1117'
)

fig.update_yaxes(title_text="<b>Power / Energy Flow Rate (Watts)</b>", title_font=dict(color="#FFA500"), secondary_y=False, gridcolor='rgba(255,255,255,0.05)')
fig.update_yaxes(title_text="<b>Battery Storage Balance (Watt-Hours)</b>", title_font=dict(color="#BF40BF"), secondary_y=True, gridcolor='rgba(255,255,255,0.05)', range=[0, bat_cap * 1.1])
fig.update_xaxes(title_text="Hour of the Day", tickmode='linear', tick0=0, dtick=1, gridcolor='rgba(255,255,255,0.05)')

st.plotly_chart(fig, use_container_width=True)

# Sidebar HUD Status Alerts
st.sidebar.markdown("---")
st.sidebar.subheader("📢 Diagnostics HUD")
if ai_report == "Optimal Dispatch System Running":
    st.sidebar.success("🟢 System Stable. Tomorrow's solar irradiance projections allow full operations.", icon="⚙️")
else:
    st.sidebar.warning("⚠️ High Cloud Cover Forecasted. AI throttling production constraints to lock storage buffer.", icon="⏳")
