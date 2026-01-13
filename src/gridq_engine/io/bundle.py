"""Run bundle I/O operations.

A run bundle is a folder containing:
- site_config.yaml: Site configuration
- run_config.yaml: Run configuration
- timeseries.parquet: Input timeseries
- (outputs):
  - dispatch.parquet: Dispatch results
  - metrics.json: Computed metrics
  - solve_stats.json: Solver statistics
  - bundle_metadata.json: Reproducibility metadata
"""

import json
from pathlib import Path

import pandas as pd
import yaml

from gridq_engine import __version__
from gridq_engine.core.schemas import BundleMetadata, DispatchResult, RunConfig, SiteConfig
from gridq_engine.io.formats import read_parquet_timeseries, write_parquet_timeseries


def load_bundle(bundle_path: str | Path) -> tuple[SiteConfig, RunConfig, pd.DataFrame]:
    """Load a run bundle.

    Args:
        bundle_path: Path to bundle directory

    Returns:
        Tuple of (site_config, run_config, timeseries_df)
    """
    bundle_path = Path(bundle_path)

    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    # Load configs
    with open(bundle_path / "site_config.yaml") as f:
        site_config = SiteConfig(**yaml.safe_load(f))

    with open(bundle_path / "run_config.yaml") as f:
        run_config = RunConfig(**yaml.safe_load(f))

    # Load timeseries
    timeseries = read_parquet_timeseries(str(bundle_path / "timeseries.parquet"))

    return site_config, run_config, timeseries


def write_results(
    bundle_path: str | Path,
    dispatch: pd.DataFrame,
    solve_result: DispatchResult,
    metrics: dict | None = None,
) -> None:
    """Write results to bundle.

    Args:
        bundle_path: Path to bundle directory
        dispatch: Dispatch result dataframe
        solve_result: Solver result
        metrics: Optional metrics dictionary
    """
    bundle_path = Path(bundle_path)
    bundle_path.mkdir(exist_ok=True)

    # Write dispatch
    write_parquet_timeseries(dispatch, str(bundle_path / "dispatch.parquet"))

    # Write solve stats
    with open(bundle_path / "solve_stats.json", "w") as f:
        json.dump(solve_result.model_dump(), f, indent=2, default=str)

    # Write metrics if provided
    if metrics is not None:
        with open(bundle_path / "metrics.json", "w") as f:
            json.dump(metrics, f, indent=2, default=str)

    # Write metadata
    metadata = BundleMetadata(gridq_version=__version__)
    with open(bundle_path / "bundle_metadata.json", "w") as f:
        json.dump(metadata.model_dump(), f, indent=2, default=str)


def init_bundle(
    bundle_path: str | Path,
    site_config: SiteConfig,
    run_config: RunConfig,
    timeseries: pd.DataFrame,
) -> None:
    """Initialize a new run bundle.

    Args:
        bundle_path: Path to bundle directory
        site_config: Site configuration
        run_config: Run configuration
        timeseries: Input timeseries dataframe
    """
    bundle_path = Path(bundle_path)
    bundle_path.mkdir(parents=True, exist_ok=True)

    # Write configs
    with open(bundle_path / "site_config.yaml", "w") as f:
        yaml.dump(site_config.model_dump(), f, default_flow_style=False)

    with open(bundle_path / "run_config.yaml", "w") as f:
        yaml.dump(run_config.model_dump(), f, default_flow_style=False)

    # Write timeseries
    write_parquet_timeseries(timeseries, str(bundle_path / "timeseries.parquet"))


def validate_bundle(bundle_path: str | Path) -> bool:
    """Validate that a bundle has all required files.

    Args:
        bundle_path: Path to bundle directory

    Returns:
        True if valid

    Raises:
        ValueError: If bundle is invalid
    """
    bundle_path = Path(bundle_path)

    required_files = ["site_config.yaml", "run_config.yaml", "timeseries.parquet"]

    for filename in required_files:
        if not (bundle_path / filename).exists():
            raise ValueError(f"Missing required file: {filename}")

    return True
