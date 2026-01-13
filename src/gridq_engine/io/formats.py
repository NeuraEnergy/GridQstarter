"""Data format helpers for Parquet I/O."""

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from gridq_engine.core.constants import REQUIRED_INPUT_COLUMNS


def ensure_columns(df: pd.DataFrame, required_columns: list[str]) -> None:
    """Ensure dataframe has required columns.

    Args:
        df: DataFrame to check
        required_columns: List of required column names

    Raises:
        ValueError: If any required columns are missing
    """
    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def read_parquet_timeseries(path: str) -> pd.DataFrame:
    """Read timeseries from Parquet file.

    Args:
        path: Path to Parquet file

    Returns:
        DataFrame with DatetimeIndex
    """
    df = pd.read_parquet(path)

    # Ensure timestamp column exists
    if "timestamp" not in df.columns:
        raise ValueError("Timeseries must have 'timestamp' column")

    # Convert to datetime and set as index
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp")
    df.index.name = "timestamp"

    return df


def write_parquet_timeseries(df: pd.DataFrame, path: str) -> None:
    """Write timeseries to Parquet file.

    Args:
        df: DataFrame with DatetimeIndex
        path: Output path
    """
    # Ensure index has the right name before resetting
    df_copy = df.copy()
    df_copy.index.name = "timestamp"

    # Reset index to save timestamp as column
    df_out = df_copy.reset_index()

    # Write with pyarrow
    table = pa.Table.from_pandas(df_out)
    pq.write_table(table, path, compression="snappy")
