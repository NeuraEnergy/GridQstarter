"""Build optimization model using linopy."""

import linopy
import pandas as pd

from gridq_engine.core.schemas import RunConfig, SiteConfig


def build_model(site: SiteConfig, run: RunConfig, ts: pd.DataFrame) -> linopy.Model:
    """Build optimization model for BTM dispatch.

    Args:
        site: Site configuration
        run: Run configuration
        ts: Input timeseries (must have DatetimeIndex)

    Returns:
        linopy.Model instance ready for solving
    """
    model = linopy.Model()

    # Time indices
    T = range(len(ts))
    timestep_hours = run.timestep_minutes / 60.0

    # Extract timeseries data
    load_kw = ts["load_kw"].values
    pv_kw = ts["pv_kw"].values

    # Prices (use timeseries if available, else fall back to flat rate)
    if "import_price_gbp_per_kwh" in ts.columns:
        import_price = ts["import_price_gbp_per_kwh"].values
    elif run.tariff.flat_import_price_gbp_per_kwh is not None:
        import_price = [run.tariff.flat_import_price_gbp_per_kwh] * len(ts)
    else:
        raise ValueError("No import price provided in timeseries or tariff config")

    if "export_price_gbp_per_kwh" in ts.columns:
        export_price = ts["export_price_gbp_per_kwh"].values
    elif run.tariff.flat_export_price_gbp_per_kwh is not None:
        export_price = [run.tariff.flat_export_price_gbp_per_kwh] * len(ts)
    else:
        raise ValueError("No export price provided in timeseries or tariff config")

    # Decision variables (all >= 0)
    grid_import = model.add_variables(lower=0, coords=[T], name="grid_import_kw")
    grid_export = model.add_variables(lower=0, coords=[T], name="grid_export_kw")
    battery_charge = model.add_variables(lower=0, coords=[T], name="battery_charge_kw")
    battery_discharge = model.add_variables(lower=0, coords=[T], name="battery_discharge_kw")
    soc = model.add_variables(lower=0, coords=[T], name="soc_kwh")

    # Add constraints
    from gridq_engine.model.constraints import (
        add_battery_constraints,
        add_grid_constraints,
        add_site_balance,
    )

    add_site_balance(model, T, load_kw, pv_kw, grid_import, grid_export, battery_charge, battery_discharge)
    add_battery_constraints(model, T, site.battery, run, soc, battery_charge, battery_discharge, timestep_hours)
    add_grid_constraints(model, T, site, grid_import, grid_export)

    # Add demand charge peak variable if enabled
    peak_demand = None
    if run.tariff.demand_charge_enabled:
        peak_demand = model.add_variables(lower=0, name="peak_demand_kw")
        # Peak >= grid_import[t] for all t
        for t in T:
            model.add_constraints(peak_demand >= grid_import[t], name=f"peak_ge_import_{t}")

    # Add objective
    from gridq_engine.model.objective import add_objective

    add_objective(
        model,
        T,
        grid_import,
        grid_export,
        battery_charge,
        battery_discharge,
        import_price,
        export_price,
        timestep_hours,
        site.battery.degradation_cost_gbp_per_kwh,
        run.tariff.demand_charge_gbp_per_kw if run.tariff.demand_charge_enabled else 0.0,
        peak_demand,
    )

    return model
