"""Test sign conventions and units."""

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
)
from gridq_engine.core.schemas import BatteryConfig, RunConfig, SiteConfig, TariffConfig
from gridq_engine.model.build import build_model
from gridq_engine.model.solve import solve_model


@pytest.fixture
def simple_site_config():
    """Create a simple site configuration."""
    battery = BatteryConfig(
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        min_soc_frac=0.1,
        max_soc_frac=0.9,
        initial_soc_frac=0.5,
        degradation_cost_gbp_per_kwh=0.0,
    )

    return SiteConfig(site_id="test_site", battery=battery)


@pytest.fixture
def simple_run_config():
    """Create a simple run configuration."""
    tariff = TariffConfig(
        flat_import_price_gbp_per_kwh=0.15,
        flat_export_price_gbp_per_kwh=0.05,
        demand_charge_enabled=False,
    )

    return RunConfig(
        run_id="test_run",
        timestep_minutes=15,
        horizon_hours=1,
        tariff=tariff,
        solver_time_limit_seconds=30.0,
    )


def test_all_variables_non_negative(simple_site_config, simple_run_config):
    """Test that all power variables are non-negative."""
    # Create simple timeseries
    dates = pd.date_range("2024-01-01", periods=4, freq="15min")
    timeseries = pd.DataFrame(
        {
            COL_LOAD_KW: [5.0, 5.0, 5.0, 5.0],
            COL_PV_KW: [3.0, 3.0, 3.0, 3.0],
            "import_price_gbp_per_kwh": [0.15, 0.15, 0.15, 0.15],
            "export_price_gbp_per_kwh": [0.05, 0.05, 0.05, 0.05],
        },
        index=dates,
    )

    # Build and solve
    model = build_model(simple_site_config, simple_run_config, timeseries)
    dispatch, _ = solve_model(model, simple_run_config, timeseries.index)

    # All variables should be non-negative
    power_cols = [
        COL_GRID_IMPORT_KW,
        COL_GRID_EXPORT_KW,
        COL_BATTERY_CHARGE_KW,
        COL_BATTERY_DISCHARGE_KW,
    ]

    for col in power_cols:
        assert (
            dispatch[col] >= -1e-6
        ).all(), f"{col} has negative values (min: {dispatch[col].min()})"


def test_import_when_load_exceeds_pv(simple_site_config, simple_run_config):
    """Test that grid import > 0 when load exceeds PV (and battery empty)."""
    # Scenario: high load, low PV, battery cannot help
    dates = pd.date_range("2024-01-01", periods=4, freq="15min")
    timeseries = pd.DataFrame(
        {
            COL_LOAD_KW: [10.0, 10.0, 10.0, 10.0],  # High load
            COL_PV_KW: [1.0, 1.0, 1.0, 1.0],  # Low PV
            "import_price_gbp_per_kwh": [0.15, 0.15, 0.15, 0.15],
            "export_price_gbp_per_kwh": [0.05, 0.05, 0.05, 0.05],
        },
        index=dates,
    )

    # Build and solve
    model = build_model(simple_site_config, simple_run_config, timeseries)
    dispatch, _ = solve_model(model, simple_run_config, timeseries.index)

    # Should have grid import in at least some timesteps
    assert dispatch[COL_GRID_IMPORT_KW].sum() > 0, "Should import from grid when load exceeds PV"


def test_export_when_pv_exceeds_load(simple_site_config, simple_run_config):
    """Test that grid export > 0 when PV exceeds load (and battery full)."""
    # High PV, low load
    dates = pd.date_range("2024-01-01", periods=8, freq="15min")  # Longer to fill battery
    timeseries = pd.DataFrame(
        {
            COL_LOAD_KW: [1.0] * 8,  # Low load
            COL_PV_KW: [8.0] * 8,  # High PV
            "import_price_gbp_per_kwh": [0.15] * 8,
            "export_price_gbp_per_kwh": [0.05] * 8,
        },
        index=dates,
    )

    # Build and solve
    model = build_model(simple_site_config, simple_run_config, timeseries)
    dispatch, _ = solve_model(model, simple_run_config, timeseries.index)

    # Should have grid export (after battery fills up)
    assert (
        dispatch[COL_GRID_EXPORT_KW].sum() > 0
    ), "Should export to grid when PV exceeds load + battery capacity"


def test_no_simultaneous_charge_discharge(simple_site_config, simple_run_config):
    """Test that battery doesn't charge and discharge simultaneously (mostly)."""
    # Create timeseries
    dates = pd.date_range("2024-01-01", periods=4, freq="15min")
    timeseries = pd.DataFrame(
        {
            COL_LOAD_KW: [5.0, 5.0, 5.0, 5.0],
            COL_PV_KW: [3.0, 3.0, 3.0, 3.0],
            "import_price_gbp_per_kwh": [0.15, 0.15, 0.15, 0.15],
            "export_price_gbp_per_kwh": [0.05, 0.05, 0.05, 0.05],
        },
        index=dates,
    )

    # Build and solve
    model = build_model(simple_site_config, simple_run_config, timeseries)
    dispatch, _ = solve_model(model, simple_run_config, timeseries.index)

    # Check for simultaneous charge/discharge (allow small tolerance)
    simultaneous = (dispatch[COL_BATTERY_CHARGE_KW] > 1e-3) & (
        dispatch[COL_BATTERY_DISCHARGE_KW] > 1e-3
    )

    # Should have minimal or no simultaneous charge/discharge
    # (LP may have small simultaneous flows due to tie-breaking)
    assert (
        simultaneous.sum() <= len(dispatch) * 0.1
    ), "Too much simultaneous charge/discharge"
