import streamlit as st
import numpy as np
import requests
import matplotlib.pyplot as plt

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
        self.v_in = v_in      
        self.v_rated = v_rated 
        self.v_out = v_out    

    def get_power(self, v_wind, wind_dir):
        if v_wind < self.v_in or v_wind > self.v_out:
            p_base = 0
        elif self.v_in <= v_wind <= self.v_rated:
            p_base = self.p_rated * ((v_wind**3 - self.v_in**3) / (self.v_rated**3 - self.v_in**3))
        else:
            p_base = self.p_rated
            
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

# --- 2. SIMPLE ORIGINAL UI ---
st.set_page_config(page_title="AI Hybrid Microgrid", layout="wide")

st.title("🧠 AI-Driven Smart Microgrid Dashboard")
st.markdown("Predictive Orchestration Engine utilizing Machine Learning heuristics for optimal power flow (Solar + Wind).")

# Sidebar
st.sidebar.header("⚙️ Hardware Parameters")
sol_cap = st.sidebar.slider("Solar Capacity (Watts)", 1000, 10000, 5000)
wind_cap = st.sidebar.slider("Wind Turbine Capacity (Watts)", 1000, 10000, 4000)
bat_cap = st.sidebar.slider("Battery Capacity (Wh)", 2000, 20000, 10000)
base_target = st.sidebar.slider("Nominal Electrolyzer Target (W)", 1000, 5000, 2000)

@st.cache_data 
def fetch_hybrid_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,shortwave_radiation,wind_speed_10m,wind_direction_10m&wind_speed_unit=ms&timezone=auto&forecast_days=2"
    res = requests.get(url).json()
    h = res['hourly']
    return (np.array(h['shortwave_radiation'][:24]), np.array(h['temperature_2m'][:24]), 
            np.array(h['wind_speed_10m'][:24]), np.array(h['wind_direction_10m'][:24]),
            np.array(h['shortwave_radiation'][24:48]))

# Kolkata Coordinates
g_today, t_today, w_spd_today, w_dir_today, g_tmrw = fetch_hybrid_weather(22.57, 88.36)

# --- 3. AI LOGIC ---
solar_arr = SolarPVArray(sol_cap)
wind_turb = WindTurbine(wind_cap)
bat = BatteryStorage(bat_cap)

# AI Decision based on tomorrow's solar forecast
if np.sum(g_tmrw) < 3000:
    ai_status = "AI Alert: Low solar yield expected tomorrow. Activating Conservative Mode."
    target_h2 = base_target * 0.7 
    alert_type = "warning"
else:
    ai_status = "AI Alert: Maximum solar yield expected tomorrow. Activating Aggressive Mode."
    target_h2 = base_target * 1.2
    alert_type = "success"

logs = {"solar": [], "wind": [], "h2": [], "bat": []}

for i in range(24):
    p_sun = solar_arr.get_power(g_today[i], t_today[i])
    p_wind = wind_turb.get_power(w_spd_today[i], w_dir_today[i])
    
    logs["solar"].append(p_sun)
    logs["wind"].append(p_wind)
    
    available = p_sun + p_wind
    
    if available >= target_h2:
        actual_h2 = target_h2
        available -= target_h2
    else:
        actual_h2 = available + bat.discharge(target_h2 - available)
        available = 0
        
    logs["h2"].append(actual_h2)
    if available > 0:
        bat.charge(available)
    logs["bat"].append(bat.current_charge_wh)

total_h2_kg = sum(logs["h2"]) * 0.000268 

# Metrics
st.markdown("Total Green Hydrogen Produced Today")
st.header(f"{total_h2_kg:.3f} kg")

# --- 4. ORIGINAL MATPLOTLIB GRAPH (With Dual Axis Fix) ---
fig, ax1 = plt.subplots(figsize=(12, 5))

# Power Lines (Left Axis)
ax1.plot(logs['solar'], label="Raw Solar Power (W)", color='orange', linestyle='--')
ax1.plot(logs['wind'], label="Raw Wind Power (W)", color='blue', linestyle=':')
ax1.plot(logs['h2'], label=f"AI Managed Power ({target_h2:.0f} W)", color='green', linewidth=2)
ax1.set_xlabel("Hour of the Day")
ax1.set_ylabel("Power (Watts)", color='black')
ax1.grid(True, linestyle=':', alpha=0.6)

# Battery Fill (Right Axis)
ax2 = ax1.twinx()
ax2.fill_between(range(24), logs['bat'], color='purple', alpha=0.3, label="Battery Charge Level (Wh)")
ax2.set_ylabel("Storage (Wh)", color='purple')
ax2.set_ylim(0, bat_cap * 1.1)

# Combine legends from both axes
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()
ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper right', fontsize=8)

st.pyplot(fig)

# Sidebar Alerts
st.sidebar.markdown("---")
st.sidebar.subheader("🧠 AI Diagnostic Layer")
if alert_type == "success":
    st.sidebar.success(ai_status)
else:
    st.sidebar.warning(ai_status)

st.sidebar.markdown(f"**Manual Target:** {base_target} W")
st.sidebar.markdown(f"**AI Adjusted Target:** {target_h2:.1f} W")
