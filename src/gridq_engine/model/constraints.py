"""Optimization model constraints."""

import linopy
import numpy as np

from gridq_engine.core.schemas import BatteryConfig, RunConfig, SiteConfig


def add_site_balance(
    model: linopy.Model,
    T: range,
    load_kw: np.ndarray,
    pv_kw: np.ndarray,
    grid_import,
    grid_export,
    battery_charge,
    battery_discharge,
) -> None:
    """Add site energy balance constraint.

    Energy balance: load + battery_charge + grid_export = pv + battery_discharge + grid_import

    Args:
        model: linopy Model
        T: Time indices
        load_kw: Load power array
        pv_kw: PV generation array
        grid_import: Grid import variable
        grid_export: Grid export variable
        battery_charge: Battery charge variable
        battery_discharge: Battery discharge variable
    """
    for t in T:
        lhs = load_kw[t] + battery_charge[t] + grid_export[t]
        rhs = pv_kw[t] + battery_discharge[t] + grid_import[t]
        model.add_constraints(lhs == rhs, name=f"site_balance_{t}")


def add_battery_constraints(
    model: linopy.Model,
    T: range,
    battery: BatteryConfig,
    run: RunConfig,
    soc,
    battery_charge,
    battery_discharge,
    timestep_hours: float,
) -> None:
    """Add battery SOC dynamics and limits.

    Args:
        model: linopy Model
        T: Time indices
        battery: Battery configuration
        run: Run configuration
        soc: SOC variable
        battery_charge: Battery charge variable
        battery_discharge: Battery discharge variable
        timestep_hours: Timestep in hours
    """
    # SOC bounds
    min_soc = battery.min_soc_frac * battery.capacity_kwh
    max_soc = battery.max_soc_frac * battery.capacity_kwh

    for t in T:
        model.add_constraints(soc[t] >= min_soc, name=f"soc_min_{t}")
        model.add_constraints(soc[t] <= max_soc, name=f"soc_max_{t}")

    # Power limits
    for t in T:
        model.add_constraints(battery_charge[t] <= battery.max_charge_kw, name=f"charge_limit_{t}")
        model.add_constraints(
            battery_discharge[t] <= battery.max_discharge_kw, name=f"discharge_limit_{t}"
        )

    # SOC dynamics
    for t in T:
        if t == 0:
            # Initial SOC
            soc_prev = battery.initial_soc_frac * battery.capacity_kwh
        else:
            soc_prev = soc[t - 1]

        # SOC[t] = SOC[t-1] + charge * efficiency * dt - discharge / efficiency * dt
        model.add_constraints(
            soc[t]
            == soc_prev
            + battery_charge[t] * battery.charge_efficiency * timestep_hours
            - battery_discharge[t] * timestep_hours / battery.discharge_efficiency,
            name=f"soc_dynamics_{t}",
        )


def add_grid_constraints(
    model: linopy.Model,
    T: range,
    site: SiteConfig,
    grid_import,
    grid_export,
) -> None:
    """Add grid import/export limits if specified.

    Args:
        model: linopy Model
        T: Time indices
        site: Site configuration
        grid_import: Grid import variable
        grid_export: Grid export variable
    """
    if site.max_grid_import_kw is not None:
        for t in T:
            model.add_constraints(
                grid_import[t] <= site.max_grid_import_kw, name=f"grid_import_limit_{t}"
            )

    if site.max_grid_export_kw is not None:
        for t in T:
            model.add_constraints(
                grid_export[t] <= site.max_grid_export_kw, name=f"grid_export_limit_{t}"
            )
