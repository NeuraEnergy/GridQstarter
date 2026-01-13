"""Input validation beyond Pydantic schemas."""

import pandas as pd

from gridq_engine.core.constants import REQUIRED_INPUT_COLUMNS


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


def validate_timeseries(df: pd.DataFrame, expected_timestep_minutes: int) -> None:
    """Validate input timeseries dataframe.

    Args:
        df: Input timeseries with datetime index
        expected_timestep_minutes: Expected timestep in minutes

    Raises:
        ValidationError: If validation fails
    """
    # Check required columns
    missing_cols = set(REQUIRED_INPUT_COLUMNS) - set(df.columns)
    if missing_cols:
        raise ValidationError(f"Missing required columns: {missing_cols}")

    # Check index is DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValidationError("Timeseries must have DatetimeIndex")

    # Check monotonic increasing timestamps
    if not df.index.is_monotonic_increasing:
        raise ValidationError("Timestamps must be monotonic increasing")

    # Check for duplicates
    if df.index.has_duplicates:
        raise ValidationError("Duplicate timestamps found")

    # Check timestep consistency
    if len(df) > 1:
        time_diffs = df.index.to_series().diff().dropna()
        expected_delta = pd.Timedelta(minutes=expected_timestep_minutes)

        if not (time_diffs == expected_delta).all():
            raise ValidationError(
                f"Inconsistent timestep. Expected {expected_timestep_minutes} minutes. "
                f"Found: {time_diffs.value_counts().to_dict()}"
            )

    # Check non-negative values for physical quantities
    for col in [col for col in REQUIRED_INPUT_COLUMNS if col in df.columns]:
        if col.endswith("_kw"):  # Power columns should be non-negative
            if (df[col] < 0).any():
                raise ValidationError(f"Column {col} contains negative values")

    # Check for NaN values
    if df[REQUIRED_INPUT_COLUMNS].isna().any().any():
        nan_cols = df[REQUIRED_INPUT_COLUMNS].columns[df[REQUIRED_INPUT_COLUMNS].isna().any()].tolist()
        raise ValidationError(f"NaN values found in columns: {nan_cols}")


def validate_dispatch_result(df: pd.DataFrame, site_config) -> None:
    """Validate dispatch result satisfies physical constraints.

    Args:
        df: Dispatch result dataframe
        site_config: SiteConfig instance

    Raises:
        ValidationError: If constraints are violated
    """
    from gridq_engine.core.constants import (
        COL_BATTERY_CHARGE_KW,
        COL_BATTERY_DISCHARGE_KW,
        COL_GRID_EXPORT_KW,
        COL_GRID_IMPORT_KW,
        COL_SOC_KWH,
        NUMERICAL_TOLERANCE,
    )

    # Check all power variables are non-negative
    power_cols = [
        COL_GRID_IMPORT_KW,
        COL_GRID_EXPORT_KW,
        COL_BATTERY_CHARGE_KW,
        COL_BATTERY_DISCHARGE_KW,
    ]
    for col in power_cols:
        if (df[col] < -NUMERICAL_TOLERANCE).any():
            raise ValidationError(f"{col} has negative values")

    # Check SOC bounds
    battery = site_config.battery
    min_soc = battery.min_soc_frac * battery.capacity_kwh
    max_soc = battery.max_soc_frac * battery.capacity_kwh

    if (df[COL_SOC_KWH] < min_soc - NUMERICAL_TOLERANCE).any():
        raise ValidationError(f"SOC below minimum: {min_soc} kWh")

    if (df[COL_SOC_KWH] > max_soc + NUMERICAL_TOLERANCE).any():
        raise ValidationError(f"SOC above maximum: {max_soc} kWh")

    # Check battery power limits
    if (df[COL_BATTERY_CHARGE_KW] > battery.max_charge_kw + NUMERICAL_TOLERANCE).any():
        raise ValidationError(f"Charge power exceeds limit: {battery.max_charge_kw} kW")

    if (df[COL_BATTERY_DISCHARGE_KW] > battery.max_discharge_kw + NUMERICAL_TOLERANCE).any():
        raise ValidationError(f"Discharge power exceeds limit: {battery.max_discharge_kw} kW")

    # Check grid limits if specified
    if site_config.max_grid_import_kw is not None:
        if (df[COL_GRID_IMPORT_KW] > site_config.max_grid_import_kw + NUMERICAL_TOLERANCE).any():
            raise ValidationError(f"Grid import exceeds limit: {site_config.max_grid_import_kw} kW")

    if site_config.max_grid_export_kw is not None:
        if (df[COL_GRID_EXPORT_KW] > site_config.max_grid_export_kw + NUMERICAL_TOLERANCE).any():
            raise ValidationError(f"Grid export exceeds limit: {site_config.max_grid_export_kw} kW")
