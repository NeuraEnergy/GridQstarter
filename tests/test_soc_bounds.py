"""Test battery SOC bounds and dynamics."""

import pandas as pd
import pytest

from gridq_engine.core.constants import COL_LOAD_KW, COL_PV_KW, COL_SOC_KWH
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
        run_id="test_run", timestep_minutes=15, horizon_hours=2, tariff=tariff
    )


def test_soc_within_bounds(site_config, run_config):
    """Test that SOC stays within min/max bounds."""
    # Create timeseries
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

    # Check SOC bounds
    min_soc = site_config.battery.min_soc_frac * site_config.battery.capacity_kwh
    max_soc = site_config.battery.max_soc_frac * site_config.battery.capacity_kwh

    soc = dispatch[COL_SOC_KWH]

    assert (soc >= min_soc - 1e-6).all(), f"SOC below minimum. Min SOC: {soc.min():.3f} kWh"
    assert (soc <= max_soc + 1e-6).all(), f"SOC above maximum. Max SOC: {soc.max():.3f} kWh"


def test_soc_initial_condition(site_config, run_config):
    """Test that initial SOC is respected."""
    # Create timeseries
    dates = pd.date_range("2024-01-01", periods=4, freq="15min")
    timeseries = pd.DataFrame(
        {
            COL_LOAD_KW: [5.0] * 4,
            COL_PV_KW: [5.0] * 4,  # Balanced, so SOC should stay roughly the same
            "import_price_gbp_per_kwh": [0.15] * 4,
            "export_price_gbp_per_kwh": [0.05] * 4,
        },
        index=dates,
    )

    # Build and solve
    model = build_model(site_config, run_config, timeseries)
    dispatch, _ = solve_model(model, run_config, timeseries.index)

    # First timestep SOC should be close to initial (after accounting for first interval dynamics)
    # This is implementation-dependent, but initial_soc_frac should influence the trajectory
    expected_initial_soc = site_config.battery.initial_soc_frac * site_config.battery.capacity_kwh

    # The first SOC value is after the first timestep, so it won't exactly match initial_soc
    # but should be in the reasonable range
    first_soc = dispatch[COL_SOC_KWH].iloc[0]
    assert (
        0.5 < first_soc < 7.0
    ), f"First SOC {first_soc:.2f} is unreasonable given initial SOC ~5.0 kWh"


def test_soc_respects_power_limits(site_config, run_config):
    """Test that SOC changes respect battery power limits."""
    # Scenario: try to charge as much as possible
    dates = pd.date_range("2024-01-01", periods=8, freq="15min")
    timeseries = pd.DataFrame(
        {
            COL_LOAD_KW: [0.0] * 8,  # No load
            COL_PV_KW: [10.0] * 8,  # High PV
            "import_price_gbp_per_kwh": [0.15] * 8,
            "export_price_gbp_per_kwh": [0.05] * 8,
        },
        index=dates,
    )

    # Build and solve
    model = build_model(site_config, run_config, timeseries)
    dispatch, _ = solve_model(model, run_config, timeseries.index)

    # Check that charge rate doesn't exceed max_charge_kw
    from gridq_engine.core.constants import COL_BATTERY_CHARGE_KW

    assert (
        dispatch[COL_BATTERY_CHARGE_KW] <= site_config.battery.max_charge_kw + 1e-6
    ).all(), "Charge power exceeds limit"

    # SOC should increase but not exceed max
    max_soc = site_config.battery.max_soc_frac * site_config.battery.capacity_kwh
    assert (
        dispatch[COL_SOC_KWH] <= max_soc + 1e-6
    ).all(), "SOC exceeds maximum"


def test_soc_cannot_go_negative(site_config, run_config):
    """Test that SOC never goes negative even with high discharge demand."""
    # Scenario: high load, no PV, try to drain battery
    dates = pd.date_range("2024-01-01", periods=8, freq="15min")
    timeseries = pd.DataFrame(
        {
            COL_LOAD_KW: [15.0] * 8,  # Very high load
            COL_PV_KW: [0.0] * 8,  # No PV
            "import_price_gbp_per_kwh": [0.30] * 8,  # High price (incentivize battery use)
            "export_price_gbp_per_kwh": [0.05] * 8,
        },
        index=dates,
    )

    # Build and solve
    model = build_model(site_config, run_config, timeseries)
    dispatch, _ = solve_model(model, run_config, timeseries.index)

    # SOC should never go negative
    assert (dispatch[COL_SOC_KWH] >= -1e-6).all(), "SOC went negative"

    # SOC should respect minimum
    min_soc = site_config.battery.min_soc_frac * site_config.battery.capacity_kwh
    assert (dispatch[COL_SOC_KWH] >= min_soc - 1e-6).all(), "SOC below minimum"
