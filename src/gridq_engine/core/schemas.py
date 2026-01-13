"""Pydantic schemas for configuration and data validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BatteryConfig(BaseModel):
    """Battery asset configuration."""

    capacity_kwh: float = Field(..., gt=0, description="Battery capacity in kWh")
    max_charge_kw: float = Field(..., gt=0, description="Max charge power in kW")
    max_discharge_kw: float = Field(..., gt=0, description="Max discharge power in kW")
    charge_efficiency: float = Field(default=0.95, ge=0, le=1, description="Round-trip charge efficiency")
    discharge_efficiency: float = Field(default=0.95, ge=0, le=1, description="Round-trip discharge efficiency")
    min_soc_frac: float = Field(default=0.1, ge=0, le=1, description="Minimum state of charge fraction")
    max_soc_frac: float = Field(default=0.9, ge=0, le=1, description="Maximum state of charge fraction")
    initial_soc_frac: float = Field(default=0.5, ge=0, le=1, description="Initial SOC fraction")
    degradation_cost_gbp_per_kwh: float = Field(default=0.0, ge=0, description="Linear degradation cost per kWh throughput")


class TariffConfig(BaseModel):
    """Tariff configuration (prices in timeseries take precedence if provided)."""

    # If these are None, prices must be provided in timeseries
    flat_import_price_gbp_per_kwh: Optional[float] = Field(default=None, ge=0)
    flat_export_price_gbp_per_kwh: Optional[float] = Field(default=None, ge=0)

    # Demand charge (£/kW of peak import in billing period)
    demand_charge_enabled: bool = Field(default=False)
    demand_charge_gbp_per_kw: float = Field(default=0.0, ge=0)


class SiteConfig(BaseModel):
    """Site asset and constraint configuration."""

    site_id: str = Field(..., description="Unique site identifier")
    battery: BatteryConfig
    max_grid_import_kw: Optional[float] = Field(default=None, gt=0, description="Grid import limit (if any)")
    max_grid_export_kw: Optional[float] = Field(default=None, gt=0, description="Grid export limit (if any)")


class RunConfig(BaseModel):
    """Run-specific configuration."""

    run_id: str = Field(..., description="Unique run identifier")
    timestep_minutes: int = Field(default=15, gt=0, description="Timestep in minutes")
    horizon_hours: int = Field(default=24, gt=0, description="Optimization horizon in hours")
    tariff: TariffConfig = Field(default_factory=TariffConfig)
    solver_time_limit_seconds: float = Field(default=60.0, gt=0)
    solver_gap_tolerance: float = Field(default=1e-4, ge=0)

    @field_validator("timestep_minutes")
    @classmethod
    def validate_timestep(cls, v: int) -> int:
        """Ensure timestep divides 60 evenly."""
        if 60 % v != 0:
            raise ValueError(f"Timestep {v} must divide 60 evenly")
        return v


class TimeseriesInputSpec(BaseModel):
    """Metadata for input timeseries."""

    num_rows: int = Field(..., ge=0)
    start_time: datetime
    end_time: datetime
    timestep_minutes: int
    required_columns: list[str] = Field(
        default_factory=lambda: [
            "load_kw",
            "pv_kw",
            "import_price_gbp_per_kwh",
            "export_price_gbp_per_kwh",
        ]
    )


class DispatchResult(BaseModel):
    """Result of a single optimization solve."""

    objective_value_gbp: float
    solve_time_seconds: float
    solver_status: str
    solver_termination_condition: str
    gap: Optional[float] = None


class BundleMetadata(BaseModel):
    """Metadata for reproducibility tracking."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    gridq_version: str
    solver_name: str = Field(default="highs")
    solver_version: Optional[str] = None
    git_commit_hash: Optional[str] = None
