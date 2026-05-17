import streamlit as st
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. THE HYBRID PHYSICS ENGINE ---
class SolarPVArray:
    def __init__(self, p_nom, alpha=-0.004):
        self.p_nom = p_nom
        self.alpha = alpha

    def get_power(self, g, t_c):
        return max(0, self.p_nom * (g / 1000) * (1 + self.alpha * (t_c - 25)))

class WindTurbine:
    def __init__(self, p_rated, v_in=3.0, v_rated=12.0, v_out=25.0):
        self.p_rated = p_rated
        self.v_in = v_in      # Minimum speed to start generating
        self.v_rated = v_rated # Speed for maximum power
        self.v_out = v_out    # Maximum safe speed (cuts out after this)

    def get_power(self, v_wind, wind_dir):
        # Base power calculation using cubic approximation
        if v_wind < self.v_in or v_wind > self.v_out:
            p_base = 0
        elif self.v_in <= v_wind <= self.v_rated:
            # Power scales with the cube of the wind speed
            p_base = self.p_rated * ((v_wind**3 - self.v_in**3) / (self.v_rated**3 - self.v_in**3))
        else:
            p_base = self.p_rated
            
        # Directional Efficiency Penalty (Simulating Yaw mechanism delay/loss)
        # Assuming optimal facing is 180 degrees (South), penalty increases as wind shifts
        misalignment_angle = abs(180 - wind_dir)
        yaw_efficiency = max(0.85, 1 - (misalignment_angle * 0.001)) 
        
        return p_base * yaw_efficiency

class BatteryStorage:
    def __init__(self, capacity_wh):
        self.capacity_wh = capacity_wh
        self.current_charge_wh = capacity_wh * 0.3

    def charge(self, power_in):
        self.current_charge_wh = min(self.capacity_wh, self.current_charge_wh + power_in)

    def discharge(self, power_needed):
        provided = min(power_needed, self.current_charge_wh)
        self.current_charge_wh -= provided
        return provided

# --- 2. PREMIUM DASHBOARD UI ---
st.set_page_config(page_title="AI Hybrid Microgrid v3.0", layout="wide")

st.markdown("""
    <style>
    div[data-testid="stMetricValue"] { color: #00d2ff !important; font-weight: 700 !important; font-size: 2.2rem !important; }
    div[data-testid="stMetricLabel"] { color: #ffffff !important; font-weight: 600 !important; font-size: 1.1rem !important; }
    div[data-testid="stMetric"] { background-color: #1e2630 !important; padding: 20px !important; border-radius: 12px !important; border: 1px solid #343d4c !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🌪️ AI-Driven Hybrid Microgrid (Solar + Wind)")
st.markdown("### Multi-vector Energy Orchestration with Wind Speed & Yaw-Direction Physics")

# Sidebar
st.sidebar.header("⚙️ Grid Hardware")
sol_cap = st.sidebar.slider("Solar PV Capacity (W)", 1000, 10000, 5000, 500)
wind_cap = st.sidebar.slider("Wind Turbine Rated Power (W)", 1000, 10000, 4000, 500)
bat_cap = st.sidebar.slider("Battery Storage (Wh)", 2000, 20000, 10000, 1000)

@st.cache_data 
def fetch_hybrid_weather(lat, lon):
    # Added wind_speed_10m and wind_direction_10m to the API call
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,shortwave_radiation,wind_speed_10m,wind_direction_10m&wind_speed_unit=ms&timezone=auto&forecast_days=2"
    res = requests.get(url).json()
    h = res['hourly']
    return (np.array(h['shortwave_radiation'][:24]), np.array(h['temperature_2m'][:24]), 
            np.array(h['wind_speed_10m'][:24]), np.array(h['wind_direction_10m'][:24]),
            np.array(h['shortwave_radiation'][24:48]), np.array(h['temperature_2m'][24:48]),
            np.array(h['wind_speed_10m'][24:48]), np.array(h['wind_direction_10m'][24:48]))

# Kolkata Coordinates
g_today, t_today, w_spd_today, w_dir_today, g_tmrw, t_tmrw, w_spd_tmrw, w_dir_tmrw = fetch_hybrid_weather(22.57, 88.36)

# Initialize Hardware Models
solar_arr = SolarPVArray(sol_cap)
wind_turb = WindTurbine(wind_cap)
bat = BatteryStorage(bat_cap)

# --- 3. HYBRID AI ORCHESTRATION ---
energy_today = sum([solar_arr.get_power(g_today[i], t_today[i]) + wind_turb.get_power(w_spd_today[i], w_dir_today[i]) for i in range(24)])
energy_tmrw = sum([solar_arr.get_power(g_tmrw[i], t_tmrw[i]) + wind_turb.get_power(w_spd_tmrw[i], w_dir_tmrw[i]) for i in range(24)])
nominal_hybrid = (sol_cap * 5) + (wind_cap * 6) # Rough daily expectation

if energy_tmrw < (0.4 * nominal_hybrid):
    ai_mode = "CONSERVATION (Low Solar+Wind Tomorrow)"
    target_h2 = 1500
    color = "orange"
else:
    ai_mode = "MAXIMUM EXTRACTION (Optimal Weather)"
    target_h2 = 3500
    color = "green"

logs = {"solar": [], "wind": [], "total_gen": [], "h2": [], "bat": []}

for i in range(24):
    p_sun = solar_arr.get_power(g_today[i], t_today[i])
    p_wind = wind_turb.get_power(w_spd_today[i], w_dir_today[i])
    
    logs["solar"].append(p_sun)
    logs["wind"].append(p_wind)
    
    available = p_sun + p_wind
    logs["total_gen"].append(available)
    
    # AI Dispatch to Hydrogen Industry
    if available >= target_h2:
        actual_h2 = target_h2
        available -= target_h2
    else:
        actual_h2 = available + bat.discharge(target_h2 - available)
        available = 0
        
    logs["h2"].append(actual_h2)
    
    # Store Excess
    if available > 0:
        bat.charge(available)
    logs["bat"].append(bat.current_charge_wh)

total_h2_kg = sum(logs["h2"]) * 0.000268 

# Render Metrics
c1, c2, c3 = st.columns(3)
c1.metric("🔮 AI Hybrid Forecast Action", ai_mode)
c2.metric("💨 Peak Wind Speed Today", f"{np.max(w_spd_today):.1f} m/s")
c3.metric("🔋 Total Hydrogen Produced", f"{total_h2_kg:.3f} kg")

st.markdown("<br>", unsafe_allow_html=True)

# --- 4. DUAL-AXIS HYBRID GRAPH ---
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Power Axis (Left)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["solar"], name="Solar PV (W)", line=dict(color='#FFA500', width=2, dash='dash')), secondary_y=False)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["wind"], name="Wind Turbine (W)", line=dict(color='#00d2ff', width=2, dash='dash')), secondary_y=False)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["h2"], name=f"AI Dispatched Load (Target: {target_h2}W)", fill='tozeroy', line=dict(color='#00FF88', width=3), fillcolor='rgba(0, 255, 136, 0.15)'), secondary_y=False)

# Storage Axis (Right)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["bat"], name="Battery Level (Wh)", line=dict(color='#BF40BF', width=4), fill='tozeroy', fillcolor='rgba(191, 64, 191, 0.08)'), secondary_y=True)

fig.update_layout(
    title=dict(text="⚡ 24-Hour Hybrid Generation & Dispatch Profile", font=dict(color='#ffffff')),
    template="plotly_dark", height=550, hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=60, r=60, t=80, b=60), plot_bgcolor='#0e1117', paper_bgcolor='#0e1117'
)

fig.update_yaxes(title_text="<b>Power (Watts)</b>", title_font=dict(color="#00d2ff"), secondary_y=False, gridcolor='rgba(255,255,255,0.05)')
fig.update_yaxes(title_text="<b>Storage (Wh)</b>", title_font=dict(color="#BF40BF"), secondary_y=True, gridcolor='rgba(255,255,255,0.05)', range=[0, bat_cap * 1.1])
fig.update_xaxes(title_text="Hour of the Day", gridcolor='rgba(255,255,255,0.05)')

st.plotly_chart(fig, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.info("💡 **Physics Applied:** Wind power calculation uses continuous Open-Meteo wind speed (m/s) data with $P \\propto v^3$ law, factored by live Yaw misalignment penalties based on shifting wind directions.", icon="🧠")
