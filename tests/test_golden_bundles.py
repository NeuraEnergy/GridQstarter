"""Golden bundle tests - validate example bundles produce expected results."""

from pathlib import Path

import pytest

from gridq_engine.runners.backtest import run_backtest


@pytest.fixture
def examples_dir():
    """Get examples directory path."""
    return Path(__file__).parent.parent / "examples" / "bundles"


def test_pv_battery_tou_bundle(examples_dir):
    """Test PV + battery + ToU tariff bundle."""
    bundle_path = examples_dir / "pv_battery_tou"

    # Run backtest
    dispatch, metrics = run_backtest(str(bundle_path))

    # Assert basic sanity checks
    assert len(dispatch) > 0, "Dispatch should not be empty"

    # Should have savings (optimizer better than baseline)
    assert metrics["savings_gbp"] >= 0, "Should have non-negative savings"

    # Battery should be utilized
    assert metrics["battery_throughput_kwh"] > 0, "Battery should be used"

    # SOC should stay within bounds
    assert (dispatch["soc_kwh"] >= 0).all(), "SOC should be non-negative"

    # All power variables should be non-negative
    for col in [
        "grid_import_kw",
        "grid_export_kw",
        "battery_charge_kw",
        "battery_discharge_kw",
    ]:
        assert (dispatch[col] >= -1e-6).all(), f"{col} should be non-negative"

    print(f"✓ PV+Battery+ToU: Savings = £{metrics['savings_gbp']:.2f}")


def test_demand_charge_peak_shave_bundle(examples_dir):
    """Test demand charge + peak shaving bundle."""
    bundle_path = examples_dir / "demand_charge_peak_shave"

    # Run backtest
    dispatch, metrics = run_backtest(str(bundle_path))

    # Assert basic sanity checks
    assert len(dispatch) > 0, "Dispatch should not be empty"

    # Should reduce peak demand
    assert (
        metrics["peak_reduction_kw"] >= -1e-6
    ), "Peak should be reduced or same (non-negative reduction)"

    # Should have savings (due to demand charge reduction)
    assert metrics["savings_gbp"] >= -1e-6, "Should have non-negative savings"

    print(
        f"✓ Demand Charge: Peak reduction = {metrics['peak_reduction_kw']:.2f} kW, "
        f"Savings = £{metrics['savings_gbp']:.2f}"
    )


def test_negative_prices_edge_bundle(examples_dir):
    """Test negative prices edge case bundle."""
    bundle_path = examples_dir / "negative_prices_edge"

    # Run backtest
    dispatch, metrics = run_backtest(str(bundle_path))

    # Assert basic sanity checks
    assert len(dispatch) > 0, "Dispatch should not be empty"

    # Optimizer should handle negative prices correctly
    assert metrics["optimal_cost_gbp"] <= metrics["baseline_cost_gbp"] + 1e-3, (
        "Optimal should not be worse than baseline"
    )

    # All power variables should be non-negative
    for col in [
        "grid_import_kw",
        "grid_export_kw",
        "battery_charge_kw",
        "battery_discharge_kw",
    ]:
        assert (dispatch[col] >= -1e-6).all(), f"{col} should be non-negative"

    print(f"✓ Negative Prices: Savings = £{metrics['savings_gbp']:.2f}")


def test_all_bundles_solve_quickly(examples_dir):
    """Test that all bundles solve within reasonable time."""
    import json

    for bundle_name in ["pv_battery_tou", "demand_charge_peak_shave", "negative_prices_edge"]:
        bundle_path = examples_dir / bundle_name

        # Run backtest (results already written)
        # Read solve stats
        solve_stats_file = bundle_path / "solve_stats.json"

        if solve_stats_file.exists():
            with open(solve_stats_file) as f:
                solve_stats = json.load(f)

            solve_time = solve_stats["solve_time_seconds"]

            # Should solve in < 10 seconds (generous for CI)
            assert solve_time < 10.0, f"{bundle_name} took too long: {solve_time:.2f}s"

            print(f"✓ {bundle_name}: Solved in {solve_time:.2f}s")
