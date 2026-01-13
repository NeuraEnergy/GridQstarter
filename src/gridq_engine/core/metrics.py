"""Metrics computation for dispatch results."""

import pandas as pd

from gridq_engine.core.constants import (
    COL_BATTERY_CHARGE_KW,
    COL_BATTERY_DISCHARGE_KW,
    COL_EXPORT_PRICE,
    COL_GRID_EXPORT_KW,
    COL_GRID_IMPORT_KW,
    COL_IMPORT_PRICE,
)
from gridq_engine.core.schemas import RunConfig, SiteConfig


def compute_cost(
    dispatch: pd.DataFrame,
    site_config: SiteConfig,
    run_config: RunConfig,
    timestep_hours: float,
) -> float:
    """Compute total cost for a dispatch schedule.

    Args:
        dispatch: Dispatch result with grid flows and prices
        site_config: Site configuration
        run_config: Run configuration
        timestep_hours: Timestep in hours

    Returns:
        Total cost in GBP (positive = cost, negative = profit)
    """
    # Import cost
    import_cost = (dispatch[COL_GRID_IMPORT_KW] * dispatch[COL_IMPORT_PRICE] * timestep_hours).sum()

    # Export revenue (negative cost)
    export_revenue = (dispatch[COL_GRID_EXPORT_KW] * dispatch[COL_EXPORT_PRICE] * timestep_hours).sum()

    # Demand charge (if enabled)
    demand_charge = 0.0
    if run_config.tariff.demand_charge_enabled:
        peak_import_kw = dispatch[COL_GRID_IMPORT_KW].max()
        demand_charge = peak_import_kw * run_config.tariff.demand_charge_gbp_per_kw

    # Degradation cost
    battery_throughput_kwh = (
        (dispatch[COL_BATTERY_CHARGE_KW] + dispatch[COL_BATTERY_DISCHARGE_KW]) * timestep_hours
    ).sum()
    degradation_cost = battery_throughput_kwh * site_config.battery.degradation_cost_gbp_per_kwh

    total_cost = import_cost - export_revenue + demand_charge + degradation_cost

    return total_cost


def compute_metrics(
    optimal_dispatch: pd.DataFrame,
    baseline_dispatch: pd.DataFrame,
    site_config: SiteConfig,
    run_config: RunConfig,
    timestep_hours: float,
) -> dict:
    """Compute metrics comparing optimal vs baseline dispatch.

    Args:
        optimal_dispatch: Optimized dispatch result
        baseline_dispatch: Baseline dispatch result
        site_config: Site configuration
        run_config: Run configuration
        timestep_hours: Timestep in hours

    Returns:
        Dictionary of metrics
    """
    optimal_cost = compute_cost(optimal_dispatch, site_config, run_config, timestep_hours)
    baseline_cost = compute_cost(baseline_dispatch, site_config, run_config, timestep_hours)

    savings_gbp = baseline_cost - optimal_cost
    savings_pct = (savings_gbp / baseline_cost * 100) if baseline_cost != 0 else 0.0

    # Peak demand
    optimal_peak_kw = optimal_dispatch[COL_GRID_IMPORT_KW].max()
    baseline_peak_kw = baseline_dispatch[COL_GRID_IMPORT_KW].max()
    peak_reduction_kw = baseline_peak_kw - optimal_peak_kw

    # Battery utilization
    battery_throughput_kwh = (
        (optimal_dispatch[COL_BATTERY_CHARGE_KW] + optimal_dispatch[COL_BATTERY_DISCHARGE_KW])
        * timestep_hours
    ).sum()

    # Approximate cycles (throughput / (2 * capacity))
    battery_cycles = battery_throughput_kwh / (2 * site_config.battery.capacity_kwh)

    # Energy flows
    total_import_kwh = (optimal_dispatch[COL_GRID_IMPORT_KW] * timestep_hours).sum()
    total_export_kwh = (optimal_dispatch[COL_GRID_EXPORT_KW] * timestep_hours).sum()

    return {
        "optimal_cost_gbp": optimal_cost,
        "baseline_cost_gbp": baseline_cost,
        "savings_gbp": savings_gbp,
        "savings_pct": savings_pct,
        "optimal_peak_import_kw": optimal_peak_kw,
        "baseline_peak_import_kw": baseline_peak_kw,
        "peak_reduction_kw": peak_reduction_kw,
        "battery_throughput_kwh": battery_throughput_kwh,
        "battery_cycles": battery_cycles,
        "total_import_kwh": total_import_kwh,
        "total_export_kwh": total_export_kwh,
    }
