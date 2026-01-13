"""Backtest runner for historical evaluation.

Runs optimization over full historical period using perfect foresight
within each optimization horizon (rolling-horizon backtest).
"""

from gridq_engine.core.baseline import compute_baseline_dispatch
from gridq_engine.core.constants import COL_EXPORT_PRICE, COL_IMPORT_PRICE
from gridq_engine.core.metrics import compute_metrics
from gridq_engine.core.validate import validate_dispatch_result, validate_timeseries
from gridq_engine.io.bundle import load_bundle, write_results
from gridq_engine.model.build import build_model
from gridq_engine.model.solve import solve_model


def run_backtest(bundle_path: str) -> tuple:
    """Run backtest on a bundle.

    For MVP, we run a single full-horizon optimization (not rolling).
    Future versions can implement rolling horizon with receding horizon control.

    Args:
        bundle_path: Path to run bundle

    Returns:
        Tuple of (dispatch_df, metrics)
    """
    print(f"Loading bundle from {bundle_path}...")
    site_config, run_config, timeseries = load_bundle(bundle_path)

    # Validate input
    validate_timeseries(timeseries, run_config.timestep_minutes)

    print(f"Site: {site_config.site_id}")
    print(f"Run: {run_config.run_id}")
    print(
        f"Timeseries: {len(timeseries)} timesteps from {timeseries.index[0]} to {timeseries.index[-1]}"
    )

    # Build and solve model
    print("Building optimization model...")
    model = build_model(site_config, run_config, timeseries)

    print("Solving optimization model...")
    dispatch_df, solve_result = solve_model(model, run_config, timeseries.index)

    print(f"Solve completed in {solve_result.solve_time_seconds:.2f}s")
    print(f"Objective value: £{solve_result.objective_value_gbp:.2f}")

    # Validate result
    validate_dispatch_result(dispatch_df, site_config)
    print("✓ Dispatch validation passed")

    # Merge prices into dispatch for metrics calculation
    dispatch_df[COL_IMPORT_PRICE] = timeseries[COL_IMPORT_PRICE].values
    dispatch_df[COL_EXPORT_PRICE] = timeseries[COL_EXPORT_PRICE].values

    # Compute baseline
    print("Computing baseline dispatch...")
    timestep_hours = run_config.timestep_minutes / 60.0
    baseline_dispatch = compute_baseline_dispatch(timeseries, site_config, timestep_hours)

    # Merge prices into baseline
    baseline_dispatch[COL_IMPORT_PRICE] = timeseries[COL_IMPORT_PRICE].values
    baseline_dispatch[COL_EXPORT_PRICE] = timeseries[COL_EXPORT_PRICE].values

    # Compute metrics
    print("Computing metrics...")
    metrics = compute_metrics(dispatch_df, baseline_dispatch, site_config, run_config, timestep_hours)

    print(f"\n✓ Backtest completed")
    print(f"Savings vs baseline: £{metrics['savings_gbp']:.2f} ({metrics['savings_pct']:.1f}%)")
    print(f"Peak reduction: {metrics['peak_reduction_kw']:.2f} kW")
    print(f"Battery cycles: {metrics['battery_cycles']:.2f}")

    # Write results
    print(f"\nWriting results to {bundle_path}...")
    write_results(bundle_path, dispatch_df, solve_result, metrics)

    return dispatch_df, metrics
