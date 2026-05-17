import streamlit as st
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------- PAGE CONFIG ----------------

st.set_page_config(
    page_title="AI Smart Microgrid",
    layout="wide"
)

# ---------------- CUSTOM CSS ----------------

st.markdown("""
<style>

body {
    background-color: #0e1117;
}

.stApp {
    background-color: #0e1117;
    color: white;
}

.main {
    background-color: #0e1117;
    color: white;
}

h1, h2, h3, h4, h5, h6 {
    color: white;
}

p, label, div {
    color: white;
}

[data-testid="stSidebar"] {
    background-color: #111827;
}

[data-testid="metric-container"] {
    background-color: #1f2937;
    border: 1px solid #374151;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0px 0px 15px rgba(0,255,255,0.2);
}

.stAlert {
    border-radius: 15px;
}

</style>
""", unsafe_allow_html=True)

# ---------------- HYBRID SYSTEM ----------------

class SolarPVArray:

    def __init__(self, p_nom, alpha=-0.004):

        self.p_nom = p_nom
        self.alpha = alpha

    def get_power(self, g, t_c):

        return max(
            0,
            self.p_nom * (g / 1000) * (1 + self.alpha * (t_c - 25))
        )

class WindTurbine:

    def __init__(
        self,
        p_rated,
        v_in=3.0,
        v_rated=12.0,
        v_out=25.0
    ):

        self.p_rated = p_rated
        self.v_in = v_in
        self.v_rated = v_rated
        self.v_out = v_out

    def get_power(self, v_wind, wind_dir):

        if v_wind < self.v_in or v_wind > self.v_out:

            p_base = 0

        elif self.v_in <= v_wind <= self.v_rated:

            p_base = self.p_rated * (
                (v_wind**3 - self.v_in**3)
                /
                (self.v_rated**3 - self.v_in**3)
            )

        else:

            p_base = self.p_rated

        misalignment_angle = abs(180 - wind_dir)

        yaw_efficiency = max(
            0.85,
            1 - (misalignment_angle * 0.001)
        )

        return p_base * yaw_efficiency

class BatteryStorage:

    def __init__(self, capacity_wh):

        self.capacity_wh = capacity_wh
        self.current_charge_wh = capacity_wh * 0.3

    def charge(self, power_in):

        self.current_charge_wh = min(
            self.capacity_wh,
            self.current_charge_wh + power_in
        )

    def discharge(self, power_needed):

        provided = min(
            power_needed,
            self.current_charge_wh
        )

        self.current_charge_wh -= provided

        return provided

# ---------------- WEATHER API ----------------

@st.cache_data
def fetch_weather(lat, lon):

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,shortwave_radiation,wind_speed_10m,wind_direction_10m&wind_speed_unit=ms&timezone=auto&forecast_days=2"

    res = requests.get(url).json()

    h = res['hourly']

    return (
        np.array(h['shortwave_radiation'][:24]),
        np.array(h['temperature_2m'][:24]),
        np.array(h['wind_speed_10m'][:24]),
        np.array(h['wind_direction_10m'][:24]),
        np.array(h['shortwave_radiation'][24:48])
    )

# ---------------- SIDEBAR ----------------

st.sidebar.title("⚙️ Hardware Parameters")

sol_cap = st.sidebar.slider(
    "Solar Capacity (W)",
    1000,
    10000,
    5000
)

wind_cap = st.sidebar.slider(
    "Wind Capacity (W)",
    1000,
    10000,
    4000
)

bat_cap = st.sidebar.slider(
    "Battery Capacity (Wh)",
    2000,
    20000,
    10000
)

base_target = st.sidebar.slider(
    "Electrolyzer Target (W)",
    1000,
    5000,
    2000
)

# ---------------- FETCH WEATHER ----------------

g_today, t_today, w_spd_today, w_dir_today, g_tmrw = fetch_weather(
    22.57,
    88.36
)

# ---------------- AI LOGIC ----------------

solar_arr = SolarPVArray(sol_cap)

wind_turb = WindTurbine(wind_cap)

bat = BatteryStorage(bat_cap)

if np.sum(g_tmrw) < 3000:

    ai_status = "⚠️ Low Solar Expected Tomorrow"

    target_h2 = base_target * 0.7

else:

    ai_status = "✅ Maximum Solar Expected Tomorrow"

    target_h2 = base_target * 1.2

logs = {
    "solar": [],
    "wind": [],
    "h2": [],
    "bat": []
}

for i in range(24):

    p_sun = solar_arr.get_power(
        g_today[i],
        t_today[i]
    )

    p_wind = wind_turb.get_power(
        w_spd_today[i],
        w_dir_today[i]
    )

    logs["solar"].append(p_sun)

    logs["wind"].append(p_wind)

    available = p_sun + p_wind

    if available >= target_h2:

        actual_h2 = target_h2

        available -= target_h2

    else:

        actual_h2 = available + bat.discharge(
            target_h2 - available
        )

        available = 0

    logs["h2"].append(actual_h2)

    if available > 0:
        bat.charge(available)

    logs["bat"].append(bat.current_charge_wh)

# ---------------- HYDROGEN ----------------

total_h2_kg = sum(logs["h2"]) * 0.000268

# ---------------- TITLE ----------------

st.title("🧠 AI-Driven Smart Microgrid Dashboard")

st.markdown(
    "AI-based renewable energy optimization for Solar + Wind + Hydrogen systems."
)

# ---------------- KPI CARDS ----------------

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "☀️ Solar Peak",
        f"{max(logs['solar']):.0f} W"
    )

with col2:

    st.metric(
        "🌪 Wind Peak",
        f"{max(logs['wind']):.0f} W"
    )

with col3:

    st.metric(
        "🔋 Battery",
        f"{logs['bat'][-1]:.0f} Wh"
    )

with col4:

    st.metric(
        "🧪 Hydrogen",
        f"{total_h2_kg:.3f} kg"
    )

# ---------------- AI STATUS ----------------

st.success(ai_status)

# ---------------- GRAPH ----------------

st.subheader("⚡ Smart Energy Flow")

fig = make_subplots(
    specs=[[{"secondary_y": True}]]
)

# Solar

fig.add_trace(
    go.Scatter(
        x=list(range(24)),
        y=logs['solar'],
        mode='lines',
        name='Solar Power',
        line=dict(
            width=4,
            dash='dash'
        )
    ),
    secondary_y=False
)

# Wind

fig.add_trace(
    go.Scatter(
        x=list(range(24)),
        y=logs['wind'],
        mode='lines',
        name='Wind Power',
        line=dict(
            width=3,
            dash='dot'
        )
    ),
    secondary_y=False
)

# AI Managed Power

fig.add_trace(
    go.Scatter(
        x=list(range(24)),
        y=logs['h2'],
        mode='lines',
        name='AI Managed Power',
        line=dict(width=5)
    ),
    secondary_y=False
)

# Battery

fig.add_trace(
    go.Scatter(
        x=list(range(24)),
        y=logs['bat'],
        fill='tozeroy',
        name='Battery Storage',
        opacity=0.35
    ),
    secondary_y=True
)

# Layout

fig.update_layout(
    template="plotly_dark",
    height=600,
    hovermode="x unified",
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    font=dict(
        color="white",
        size=14
    ),
    legend=dict(
        bgcolor="#111827"
    )
)

fig.update_xaxes(
    title_text="Hour of Day"
)

fig.update_yaxes(
    title_text="Power (W)",
    secondary_y=False
)

fig.update_yaxes(
    title_text="Battery (Wh)",
    secondary_y=True
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# ---------------- SIDEBAR AI ----------------

st.sidebar.markdown("---")

st.sidebar.subheader("🧠 AI Diagnostic Layer")

st.sidebar.success(ai_status)

st.sidebar.markdown(
    f"### 🎯 AI Adjusted Target: {target_h2:.0f} W"
)
