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
        self.current_charge_wh = capacity_wh * 0.3 # Starts with 30% buffer

    def charge(self, power_in):
        self.current_charge_wh = min(self.capacity_wh, self.current_charge_wh + power_in)

    def discharge(self, power_needed):
        actual_power_provided = min(power_needed, self.current_charge_wh)
        self.current_charge_wh -= actual_power_provided
        return actual_power_provided

# --- 3. THE INDUSTRIAL LOAD (Electrolyzer) ---
class HydrogenElectrolyzer:
    def __init__(self, stack_voltage, num_cells, faraday_efficiency=0.9):
        self.stack_voltage = stack_voltage
        self.num_cells = num_cells
        self.faraday_efficiency = faraday_efficiency
        self.faraday_constant = 96485
        self.molar_mass_h2 = 0.002016

    def get_h2_kg_per_hour(self, power_in_watts):
        if power_in_watts <= 0:
            return 0
        current = power_in_watts / self.stack_voltage
        moles_per_second = (self.faraday_efficiency * self.num_cells * current) / (2 * self.faraday_constant)
        return moles_per_second * self.molar_mass_h2 * 3600

# --- 4. THE WEB DASHBOARD UI ---
st.set_page_config(page_title="Rural Medical Microgrid AI", layout="wide")
st.title("🏥 AI Rural Medical Lifeline & Microgrid")
st.markdown("First-Principles Predictive Orchestration Engine protecting critical healthcare cold-chains during weather crises.")

# UI Sidebar
st.sidebar.header("⚙️ Rural Grid Parameters")
user_solar_capacity = st.sidebar.slider("Solar PV Capacity (Watts)", 1000, 10000, 5000, 500)
user_battery_capacity = st.sidebar.slider("Battery Storage Capacity (Wh)", 2000, 20000, 10000, 1000)

st.sidebar.markdown("---")
st.sidebar.subheader("🚨 Critical Lifeline Load")
medical_load = st.sidebar.number_input("Vaccine Fridge & Clinic Load (Watts)", value=500, disabled=True)
st.sidebar.caption("This 500W load is permanently prioritized by AI over industrial production.")

# Fetch 48-Hour Live Data (Kolkata Region)
@st.cache_data 
def get_live_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,shortwave_radiation&timezone=auto&forecast_days=2"
    response = requests.get(url)
    data = response.json()
    return (np.array(data['hourly']['shortwave_radiation'][:24]), 
            np.array(data['hourly']['temperature_2m'][:24]),
            np.array(data['hourly']['shortwave_radiation'][24:48]), 
            np.array(data['hourly']['temperature_2m'][24:48]))

g_today, t_today, g_tomorrow, t_tomorrow = get_live_weather_data(22.5726, 88.3639)
hours = np.arange(24)

my_solar = SolarPVArray(p_nom=user_solar_capacity, alpha=-0.004)
my_battery = BatteryStorage(capacity_wh=user_battery_capacity) 
my_electrolyzer = HydrogenElectrolyzer(stack_voltage=48, num_cells=30)

# --- 5. LIFELINE AI LOGIC ---
st.sidebar.header("🧠 AI Lifeline Diagnostic")
nominal_daily_energy = user_solar_capacity * 5
total_solar_today = sum([my_solar.get_power(g_today[i], t_today[i]) for i in range(24)])
predicted_tomorrow_energy = sum([my_solar.get_power(g_tomorrow[i], t_tomorrow[i]) for i in range(24)])

# AI Mode selection based on physics & forecasting
if total_solar_today < (0.3 * nominal_daily_energy) and predicted_tomorrow_energy < (0.3 * nominal_daily_energy):
    ai_mode = "CRITICAL EMERGENCY"
    target_h2_power = 0  # Complete shutdown of industry to save clinic
    st.sidebar.error("🔴 AI ALERT: Severe Multi-day Weather Crisis. Hydrogen Plant SHUTDOWN. 100% Power routed to Medical Clinic.")
elif predicted_tomorrow_energy < (0.6 * nominal_daily_energy):
    ai_mode = "CONSERVATION WARNING"
    target_h2_power = 1000  # Throttle industry
    st.sidebar.warning("⚠️ AI ALERT: Tomorrow cloud cover expected. Throttling Hydrogen to buffer Vaccine Fridge.")
else:
    ai_mode = "NORMAL HEALTHY"
    target_h2_power = 2500  # Full operation
    st.sidebar.success("🟢 AI STATUS: Grid Stable. Solar generation optimal for both Clinic and Industry.")

# Simulation Arrays
solar_power_log = []
medical_served_log = []
h2_power_log = []
battery_state_log = []

# ORCHESTRATION LOOP (Hourly Physics Simulation)
for i in range(24):
    current_solar = my_solar.get_power(g_today[i], t_today[i])
    solar_power_log.append(current_solar)
    
    available_power = current_solar
    
    # Priority 1: Serve Critical Medical Load First
    if available_power >= medical_load:
        actual_medical = medical_load
        available_power -= medical_load
    else:
        # Solar is deficit, pull from battery for clinic!
        deficit = medical_load - available_power
        actual_medical = available_power + my_battery.discharge(deficit)
        available_power = 0
        
    medical_served_log.append(actual_medical)
    
    # Priority 2: Industrial Hydrogen Generation (Only if AI Mode allows and power is left)
    actual_h2_power = 0
    if ai_mode != "CRITICAL EMERGENCY" and available_power > 0:
        actual_h2_power = min(available_power, target_h2_power)
        available_power -= actual_h2_power
    h2_power_log.append(actual_h2_power)
    
    # Priority 3: Store remaining excess power in battery
    if available_power > 0:
        my_battery.charge(available_power)
        
    battery_state_log.append(my_battery.current_charge_wh)

# Calculate Outputs
h2_produced = [my_electrolyzer.get_h2_kg_per_hour(p) for p in h2_power_log]
total_h2 = sum(h2_produced)
total_medical_hours_unserved = medical_served_log.count(0) # Critical metric

# --- 6. RENDER RE-DESIGNED UI ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="AI Grid Status Mode", value=ai_mode)
with col2:
    st.metric(label="Vaccine Fridge Power Security", value="100% SECURE" if total_medical_hours_unserved == 0 else "⚠️ VULNERABLE")
with col3:
    st.metric(label="Green Hydrogen Commodity Produced", value=f"{total_h2:.3f} kg")

# Dynamic Metrics Warning
if total_medical_hours_unserved > 0:
    st.error(f"🚨 CRITICAL WARNING: Battery depleted! Medical clinic faced {total_medical_hours_unserved} hours of power blackout today! Increase battery or solar capacity instantly!")

# Plotting the Ecosystem
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(hours, solar_power_log, label="Raw Solar Generation (W)", color="orange", linestyle="--")
ax.plot(hours, h2_power_log, label="Industrial Hydrogen Load (W)", color="green", linewidth=2)
ax.bar(hours, medical_served_log, label="Prioritized Medical Clinic Load (W)", color="red", alpha=0.6)
ax.fill_between(hours, battery_state_log, color="purple", alpha=0.2, label="Emergency Battery Reserve (Wh)")
ax.set_xlabel("Hour of the Day")
ax.set_ylabel("Power (W) / Energy (Wh)")
ax.set_title("🏥 24-Hour AI Lifeline Power Distribution Profile")
ax.legend(loc="upper left")
ax.grid(True)
ax.set_xticks(hours)
st.pyplot(fig)
