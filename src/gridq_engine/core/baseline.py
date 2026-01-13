"""Baseline dispatch strategy for comparison.

Simple heuristic: PV self-consumption first, charge battery from excess PV,
discharge to serve load, no arbitrage.
"""

import pandas as pd

from gridq_engine.core.constants import (
    COL_BATTERY_CHARGE_KW,
    COL_BATTERY_DISCHARGE_KW,
    COL_GRID_EXPORT_KW,
    COL_GRID_IMPORT_KW,
    COL_LOAD_KW,
    COL_PV_KW,
    COL_SOC_KWH,
)
from gridq_engine.core.schemas import SiteConfig


def compute_baseline_dispatch(
    timeseries: pd.DataFrame, site_config: SiteConfig, timestep_hours: float
) -> pd.DataFrame:
    """Compute baseline dispatch using simple heuristic.

    Strategy:
    1. Use PV to serve load directly
    2. Excess PV charges battery (up to limits)
    3. Remaining excess PV exports to grid
    4. Load deficit first met by battery discharge (if available)
    5. Remaining deficit met by grid import

    Args:
        timeseries: Input timeseries with load_kw and pv_kw
        site_config: Site configuration
        timestep_hours: Timestep in hours (e.g., 0.25 for 15 minutes)

    Returns:
        DataFrame with baseline dispatch columns
    """
    battery = site_config.battery
    result = timeseries.copy()

    # Initialize dispatch columns
    result[COL_GRID_IMPORT_KW] = 0.0
    result[COL_GRID_EXPORT_KW] = 0.0
    result[COL_BATTERY_CHARGE_KW] = 0.0
    result[COL_BATTERY_DISCHARGE_KW] = 0.0
    result[COL_SOC_KWH] = battery.initial_soc_frac * battery.capacity_kwh

    for i in range(len(result)):
        load = result.iloc[i][COL_LOAD_KW]
        pv = result.iloc[i][COL_PV_KW]

        # Current SOC
        if i == 0:
            soc = battery.initial_soc_frac * battery.capacity_kwh
        else:
            soc = result.iloc[i - 1][COL_SOC_KWH]

        # Net position after PV
        net = pv - load

        charge_kw = 0.0
        discharge_kw = 0.0
        grid_import_kw = 0.0
        grid_export_kw = 0.0

        if net > 0:
            # Excess PV: charge battery first, then export
            max_charge = min(
                battery.max_charge_kw,
                (battery.max_soc_frac * battery.capacity_kwh - soc)
                / (timestep_hours * battery.charge_efficiency),
            )
            charge_kw = min(net, max_charge)
            remaining_excess = net - charge_kw

            grid_export_kw = remaining_excess

        else:
            # Deficit: discharge battery first, then import
            deficit = -net
            max_discharge = min(
                battery.max_discharge_kw,
                (soc - battery.min_soc_frac * battery.capacity_kwh)
                / (timestep_hours / battery.discharge_efficiency),
            )
            discharge_kw = min(deficit, max_discharge)
            remaining_deficit = deficit - discharge_kw

            grid_import_kw = remaining_deficit

        # Apply grid limits if specified
        if site_config.max_grid_import_kw is not None:
            grid_import_kw = min(grid_import_kw, site_config.max_grid_import_kw)

        if site_config.max_grid_export_kw is not None:
            grid_export_kw = min(grid_export_kw, site_config.max_grid_export_kw)

        # Update SOC
        new_soc = (
            soc
            + charge_kw * timestep_hours * battery.charge_efficiency
            - discharge_kw * timestep_hours / battery.discharge_efficiency
        )

        # Clamp SOC to bounds (should already be satisfied but just in case)
        new_soc = max(
            battery.min_soc_frac * battery.capacity_kwh,
            min(battery.max_soc_frac * battery.capacity_kwh, new_soc),
        )

        # Store results
        result.at[result.index[i], COL_GRID_IMPORT_KW] = grid_import_kw
        result.at[result.index[i], COL_GRID_EXPORT_KW] = grid_export_kw
        result.at[result.index[i], COL_BATTERY_CHARGE_KW] = charge_kw
        result.at[result.index[i], COL_BATTERY_DISCHARGE_KW] = discharge_kw
        result.at[result.index[i], COL_SOC_KWH] = new_soc

    return result
