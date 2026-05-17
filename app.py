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

# --- 2. DASHBOARD SETUP (HIGH CONTRAST CLEAN UI) ---
st.set_page_config(page_title="Smart Microgrid AI v2.2", layout="wide")

# White-and-Dark high contrast theme for crisp visibility
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
    p { color: #cbd5e1 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏥 Smart Microgrid AI: Version 2.2")
st.markdown("### First-Principles Resilient Energy Dashboard for Rural Healthcare")

# Sidebar
st.sidebar.header("⚙️ Control Panel")
sol_cap = st.sidebar.slider("Solar PV Capacity (W)", 2000, 15000, 7000)
bat_cap = st.sidebar.slider("Battery Energy (Wh)", 5000, 30000, 15000)
med_load = 500 # 500W Standard Critical Load

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
    ai_mode, target_h2, status_color = "HEALTHY: OPTIMAL", 2500, "green"

# Simulation
bat = BatteryStorage(bat_cap)
logs = {"solar": [], "med": [], "h2": [], "bat": []}

for i in range(24):
    p_sun = SolarPVArray(sol_cap).get_power(g_today[i], t_today[i])
    logs["solar"].append(p_sun)
    
    # Priority 1: Clinic Load First
    if p_sun >= med_load:
        logs["med"].append(med_load)
        p_sun -= med_load
    else:
        logs["med"].append(p_sun + bat.discharge(med_load - p_sun))
        p_sun = 0
        
    # Priority 2: Hydrogen
    p_h2 = min(p_sun, target_h2) if ai_mode != "CRITICAL: EMERGENCY" else 0
    logs["h2"].append(p_h2)
    p_sun -= p_h2
    
    # Priority 3: Battery Storage
    if p_sun > 0: 
        bat.charge(p_sun)
    logs["bat"].append(bat.current_charge_wh)

# Metrics Display Row
st.markdown("<br>", unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.metric("🧠 AI Strategy Mode", ai_mode)
c2.metric("🛡️ Clinic Vaccine Security", "100% SECURE" if logs["med"].count(med_load) == 24 else "⚠️ BLACKOUT RISK")
c3.metric("🔋 Green Hydrogen Produced", f"{sum(logs['h2'])*0.00002:.3f} kg")
st.markdown("<br>", unsafe_allow_html=True)

# --- 4. THE ULTIMATE BALANCED GRAPH ---
fig = make_subplots(specs=[[{"secondary_y": True}]])

# Primary Axis (Left): Power in Watts
# 1. Raw Solar - Bold Dash Line
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["solar"], name="Raw Solar Power (W)", line=dict(color='#FFA500', width=3, dash='dash')), secondary_y=False)
# 2. Hydrogen Load - Solid Green Line with Area Fill (Like v1)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["h2"], name="AI Managed Hydrogen Load (W)", fill='tozeroy', line=dict(color='#00FF88', width=3)), secondary_y=False)
# 3. Medical Clinic - Red Solid Block Bars at the bottom
fig.add_trace(go.Bar(x=list(range(24)), y=logs["med"], name="Prioritized Clinic Load (W)", marker_color='#FF4B4B', opacity=0.85), secondary_y=False)

# Secondary Axis (Right): Energy in Watt-Hours (Separated Scaling!)
fig.add_trace(go.Scatter(x=list(range(24)), y=logs["bat"], name="Emergency Battery Level (Wh)", line=dict(color='#BF40BF', width=4), fill='tozeroy', fillcolor='rgba(191, 64, 191, 0.1)'), secondary_y=True)

# Layout adjustments for a high-contrast premium look
fig.update_layout(
    title=dict(text="⚡ 24-Hour AI Lifeline Power & Energy Balance Profile", font=dict(size=18, color='#ffffff')),
    template="plotly_dark", 
    height=550, 
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=60, r=60, t=80, b=60),
    plot_bgcolor='#0e1117',
    paper_bgcolor='#0e1117'
)

fig.update_yaxes(title_text="<b>Power Flows (Watts)</b>", title_font=dict(color="#FFA500"), secondary_y=False, gridcolor='rgba(255,255,255,0.05)')
fig.update_yaxes(title_text="<b>Battery Storage (Watt-Hours)</b>", title_font=dict(color="#BF40BF"), secondary_y=True, gridcolor='rgba(255,255,255,0.05)', range=[0, bat_cap * 1.1])
fig.update_xaxes(title_text="Hour of the Day", tickmode='linear', tick0=0, dtick=1, gridcolor='rgba(255,255,255,0.05)')

st.plotly_chart(fig, use_container_width=True)

# Sidebar Alert HUD
st.sidebar.markdown("---")
st.sidebar.subheader("📢 Live HUD Status")
if ai_mode == "HEALTHY: OPTIMAL":
    st.sidebar.success(f"🟢 Grid Stable.<br>Solar generation is optimal for both the healthcare clinic and industrial production.", icon="✅")
elif ai_mode == "WARNING: CONSERVE":
    st.sidebar.warning(f"⚠️ Tomorrow's forecast indicates low irradiance.<br>Throttling Hydrogen system to conserve battery buffer.", icon="⚠️")
else:
    st.sidebar.error(f"🔴 Multi-day extreme weather alert.<br>Hydrogen plant SHUTDOWN. 100% solar routed to clinic vaccines.", icon="🚨")
