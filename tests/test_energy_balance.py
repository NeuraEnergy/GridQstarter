"""Test energy balance constraints."""

import numpy as np
import pandas as pd
import pytest

from gridq_engine.core.constants import (
    COL_BATTERY_CHARGE_KW,
    COL_BATTERY_DISCHARGE_KW,
    COL_GRID_EXPORT_KW,
    COL_GRID_IMPORT_KW,
    COL_LOAD_KW,
    COL_PV_KW,
    NUMERICAL_TOLERANCE,
)
from gridq_engine.core.schemas import BatteryConfig, RunConfig, SiteConfig, TariffConfig
from gridq_engine.model.build import build_model
from gridq_engine.model.solve import solve_model


@pytest.fixture
def site_config():
    """Create site configuration."""
    battery = BatteryConfig(
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        min_soc_frac=0.1,
        max_soc_frac=0.9,
        initial_soc_frac=0.5,
    )
    return SiteConfig(site_id="test_site", battery=battery)


@pytest.fixture
def run_config():
    """Create run configuration."""
    tariff = TariffConfig(
        flat_import_price_gbp_per_kwh=0.15, flat_export_price_gbp_per_kwh=0.05
    )
    return RunConfig(
        run_id="test_run",
        timestep_minutes=15,
        horizon_hours=2,
        tariff=tariff,
    )


def test_energy_balance_satisfied(site_config, run_config):
    """Test that energy balance is satisfied at every timestep.

    Energy balance: load + battery_charge + grid_export = pv + battery_discharge + grid_import
    """
    # Create timeseries with varying load and PV
    dates = pd.date_range("2024-01-01", periods=8, freq="15min")
    timeseries = pd.DataFrame(
        {
            COL_LOAD_KW: [5.0, 6.0, 4.0, 7.0, 5.0, 5.0, 6.0, 4.0],
            COL_PV_KW: [2.0, 4.0, 6.0, 3.0, 2.0, 5.0, 4.0, 3.0],
            "import_price_gbp_per_kwh": [0.15] * 8,
            "export_price_gbp_per_kwh": [0.05] * 8,
        },
        index=dates,
    )

    # Build and solve
    model = build_model(site_config, run_config, timeseries)
    dispatch, _ = solve_model(model, run_config, timeseries.index)

    # Check energy balance at each timestep
    load = timeseries[COL_LOAD_KW].values
    pv = timeseries[COL_PV_KW].values
    grid_import = dispatch[COL_GRID_IMPORT_KW].values
    grid_export = dispatch[COL_GRID_EXPORT_KW].values
    batt_charge = dispatch[COL_BATTERY_CHARGE_KW].values
    batt_discharge = dispatch[COL_BATTERY_DISCHARGE_KW].values

    # LHS: load + battery_charge + grid_export
    lhs = load + batt_charge + grid_export

    # RHS: pv + battery_discharge + grid_import
    rhs = pv + batt_discharge + grid_import

    # Check balance
    balance_error = np.abs(lhs - rhs)

    assert (
        balance_error < NUMERICAL_TOLERANCE * 10
    ).all(), f"Energy balance violated. Max error: {balance_error.max()}"


def test_energy_balance_with_high_prices(site_config, run_config):
    """Test energy balance with extreme price variations."""
    # Create timeseries with varying prices
    dates = pd.date_range("2024-01-01", periods=8, freq="15min")
    timeseries = pd.DataFrame(
        {
            COL_LOAD_KW: [5.0] * 8,
            COL_PV_KW: [3.0] * 8,
            "import_price_gbp_per_kwh": [0.05, 0.30, 0.10, 0.25, 0.05, 0.30, 0.10, 0.20],
            "export_price_gbp_per_kwh": [0.05] * 8,
        },
        index=dates,
    )

    # Build and solve
    model = build_model(site_config, run_config, timeseries)
    dispatch, _ = solve_model(model, run_config, timeseries.index)

    # Check energy balance
    load = timeseries[COL_LOAD_KW].values
    pv = timeseries[COL_PV_KW].values
    grid_import = dispatch[COL_GRID_IMPORT_KW].values
    grid_export = dispatch[COL_GRID_EXPORT_KW].values
    batt_charge = dispatch[COL_BATTERY_CHARGE_KW].values
    batt_discharge = dispatch[COL_BATTERY_DISCHARGE_KW].values

    lhs = load + batt_charge + grid_export
    rhs = pv + batt_discharge + grid_import

    balance_error = np.abs(lhs - rhs)

    assert (
        balance_error < NUMERICAL_TOLERANCE * 10
    ).all(), f"Energy balance violated. Max error: {balance_error.max()}"
