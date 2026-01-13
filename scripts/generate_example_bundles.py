"""Generate synthetic example bundles for testing and demonstration."""

import numpy as np
import pandas as pd
import yaml
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gridq_engine.core.schemas import BatteryConfig, SiteConfig, RunConfig, TariffConfig
from gridq_engine.io.bundle import init_bundle


def generate_pv_battery_tou():
    """Generate PV + battery + time-of-use tariff bundle."""
    print("Generating pv_battery_tou bundle...")

    # Site config
    battery = BatteryConfig(
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        min_soc_frac=0.1,
        max_soc_frac=0.9,
        initial_soc_frac=0.5,
        degradation_cost_gbp_per_kwh=0.01,
    )

    site_config = SiteConfig(
        site_id="example_site_001",
        battery=battery,
        max_grid_import_kw=None,
        max_grid_export_kw=None,
    )

    # Run config with ToU tariff
    tariff = TariffConfig(
        flat_import_price_gbp_per_kwh=None,  # Will use timeseries
        flat_export_price_gbp_per_kwh=None,
        demand_charge_enabled=False,
        demand_charge_gbp_per_kw=0.0,
    )

    run_config = RunConfig(
        run_id="backtest_001",
        timestep_minutes=15,
        horizon_hours=24,
        tariff=tariff,
        solver_time_limit_seconds=60.0,
        solver_gap_tolerance=1e-4,
    )

    # Generate synthetic timeseries (1 week, 15-min resolution)
    num_days = 7
    timestep_minutes = 15
    num_steps = int(num_days * 24 * 60 / timestep_minutes)

    dates = pd.date_range("2024-01-01", periods=num_steps, freq=f"{timestep_minutes}min")

    # Synthetic load (higher during day)
    hour_of_day = dates.hour
    load_base = 2.0
    load_variation = 3.0 * np.sin((hour_of_day - 6) * np.pi / 12)
    load_kw = np.maximum(load_base + load_variation, 0.5) + np.random.normal(0, 0.2, num_steps)
    load_kw = np.maximum(load_kw, 0)

    # Synthetic PV (solar profile)
    pv_kw = np.zeros(num_steps)
    for i, dt in enumerate(dates):
        if 7 <= dt.hour <= 17:
            # Bell curve for solar generation
            pv_kw[i] = 8.0 * np.sin((dt.hour - 7) * np.pi / 10) ** 2
    pv_kw += np.random.normal(0, 0.1, num_steps)
    pv_kw = np.maximum(pv_kw, 0)

    # Time-of-use import prices (peak 4pm-9pm)
    import_price = np.zeros(num_steps)
    for i, dt in enumerate(dates):
        if 16 <= dt.hour < 21:
            import_price[i] = 0.30  # Peak rate
        elif 7 <= dt.hour < 16:
            import_price[i] = 0.15  # Day rate
        else:
            import_price[i] = 0.10  # Night rate

    # Flat export price
    export_price = np.full(num_steps, 0.05)

    timeseries = pd.DataFrame({
        "load_kw": load_kw,
        "pv_kw": pv_kw,
        "import_price_gbp_per_kwh": import_price,
        "export_price_gbp_per_kwh": export_price,
    }, index=dates)

    # Create bundle
    bundle_path = Path(__file__).parent.parent / "examples" / "bundles" / "pv_battery_tou"
    init_bundle(bundle_path, site_config, run_config, timeseries)
    print(f"✓ Created {bundle_path}")


def generate_demand_charge_peak_shave():
    """Generate demand charge + peak shaving bundle (no PV)."""
    print("Generating demand_charge_peak_shave bundle...")

    # Site config (no PV, battery for peak shaving)
    battery = BatteryConfig(
        capacity_kwh=20.0,
        max_charge_kw=10.0,
        max_discharge_kw=10.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        min_soc_frac=0.1,
        max_soc_frac=0.9,
        initial_soc_frac=0.5,
        degradation_cost_gbp_per_kwh=0.01,
    )

    site_config = SiteConfig(
        site_id="example_site_002",
        battery=battery,
        max_grid_import_kw=None,
        max_grid_export_kw=None,
    )

    # Run config with demand charge
    tariff = TariffConfig(
        flat_import_price_gbp_per_kwh=0.15,
        flat_export_price_gbp_per_kwh=0.0,  # No export
        demand_charge_enabled=True,
        demand_charge_gbp_per_kw=20.0,  # £20/kW peak demand
    )

    run_config = RunConfig(
        run_id="backtest_002",
        timestep_minutes=15,
        horizon_hours=24,
        tariff=tariff,
        solver_time_limit_seconds=60.0,
        solver_gap_tolerance=1e-4,
    )

    # Generate synthetic timeseries (1 week)
    num_days = 7
    timestep_minutes = 15
    num_steps = int(num_days * 24 * 60 / timestep_minutes)

    dates = pd.date_range("2024-01-01", periods=num_steps, freq=f"{timestep_minutes}min")

    # Load with pronounced peaks during business hours
    hour_of_day = dates.hour
    load_kw = np.zeros(num_steps)
    for i, dt in enumerate(dates):
        if 9 <= dt.hour < 17:
            # Business hours with peaks
            load_kw[i] = 15.0 + 5.0 * np.sin((dt.hour - 9) * np.pi / 8)
            # Add occasional spikes
            if np.random.random() < 0.1:
                load_kw[i] += 10.0
        else:
            load_kw[i] = 5.0

    load_kw += np.random.normal(0, 0.5, num_steps)
    load_kw = np.maximum(load_kw, 0)

    # No PV
    pv_kw = np.zeros(num_steps)

    # Flat prices (demand charge is the main driver)
    import_price = np.full(num_steps, 0.15)
    export_price = np.zeros(num_steps)

    timeseries = pd.DataFrame({
        "load_kw": load_kw,
        "pv_kw": pv_kw,
        "import_price_gbp_per_kwh": import_price,
        "export_price_gbp_per_kwh": export_price,
    }, index=dates)

    # Create bundle
    bundle_path = Path(__file__).parent.parent / "examples" / "bundles" / "demand_charge_peak_shave"
    init_bundle(bundle_path, site_config, run_config, timeseries)
    print(f"✓ Created {bundle_path}")


def generate_negative_prices_edge():
    """Generate bundle with negative prices to test edge cases."""
    print("Generating negative_prices_edge bundle...")

    # Site config
    battery = BatteryConfig(
        capacity_kwh=15.0,
        max_charge_kw=7.5,
        max_discharge_kw=7.5,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        min_soc_frac=0.1,
        max_soc_frac=0.9,
        initial_soc_frac=0.5,
        degradation_cost_gbp_per_kwh=0.01,
    )

    site_config = SiteConfig(
        site_id="example_site_003",
        battery=battery,
        max_grid_import_kw=None,
        max_grid_export_kw=None,
    )

    # Run config
    tariff = TariffConfig(
        flat_import_price_gbp_per_kwh=None,
        flat_export_price_gbp_per_kwh=None,
        demand_charge_enabled=False,
        demand_charge_gbp_per_kw=0.0,
    )

    run_config = RunConfig(
        run_id="backtest_003",
        timestep_minutes=15,
        horizon_hours=24,
        tariff=tariff,
        solver_time_limit_seconds=60.0,
        solver_gap_tolerance=1e-4,
    )

    # Generate synthetic timeseries (3 days)
    num_days = 3
    timestep_minutes = 15
    num_steps = int(num_days * 24 * 60 / timestep_minutes)

    dates = pd.date_range("2024-01-01", periods=num_steps, freq=f"{timestep_minutes}min")

    # Simple load
    load_kw = 5.0 + np.random.normal(0, 0.5, num_steps)
    load_kw = np.maximum(load_kw, 0)

    # Moderate PV
    pv_kw = np.zeros(num_steps)
    for i, dt in enumerate(dates):
        if 8 <= dt.hour <= 16:
            pv_kw[i] = 6.0 * np.sin((dt.hour - 8) * np.pi / 8) ** 2

    # Import prices with occasional negative values (wind/solar surplus)
    import_price = np.full(num_steps, 0.15)
    for i, dt in enumerate(dates):
        # Negative import prices during night (wind surplus)
        if 2 <= dt.hour <= 5:
            import_price[i] = -0.05
        # Negative import prices during solar peak (oversupply)
        elif 12 <= dt.hour <= 14 and np.random.random() < 0.3:
            import_price[i] = -0.02

    # Export prices (sometimes negative = must pay to export)
    export_price = np.full(num_steps, 0.05)
    for i, dt in enumerate(dates):
        # Negative export prices during oversupply
        if 12 <= dt.hour <= 14 and np.random.random() < 0.2:
            export_price[i] = -0.01

    timeseries = pd.DataFrame({
        "load_kw": load_kw,
        "pv_kw": pv_kw,
        "import_price_gbp_per_kwh": import_price,
        "export_price_gbp_per_kwh": export_price,
    }, index=dates)

    # Create bundle
    bundle_path = Path(__file__).parent.parent / "examples" / "bundles" / "negative_prices_edge"
    init_bundle(bundle_path, site_config, run_config, timeseries)
    print(f"✓ Created {bundle_path}")


if __name__ == "__main__":
    print("Generating example bundles...\n")
    generate_pv_battery_tou()
    generate_demand_charge_peak_shave()
    generate_negative_prices_edge()
    print("\n✓ All example bundles generated")
