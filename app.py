import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import requests

# --- 1. THE POWER SOURCE ---
class SolarPVArray:
    def __init__(self, p_nom, alpha, g_ref=1000, t_ref=25):
        self.p_nom = p_nom
        self.alpha = alpha
        self.g_ref = g_ref
        self.t_ref = t_ref

    def get_power(self, g, t_c):
        irradiance_ratio = g / self.g_ref
        temp_penalty = 1 + (self.alpha * (t_c - self.t_ref))
        return max(0, self.p_nom * irradiance_ratio * temp_penalty)

# --- 2. THE STORAGE (Battery) ---
class BatteryStorage:
    def __init__(self, capacity_wh):
        self.capacity_wh = capacity_wh
        self.current_charge_wh = 0

    def charge(self, power_in):
        self.current_charge_wh = min(self.capacity_wh, self.current_charge_wh + power_in)

    def discharge(self, power_needed):
        actual_power_provided = min(power_needed, self.current_charge_wh)
        self.current_charge_wh -= actual_power_provided
        return actual_power_provided

# --- 3. THE LOAD (Electrolyzer) ---
class HydrogenElectrolyzer:
    def __init__(self, stack_voltage, num_cells, faraday_efficiency=0.9):
        self.stack_voltage = stack_voltage
        self.num_cells = num_cells
        self.faraday_efficiency = faraday_efficiency
        self.faraday_constant = 96485
        self.molar_mass_h2 = 0.002016

    def get_h2_kg_per_hour(self, power_in_watts):
        current = power_in_watts / self.stack_voltage
        moles_per_second = (self.faraday_efficiency * self.num_cells * current) / (2 * self.faraday_constant)
        return moles_per_second * self.molar_mass_h2 * 3600

# --- NEW: 4. THE AI PREDICTIVE ENGINE ---
class AIEngine:
    def __init__(self, solar_array):
        self.solar_array = solar_array

    def predict_tomorrow_energy(self, g_array_tomorrow, t_array_tomorrow):
        total_energy = 0
        for i in range(24):
            total_energy += self.solar_array.get_power(g_array_tomorrow[i], t_array_tomorrow[i])
        return total_energy

    def optimize_load(self, base_target, predicted_tomorrow_energy, nominal_daily_energy):
        # AI Decision Logic based on future physical constraints
        if predicted_tomorrow_energy < (0.7 * nominal_daily_energy):
            st.sidebar.error("⚠️ AI Alert: Heavy cloud cover detected for tomorrow. Activating Conservation Mode.")
            return base_target * 0.6  # Drop load by 40% to aggressively charge battery today
        elif predicted_tomorrow_energy > (1.1 * nominal_daily_energy):
            st.sidebar.success("☀️ AI Alert: Maximum solar yield expected tomorrow. Activating Aggressive Mode.")
            return base_target * 1.2  # Increase load by 20% to maximize H2
        else:
            st.sidebar.info("🤖 AI Status: Tomorrow's weather is stable. Maintaining nominal target.")
            return base_target

# --- 5. DATA LAYER (Now fetching 2 days of data) ---
@st.cache_data 
def get_live_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,shortwave_radiation&timezone=auto&forecast_days=2"
    response = requests.get(url)
    data = response.json()
    
    # Slice the data into Today (0-24) and Tomorrow (24-48)
    t_today = np.array(data['hourly']['temperature_2m'][:24])
    g_today = np.array(data['hourly']['shortwave_radiation'][:24])
    t_tomorrow = np.array(data['hourly']['temperature_2m'][24:48])
    g_tomorrow = np.array(data['hourly']['shortwave_radiation'][24:48])
    
    return g_today, t_today, g_tomorrow, t_tomorrow

# --- 6. THE WEB DASHBOARD UI ---
st.set_page_config(page_title="Microgrid AI Twin", layout="wide")
st.title("🧠 AI-Driven Smart Microgrid Dashboard")
st.markdown("Predictive Orchestration Engine utilizing Machine Learning heuristics for optimal power flow.")

# UI Sidebar
st.sidebar.header("⚙️ Hardware Parameters")
user_solar_capacity = st.sidebar.slider("Solar Capacity (Watts)", 1000, 10000, 5000, 500)
user_battery_capacity = st.sidebar.slider("Battery Capacity (Wh)", 2000, 20000, 10000, 1000)
user_target_power = st.sidebar.slider("Nominal Electrolyzer Target (W)", 500, 5000, 2000, 500)

# Fetch 48-Hour Data
g_today, t_today, g_tomorrow, t_tomorrow = get_live_weather_data(22.5726, 88.3639)
hours = np.arange(24)

# Initialize Hardware & AI
my_solar = SolarPVArray(p_nom=user_solar_capacity, alpha=-0.004)
my_battery = BatteryStorage(capacity_wh=user_battery_capacity) 
my_electrolyzer = HydrogenElectrolyzer(stack_voltage=48, num_cells=30)
my_ai = AIEngine(solar_array=my_solar)

# AI IN ACTION: Predict and Optimize before running the grid
st.sidebar.header("🧠 AI Diagnostic Layer")
nominal_daily_energy = user_solar_capacity * 5  # Rough estimate of a perfect day
predicted_tomorrow = my_ai.predict_tomorrow_energy(g_tomorrow, t_tomorrow)

# The AI overrides the user's manual target based on the future!
ai_optimized_target = my_ai.optimize_load(user_target_power, predicted_tomorrow, nominal_daily_energy)

st.sidebar.write(f"**Manual Target:** {user_target_power} W")
st.sidebar.write(f"**AI Adjusted Target:** {ai_optimized_target:.1f} W")

power_to_electrolyzer_log = []
battery_state_log = []
solar_power_log = []

# ORCHESTRATION LOOP (Using AI's target)
for i in range(24):
    current_solar = my_solar.get_power(g_today[i], t_today[i])
    solar_power_log.append(current_solar)

    if current_solar >= ai_optimized_target:
        actual_power_to_electrolyzer = ai_optimized_target
        excess_power = current_solar - ai_optimized_target
        my_battery.charge(excess_power)
    else:
        deficit = ai_optimized_target - current_solar
        power_from_battery = my_battery.discharge(deficit)
        actual_power_to_electrolyzer = current_solar + power_from_battery

    power_to_electrolyzer_log.append(actual_power_to_electrolyzer)
    battery_state_log.append(my_battery.current_charge_wh)

# Calculate Outputs
h2_produced = [my_electrolyzer.get_h2_kg_per_hour(p) for p in power_to_electrolyzer_log]
total_h2 = sum(h2_produced)

# UI Display
st.metric(label="Total Green Hydrogen Produced Today", value=f"{total_h2:.3f} kg")

fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(hours, solar_power_log, label="Raw Solar Power (W)", color="orange", linestyle="--", linewidth=2)
ax.plot(hours, power_to_electrolyzer_log, label=f"AI Managed Power ({ai_optimized_target:.0f} W)", color="green", linewidth=3)
ax.fill_between(hours, battery_state_log, color="purple", alpha=0.3, label="Battery Charge Level (Wh)")
ax.set_xlabel("Hour of the Day")
ax.set_ylabel("Power / Energy")
ax.legend()
ax.grid(True)
ax.set_xticks(hours)
st.pyplot(fig)