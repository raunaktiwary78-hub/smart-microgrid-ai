import streamlit as st
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. THE PHYSICS ENGINE ---
class SolarPVArray:
    def __init__(self, p_nom, alpha=-0.004):
        self.p_nom = p_nom
        self.alpha = alpha

    def get_power(self, g, t_c):
        return max(0, self.p_nom * (g / 1000) * (1 + self.alpha * (t_c - 25)))

class BatteryStorage:
    def __init__(self, capacity_wh):
        self.capacity_wh = capacity_wh
        self.current_charge_wh = capacity_wh * 0.4

    def charge(self, power_in):
        self.current_charge_wh = min(self.capacity_wh, self.current_charge_wh + power_in)

    def discharge(self, power_needed):
        provided = min(power_needed, self.current_charge_wh)
        self.current_charge_wh -= provided
        return provided

# --- 2. DASHBOARD SETUP ---
st.set_page_config(page_title="Microgrid AI v2.0", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: white; }
    .stMetric { background-color: #1a1c24; padding: 15px; border-radius: 10px; border-left: 5px solid #00d2ff; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏥 Smart Microgrid AI: Version 2.0 Elite")
st.caption("Advanced Predictive Orchestration for Rural Healthcare Resiliency")

# Sidebar
st.sidebar.header("🕹️ Control Panel")
sol_cap = st.sidebar.slider("Solar PV Capacity (W)", 2000, 15000, 7000)
bat_cap = st.sidebar.slider("Battery Energy (Wh)", 5000, 30000, 15000)
med_load = 600 # Fixed Medical Load

@st.cache_data 
def fetch_data(lat, lon):
    res = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,shortwave_radiation&timezone=auto&forecast_days=2").json()
    return (np.array(res['hourly']['shortwave_radiation'][:24]), np.array(res['hourly']['temperature_2m'][:24]),
            np.array(res['hourly']['shortwave_radiation'][24:48]), np.array(res['hourly']['temperature_2m'][24:48]))

g_today, t_today, g_tomorrow, t_tomorrow = fetch_data(22.57, 88.36)

# --- 3. AI ORCHESTRATION ---
solar_today = sum([SolarPVArray(sol_cap).get_power(g_today[i], t_today[i]) for i in range(24)])
solar_tmrw = sum([SolarPVArray(sol_cap).get_power(g_tomorrow[i], t_tomorrow[i]) for i in range(24)])

if solar_tmrw < 0.3 * (sol_cap * 5):
    ai_mode, target_h2, status_color = "CRITICAL: EMERGENCY", 0, "red"
elif solar_tmrw < 0.6 * (sol_cap * 5):
    ai_mode, target_h2, status_color = "WARNING: CONSERVE", 800, "orange"
else:
    ai_mode, target_h2, status_color = "HEALTHY: OPTIMAL", 2800, "green"

# Simulation
bat = BatteryStorage(bat_cap)
logs = {"solar": [], "med": [], "h2": [], "bat": []}

for i in range(24):
    p_sun = SolarPVArray(sol_cap).get_power(g_today[i], t_today[i])
    logs["solar"].append(p_sun)
    
    # Priority 1: Clinic
    if p_sun >= med_load:
        logs["med"].append(med_load)
        p_sun -= med_load
    else:
        logs["med"].append(p_sun + bat.discharge(med_load - p_sun))
        p_sun = 0
        
    # Priority 2: Industry (Hydrogen)
    p_h2 = min(p_sun, target_h2) if ai_mode != "CRITICAL: EMERGENCY" else 0
    logs["h2"].append(p_h2)
    p_sun -= p_h2
    
    # Priority 3: Battery
    if p_sun > 0: bat.charge(p_sun)
    logs["bat"].append(bat.current_charge_wh)

# --- 4. INTERACTIVE VISUALIZATION (Plotly) ---
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Primary Axis: Power (W)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["solar"], name="Solar Generation (W)", line=dict(color='#FFD700', dash='dash')), secondary_y=False)
fig.add_trace(go.Bar(x=list(range(24)), y=logs["med"], name="Medical Clinic Load (W)", marker_color='#FF4B4B', opacity=0.7), secondary_y=False)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["h2"], name="Hydrogen Load (W)", fill='tozeroy', line=dict(color='#00FF88')), secondary_y=False)

# Secondary Axis: Energy (Wh)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["bat"], name="Battery State (Wh)", line=dict(color='#BF40BF', width=3)), secondary_y=True)

fig.update_layout(title="24-Hour Energy Balance Hub (Elite v2.0)", template="plotly_dark", height=600, hovermode="x unified")
fig.update_yaxes(title_text="Power Demand (Watts)", secondary_y=False)
fig.update_yaxes(title_text="Energy Storage (Watt-Hours)", secondary_y=True)

# Metrics
c1, c2, c3 = st.columns(3)
c1.metric("AI Strategy Mode", ai_mode)
c2.metric("System Health", "STABLE" if logs["med"].count(med_load) == 24 else "RISK")
c3.metric("Green Hydrogen Produced", f"{sum(logs['h2'])*0.00002:.3f} kg")

st.plotly_chart(fig, use_container_width=True)
st.sidebar.markdown(f"<div style='color:{status_color}; font-weight:bold; border:1px solid {status_color}; padding:10px;'>{ai_mode}</div>", unsafe_allow_html=True)
