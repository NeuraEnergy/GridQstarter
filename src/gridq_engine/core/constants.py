"""Canonical column names, units, and sign conventions.

SIGN CONVENTIONS (all positive direction):
- load_kw: Positive = consumption
- pv_kw: Positive = generation
- grid_import_kw: Positive = import from grid
- grid_export_kw: Positive = export to grid
- battery_charge_kw: Positive = charging (energy into battery)
- battery_discharge_kw: Positive = discharging (energy from battery)
- soc_kwh: Absolute state of charge in kWh

UNITS:
- Power: kW
- Energy: kWh
- Prices: £/kWh (GBP per kWh)
- Demand charge: £/kW (GBP per kW of peak)
- Time: minutes (for timesteps), hours (for horizons)
- Timestamps: UTC

ENERGY BALANCE EQUATION:
load_kw + battery_charge_kw + grid_export_kw = pv_kw + battery_discharge_kw + grid_import_kw

All variables are >= 0 (no negative power flows).
"""

# Required input columns
COL_TIMESTAMP = "timestamp"
COL_LOAD_KW = "load_kw"
COL_PV_KW = "pv_kw"
COL_IMPORT_PRICE = "import_price_gbp_per_kwh"
COL_EXPORT_PRICE = "export_price_gbp_per_kwh"
COL_FLEX_PRICE = "flex_price_gbp_per_kwh"  # Optional, future use

REQUIRED_INPUT_COLUMNS = [
    COL_LOAD_KW,
    COL_PV_KW,
    COL_IMPORT_PRICE,
    COL_EXPORT_PRICE,
]

# Output columns
COL_GRID_IMPORT_KW = "grid_import_kw"
COL_GRID_EXPORT_KW = "grid_export_kw"
COL_BATTERY_CHARGE_KW = "battery_charge_kw"
COL_BATTERY_DISCHARGE_KW = "battery_discharge_kw"
COL_SOC_KWH = "soc_kwh"
COL_SOC_FRAC = "soc_frac"

OUTPUT_COLUMNS = [
    COL_GRID_IMPORT_KW,
    COL_GRID_EXPORT_KW,
    COL_BATTERY_CHARGE_KW,
    COL_BATTERY_DISCHARGE_KW,
    COL_SOC_KWH,
]

# Tolerance for numerical comparisons
NUMERICAL_TOLERANCE = 1e-6
