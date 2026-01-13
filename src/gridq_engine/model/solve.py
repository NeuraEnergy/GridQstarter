"""Model solving and result extraction."""

import time

import linopy
import pandas as pd

from gridq_engine.core.constants import (
    COL_BATTERY_CHARGE_KW,
    COL_BATTERY_DISCHARGE_KW,
    COL_GRID_EXPORT_KW,
    COL_GRID_IMPORT_KW,
    COL_SOC_KWH,
)
from gridq_engine.core.schemas import DispatchResult, RunConfig


def solve_model(
    model: linopy.Model, run_config: RunConfig, ts_index: pd.DatetimeIndex
) -> tuple[pd.DataFrame, DispatchResult]:
    """Solve optimization model and extract results.

    Args:
        model: Built linopy Model
        run_config: Run configuration with solver settings
        ts_index: DatetimeIndex for result dataframe

    Returns:
        Tuple of (dispatch_df, solve_result)
    """
    # Solve
    start_time = time.time()

    try:
        # HiGHS doesn't support mip_gap for LP problems, only time_limit
        model.solve(
            solver_name="highs",
            time_limit=run_config.solver_time_limit_seconds,
        )
    except Exception as e:
        raise RuntimeError(f"Solver failed: {e}")

    solve_time = time.time() - start_time

    # Check solver status
    if model.status != "ok":
        raise RuntimeError(f"Solver returned non-optimal status: {model.status}")

    # Extract solution
    dispatch_df = pd.DataFrame(index=ts_index)

    dispatch_df[COL_GRID_IMPORT_KW] = model.solution["grid_import_kw"].values
    dispatch_df[COL_GRID_EXPORT_KW] = model.solution["grid_export_kw"].values
    dispatch_df[COL_BATTERY_CHARGE_KW] = model.solution["battery_charge_kw"].values
    dispatch_df[COL_BATTERY_DISCHARGE_KW] = model.solution["battery_discharge_kw"].values
    dispatch_df[COL_SOC_KWH] = model.solution["soc_kwh"].values

    # Create DispatchResult
    solve_result = DispatchResult(
        objective_value_gbp=float(model.objective.value),
        solve_time_seconds=solve_time,
        solver_status=model.status,
        solver_termination_condition=model.termination_condition if hasattr(model, "termination_condition") else "optimal",
        gap=None,  # HiGHS LP doesn't report gap for LP
    )

    return dispatch_df, solve_result
