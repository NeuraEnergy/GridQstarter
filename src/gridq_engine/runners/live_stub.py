"""Live operations runner stub.

Placeholder for future live dispatch optimization.
"""

from datetime import datetime


def run_live_dispatch(
    site_config_path: str, current_state: dict, forecast_provider
) -> dict:
    """Run live dispatch optimization.

    This is a stub for future implementation. Live ops will:
    - Load current site state (SOC, meter readings)
    - Get forecast from provider
    - Run single-horizon optimization
    - Return dispatch schedule for actuation
    - Handle safety constraints and failsafes

    Args:
        site_config_path: Path to site configuration
        current_state: Dict with current SOC, timestamp, etc.
        forecast_provider: ForecastProvider instance

    Returns:
        Dictionary with dispatch schedule

    Raises:
        NotImplementedError: This is a stub
    """
    raise NotImplementedError(
        "Live dispatch runner not yet implemented. "
        "This will be added in a future sprint for real-time operations."
    )
