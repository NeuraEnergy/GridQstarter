"""Forecast provider interface."""

from datetime import datetime
from typing import Protocol

import pandas as pd


class ForecastProvider(Protocol):
    """Protocol for forecast providers.

    Forecast providers take current time and horizon and return
    a dataframe with forecasted values for required columns.
    """

    def forecast(self, ts_now: datetime, horizon_hours: int) -> pd.DataFrame:
        """Generate forecast for given horizon.

        Args:
            ts_now: Current timestamp
            horizon_hours: Forecast horizon in hours

        Returns:
            DataFrame with DatetimeIndex and forecasted columns:
            - load_kw
            - pv_kw
            - import_price_gbp_per_kwh
            - export_price_gbp_per_kwh
        """
        ...
