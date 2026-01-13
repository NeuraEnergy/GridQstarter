"""Forecast provider implementations."""

from datetime import datetime

import pandas as pd


class HistoricalReplayProvider:
    """Perfect foresight provider for backtesting.

    Returns actual historical values from the full dataset.
    """

    def __init__(self, historical_data: pd.DataFrame):
        """Initialize with full historical dataset.

        Args:
            historical_data: Full timeseries with DatetimeIndex
        """
        self.historical_data = historical_data

    def forecast(self, ts_now: datetime, horizon_hours: int) -> pd.DataFrame:
        """Return actual historical values for the forecast horizon.

        Args:
            ts_now: Current timestamp
            horizon_hours: Forecast horizon in hours

        Returns:
            DataFrame with actual historical values
        """
        # Find the window
        end_time = ts_now + pd.Timedelta(hours=horizon_hours)

        # Slice the historical data
        forecast_df = self.historical_data.loc[ts_now:end_time].copy()

        # Exclude the end_time itself if it exists
        if len(forecast_df) > 0 and forecast_df.index[-1] >= end_time:
            forecast_df = forecast_df.iloc[:-1]

        if len(forecast_df) == 0:
            raise ValueError(f"No historical data available for forecast at {ts_now}")

        return forecast_df


class PersistenceProvider:
    """Persistence (naive) forecast provider.

    Repeats the last observed values for the entire forecast horizon.
    """

    def __init__(self, historical_data: pd.DataFrame, timestep_minutes: int):
        """Initialize with historical data for lookback.

        Args:
            historical_data: Historical timeseries with DatetimeIndex
            timestep_minutes: Timestep in minutes
        """
        self.historical_data = historical_data
        self.timestep_minutes = timestep_minutes

    def forecast(self, ts_now: datetime, horizon_hours: int) -> pd.DataFrame:
        """Generate persistence forecast.

        Args:
            ts_now: Current timestamp
            horizon_hours: Forecast horizon in hours

        Returns:
            DataFrame with repeated last observed values
        """
        # Get last observed value
        if ts_now not in self.historical_data.index:
            # Find the closest prior timestamp
            prior_data = self.historical_data.loc[:ts_now]
            if len(prior_data) == 0:
                raise ValueError(f"No historical data available before {ts_now}")
            last_obs = prior_data.iloc[-1]
        else:
            last_obs = self.historical_data.loc[ts_now]

        # Generate forecast timestamps
        num_steps = int(horizon_hours * 60 / self.timestep_minutes)
        forecast_index = pd.date_range(
            start=ts_now + pd.Timedelta(minutes=self.timestep_minutes),
            periods=num_steps,
            freq=f"{self.timestep_minutes}min",
        )

        # Repeat last observation
        forecast_df = pd.DataFrame(
            {col: [last_obs[col]] * num_steps for col in last_obs.index}, index=forecast_index
        )

        return forecast_df
