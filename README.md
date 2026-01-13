# GridQ Optimization Engine

A single-site behind-the-meter (BTM) optimization engine for battery energy storage systems. GridQ optimizes battery dispatch to minimize energy costs, reduce peak demand, and maximize value from distributed energy resources.

## What This Is

GridQ is a **deterministic, reproducible optimization engine** for BTM battery dispatch. It:

- Solves LP-based optimization problems using HiGHS (via linopy)
- Operates as a pure library with no network calls or filesystem side effects
- Uses "run bundles" as the unit of reproducibility
- Supports multiple operation modes: backtest, underwriting (stub), live-ops (stub)
- Validates all inputs and outputs against a canonical data model

This is an MVP focused on **structure and correctness**, not feature completeness.

## Quickstart

### Install

```bash
pip install -e .
```

### Generate Example Bundles

```bash
python scripts/generate_example_bundles.py
```

### Run Backtest

```bash
gridq backtest examples/bundles/pv_battery_tou
```

### Run Tests

```bash
make test
```

### View Results

```bash
gridq report examples/bundles/pv_battery_tou
```

## Architecture Overview

### Core Principles

1. **Pure Engine Library**: The optimization engine is a pure function with deterministic outputs for identical inputs. No network calls, no filesystem side effects.

2. **Run Bundles**: Every run reads from and writes to a "run bundle" - a folder containing configuration, input timeseries, and results. Bundles are the unit of reproducibility and audit.

3. **One Engine, Multiple Runners**: Backtest, underwriting, and live-ops all use the same core engine interface. The difference is in how data flows in and out.

4. **Schema-First**: All configurations use Pydantic validation. Sign conventions and units are explicitly documented and tested.

5. **Trialable**: `make test` and `gridq backtest` work from a clean checkout. CI passes. Docker builds.

### Package Structure

```
src/gridq_engine/
├── core/              # Pure domain logic
│   ├── schemas.py     # Pydantic models
│   ├── constants.py   # Canonical column names, units
│   ├── validate.py    # Input validation
│   ├── baseline.py    # Baseline comparator
│   └── metrics.py     # Savings computation
├── model/             # Optimization model
│   ├── build.py       # Build linopy model
│   ├── constraints.py # SOC dynamics, balance, limits
│   ├── objective.py   # Cost minimization
│   └── solve.py       # Solver interface
├── io/                # Bundle I/O
│   ├── bundle.py      # Load/write bundles
│   └── formats.py     # Parquet helpers
├── forecast/          # Forecast interface (stub)
│   ├── interface.py   # ForecastProvider protocol
│   └── providers.py   # Replay, persistence
├── runners/           # Operation modes
│   ├── backtest.py    # Historical backtest
│   ├── underwrite.py  # Underwriting (stub)
│   └── live_stub.py   # Live ops (stub)
└── cli.py             # Typer CLI
```

### Run Bundle Format

A run bundle is a folder with:

```
bundle_name/
├── site_config.yaml       # Site and battery config
├── run_config.yaml        # Run parameters, tariff
├── timeseries.parquet     # Input timeseries
└── (outputs):
    ├── dispatch.parquet   # Optimized dispatch
    ├── metrics.json       # Savings vs baseline
    ├── solve_stats.json   # Solver statistics
    └── bundle_metadata.json  # Reproducibility metadata
```

**Required timeseries columns:**
- `timestamp` (DatetimeIndex)
- `load_kw`
- `pv_kw`
- `import_price_gbp_per_kwh`
- `export_price_gbp_per_kwh`

**Output columns:**
- `grid_import_kw`
- `grid_export_kw`
- `battery_charge_kw`
- `battery_discharge_kw`
- `soc_kwh`

## Sign Conventions and Units

**All power flows are positive in their named direction:**

- `load_kw`: Positive = consumption
- `pv_kw`: Positive = generation
- `grid_import_kw`: Positive = import from grid
- `grid_export_kw`: Positive = export to grid
- `battery_charge_kw`: Positive = charging (energy into battery)
- `battery_discharge_kw`: Positive = discharging (energy from battery)
- `soc_kwh`: Absolute state of charge in kWh

**Energy balance:**
```
load + battery_charge + grid_export = pv + battery_discharge + grid_import
```

**Units:**
- Power: kW
- Energy: kWh
- Prices: £/kWh (GBP per kWh)
- Demand charge: £/kW (GBP per kW of peak)
- Timestamps: UTC, monotonic, fixed timestep

**Timestep:**
- Default: 15 minutes
- Must divide 60 evenly (15, 30, etc.)

## Architectural Decisions Made

These decisions are **locked in** for the MVP:

1. **Python + linopy + HiGHS**: Python for rapid iteration, linopy for LP modeling, HiGHS for open-source solving.

2. **Engine purity**: No network calls, no filesystem side effects inside the engine. Deterministic outputs.

3. **Canonical data model**: Pydantic schemas for all configs. Sign conventions tested and documented.

4. **Run bundles**: Reproducibility and audit via self-contained bundle folders.

5. **Monorepo**: Single repo, no microservices. Runner modes are imports, not services.

6. **CI + Docker from day one**: All code must pass tests and build in Docker before merge.

7. **Forecasting is an interface**: MVP uses persistence and replay only. ML forecasting is a future provider implementation.

8. **No hardware control in MVP**: Live-ops is a stub. Actuation/safety will be added later.

## Architectural Decisions To Be Made

These decisions are **deferred** to future sprints:

1. **Solver strategy for production**: HiGHS is open-source but may not scale. Evaluate Gurobi, CPLEX, or others. Consider licensing costs, performance, and support.

2. **Full-year underwriting scaling**: How to handle 35,000+ timesteps? Chunking? Parallelization? Approximations? Need to benchmark.

3. **Multi-site / portfolio modeling**: Independent sites vs coupled constraints (e.g., VPP dispatch). What's the right level of coordination?

4. **Degradation model sophistication**: Linear cost is a placeholder. Evaluate rainflow cycle counting, calendar aging, and SOH tracking.

5. **Demand charge generalization**: UK DUoS has ratchets, seasonal bands, and triads. Need to model these accurately.

6. **Data ingestion strategy**: Home API integrations vs industrial SCADA. Privacy, GDPR, and data retention policies.

7. **Live actuation/control plane**: Device protocols (Modbus, OCPP, proprietary). Safety constraints, rate limits, failsafes, and local override.

8. **Observability**: Structured logging, tracing, metrics store. How to monitor production? Alerting on failed solves?

9. **Storage layer for bundles**: Local FS for MVP. Move to S3/GCS for production? Immutability, versioning, and access control.

10. **Security model**: Tenant isolation, secrets management, authN/Z. Not needed until API exists.

11. **Billing/settlement integration**: Waterfall logic for cost allocation. Audit trails for reconciliation with actual meter reads.

## CLI Commands

```bash
# Validate a bundle
gridq validate examples/bundles/pv_battery_tou

# Run backtest
gridq backtest examples/bundles/pv_battery_tou

# Generate report from results
gridq report examples/bundles/pv_battery_tou

# Show version
gridq version
```

## Development

### Setup

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
make test
```

### Lint

```bash
make lint
```

### Docker

```bash
make docker-build
make docker-backtest
```

## Testing

The test suite includes:

- **Golden bundle tests**: Validate example bundles produce expected results
- **Sign convention tests**: Verify all power flows are non-negative
- **Energy balance tests**: Ensure balance equation holds at every timestep
- **SOC bounds tests**: Verify battery SOC stays within limits

Run with:

```bash
pytest tests/ -v
```

## Roadmap

**Sprint 1 (MVP)** - Complete:
- Core engine with linopy + HiGHS
- Run bundle I/O
- Backtest runner with baseline comparison
- Example bundles and tests
- CLI, Docker, CI

**Sprint 2**:
- Flex price-taker (sell load curtailment)
- Expanded tariff models (DUoS, triads)
- More realistic synthetic datasets
- Basic plotting/visualization
- Performance profiling

**Sprint 3**:
- Underwriting runner (full-year)
- Forecast provider implementations (persistence, ML stub)
- Multi-day rolling horizon backtest
- Scenario analysis framework

**Later**:
- Live-ops runner
- Hardware integration
- VPP / portfolio optimization
- Advanced degradation models

## Contributing

This is an internal repo. See `CONTRIBUTING.md` for development guidelines.

## License

MIT License. See `LICENSE` file.
