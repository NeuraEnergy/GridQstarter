"""Optimization objective function."""

import linopy
import numpy as np


def add_objective(
    model: linopy.Model,
    T: range,
    grid_import,
    grid_export,
    battery_charge,
    battery_discharge,
    import_price: np.ndarray,
    export_price: np.ndarray,
    timestep_hours: float,
    degradation_cost_gbp_per_kwh: float,
    demand_charge_gbp_per_kw: float,
    peak_demand=None,
) -> None:
    """Add unified cost minimization objective.

    Objective = import_cost - export_revenue + demand_charge + degradation_cost

    Args:
        model: linopy Model
        T: Time indices
        grid_import: Grid import variable
        grid_export: Grid export variable
        battery_charge: Battery charge variable
        battery_discharge: Battery discharge variable
        import_price: Import price array (£/kWh)
        export_price: Export price array (£/kWh)
        timestep_hours: Timestep in hours
        degradation_cost_gbp_per_kwh: Battery degradation cost per kWh throughput
        demand_charge_gbp_per_kw: Demand charge rate (£/kW)
        peak_demand: Peak demand variable (if demand charge enabled)
    """
    # Import cost
    import_cost = sum(grid_import[t] * import_price[t] * timestep_hours for t in T)

    # Export revenue (negative cost)
    export_revenue = sum(grid_export[t] * export_price[t] * timestep_hours for t in T)

    # Degradation cost (throughput = charge + discharge)
    degradation_cost = sum(
        (battery_charge[t] + battery_discharge[t]) * timestep_hours * degradation_cost_gbp_per_kwh
        for t in T
    )

    # Total objective
    objective = import_cost - export_revenue + degradation_cost

    # Add demand charge if enabled
    if peak_demand is not None:
        objective += peak_demand * demand_charge_gbp_per_kw

    # Minimize total cost
    model.add_objective(objective, sense="min")
