# Multi-Objective Battery Optimization

## File

**`multi_objective_bess.py`** - Single standalone Python file (~250 lines of logic)

## The Problem

Commercial electricity tariffs typically have two cost components:

1. **Energy charges (£/kWh)**: Time-varying prices for electricity consumed
2. **Demand charges (£/kW)**: Monthly fee based on peak power drawn from grid

These create **conflicting objectives** for battery dispatch:

| Objective | Strategy | Consequence |
|-----------|----------|-------------|
| Minimize energy cost | Charge aggressively when prices are low | Higher peak grid import |
| Minimize peak demand | Spread grid imports evenly | Miss cheapest charging windows |

A single-objective optimizer must choose one. A **multi-objective optimizer** finds the full trade-off curve (Pareto front) and lets the operator select their preferred balance.

## Technique Used: Epsilon-Constraint Method

### Why This Method?

| Method | Description | Limitation |
|--------|-------------|------------|
| **Weighted Sum** | Combine objectives: `w₁·f₁ + w₂·f₂` | Cannot find non-convex Pareto regions |
| **NSGA-II** | Evolutionary multi-objective algorithm | Overkill for LP; computationally heavy |
| **Epsilon-Constraint** | Optimize f₁ while constraining f₂ ≤ ε | Requires objective bounds (easy for our problem) |

The epsilon-constraint method is ideal because:
- Our problem is a **Linear Program (LP)** - fast to solve
- Peak demand has natural bounds (0 to max load)
- Guarantees finding all Pareto-optimal points, including non-convex regions

### How It Works

**Standard formulation:**
```
minimize    f₁(x)           # Primary objective
subject to  f₂(x) ≤ ε       # Secondary objective as constraint
            g(x) ≤ 0        # Original constraints
```

**Our implementation:**
```
For ε in [min_feasible_peak, ..., max_peak]:

    minimize    Σ (import_price[t] × grid_import[t] × dt)     # Energy cost
                - Σ (export_price[t] × grid_export[t] × dt)   # Export revenue

    subject to  grid_import[t] ≤ ε                    ∀t      # Peak constraint (epsilon)
                load[t] + charge[t] + export[t] =
                    pv[t] + discharge[t] + import[t]  ∀t      # Energy balance
                soc[t] = soc[t-1] + charge×η×dt - discharge×dt/η  # SOC dynamics
                min_soc ≤ soc[t] ≤ max_soc            ∀t      # SOC bounds
                0 ≤ charge[t] ≤ max_charge            ∀t      # Power limits
                0 ≤ discharge[t] ≤ max_discharge      ∀t

    Record (energy_cost, ε) as Pareto point
```

By sweeping ε from minimum feasible to maximum, we trace the entire Pareto front.

### Finding the Bounds

1. **Upper bound**: Maximum net load (load - PV) when no battery is used
2. **Lower bound**: Binary search to find minimum peak where LP remains feasible

```python
# Binary search for minimum feasible peak
peak_min, peak_max = 0.0, max(net_load)
for _ in range(20):
    mid = (peak_min + peak_max) / 2
    if solve_with_peak_limit(mid) is feasible:
        peak_max = mid
    else:
        peak_min = mid
```

## References

### Primary Technique Reference

**Epsilon-Constraint Method:**
- Mavrotas, G. (2009). "Effective implementation of the ε-constraint method in Multi-Objective Mathematical Programming problems." *Applied Mathematics and Computation*, 213(2), 455-465.
- Tutorial: [SCDA - Augmented Epsilon-Constraint Method](https://www.supplychaindataanalytics.com/augmented-epsilon-constraint-method-multi-goal-optimization-with-pulp-in-python/)
- Implementation guide: [OpenMDAO Multi-objective Optimization](https://openmdao.github.io/PracticalMDO/Notebooks/Optimization/multiobjective.html)

### Battery Optimization Context

**Multi-objective BESS papers:**
- Parra, D., et al. (2019). "Multi-objective optimization of energy arbitrage in community energy storage systems using different battery technologies." *Applied Energy*, 239, 356-372. [Link](https://www.sciencedirect.com/science/article/pii/S0306261919302478)
- Demonstrates EA (Energy Arbitrage) vs EA-PS (Energy Arbitrage + Peak Shaving) scenarios

**Demand charge management:**
- NREL (2019). "Overview of Distributed Energy Storage for Demand Charge Reduction." [Link](https://www.osti.gov/servlets/purl/1496630)
- Notes demand charges typically 30-70% of commercial electricity bills

### Solver

Uses `scipy.optimize.linprog` with HiGHS backend (no external solver installation required).

## Algorithm Pseudocode

```
function compute_pareto_front(config, load, pv, prices):

    # Step 1: Find peak demand bounds
    peak_upper = max(load - pv)
    peak_lower = binary_search_min_feasible_peak()

    # Step 2: Generate epsilon values
    epsilons = linspace(peak_lower, peak_upper, n_points)

    # Step 3: Solve LP for each epsilon
    pareto_front = []
    for ε in epsilons:
        result = solve_lp(
            objective = minimize(energy_cost),
            constraints = [
                grid_import[t] <= ε for all t,  # Epsilon constraint
                energy_balance,
                soc_dynamics,
                power_limits
            ]
        )
        if result.success:
            pareto_front.append((result.energy_cost, ε))

    return pareto_front
```

## Output Interpretation

Example Pareto front with £0.50/kW demand charge:

```
Peak (kW)    Energy (£)   Total (£)
─────────────────────────────────────
1.75         4.64         5.52      ← Minimum peak (highest energy cost)
1.99         4.44         5.43      ← OPTIMAL (minimum total cost)
2.23         4.39         5.50
2.70         4.39         5.74      ← Minimum energy cost (highest peak)
```

**Key insight**: The optimal operating point (1.99 kW) is neither extreme - demonstrating why multi-objective optimization matters.

## Usage

```python
from multi_objective_bess import (
    Config,
    compute_pareto_front,
    select_operating_point,
    generate_data
)

# Configure site
cfg = Config(
    capacity_kwh=10.0,
    max_charge_kw=5.0,
    max_discharge_kw=5.0,
    efficiency=0.95,
    demand_charge_per_kw=15.0,  # £/kW/month
)

# Load data (or use synthetic)
load, pv, import_price, export_price = generate_data(hours=24)

# Compute Pareto front
front = compute_pareto_front(cfg, load, pv, import_price, export_price)

# Select operating point
#   preference=0.0 → minimize energy cost
#   preference=0.5 → minimize total cost (balanced)
#   preference=1.0 → minimize peak demand
selected = select_operating_point(front, preference=0.5)

print(f"Optimal: Peak={selected.peak_demand_kw:.2f}kW, Cost=£{selected.total_cost:.2f}")
```

## Dependencies

```
numpy
scipy
matplotlib (optional, for plots)
```

No external LP solver required - uses scipy's built-in HiGHS.

## Key Design Decisions

1. **LP not MILP**: No binary variables for charge/discharge exclusivity - allows simultaneous charge and discharge if profitable (rare in practice due to efficiency losses)

2. **Epsilon on peak, not energy**: Peak demand is naturally bounded and interpretable; energy cost range depends on prices

3. **Binary search for lower bound**: More robust than analytical calculation when battery constraints interact

4. **Deduplication**: Adjacent Pareto points with identical energy costs are filtered (constraint not binding)

## LP Degeneracy and Regularization

### The Problem: Bang-Bang Oscillation

LP-based battery optimization commonly produces **oscillating dispatch schedules** where charging switches on and off arbitrarily even when load and PV are smooth. This occurs because:

1. **LP Degeneracy**: Multiple solutions achieve the same optimal objective value
2. **Bang-Bang Control**: LP naturally produces extreme solutions (max charge OR zero) rather than intermediate values
3. **Temporal Indifference**: With perfect foresight, the optimizer doesn't care *when* it charges, only that it reaches target SOC by the needed time

This is a well-documented phenomenon in optimal control theory and energy optimization literature.

### The Solution: Ramp Rate Constraints + Time-Weighted Regularization

We use two complementary techniques:

**1. Ramp Rate Constraints (Primary)**

Limit how fast battery power can change between timesteps:

```
|net_power[t] - net_power[t-1]| ≤ ramp_limit
```

where `net_power = charge - discharge`. We use `ramp_limit = 1.0 kW` per timestep (4 kW/hour for 15-minute resolution).

This forces smooth transitions and eliminates arbitrary oscillation by making the LP unable to switch rapidly between charging and exporting.

**2. Time-Weighted Regularization (Secondary)**

Small penalty that prefers earlier charging and later discharging when solutions are otherwise equivalent:

```
Objective += ε × Σ (1 + t/T) × charge[t]    # Later charging costs more
Objective += ε × Σ (2 - t/T) × discharge[t] # Earlier discharging costs more
```

where `ε = 10⁻⁶` is negligible compared to real price differences.

**Reference**: [arXiv:2507.04343](https://arxiv.org/abs/2507.04343) - "Optimal Sizing and Control of a Grid-Connected Battery in a Stacked Revenue Model" (2025)

The paper identifies L1/L2 regularization approaches. We extend this with ramp constraints for guaranteed smooth profiles.

### Related Literature

- Silva & Trélat (2010). "Smooth regularization of bang-bang optimal control problems." [IEEE TAC](https://ieeexplore.ieee.org/document/5445043)
- [MIT OCW Tutorial 7](https://ocw.mit.edu/courses/15-053-optimization-methods-in-management-science-spring-2013/): Degeneracy in Linear Programming
- Vanderbei, R.J. "Linear Programming: Foundations and Extensions" - Chapter on degeneracy

## Limitations

- Perfect foresight assumed (no forecast uncertainty)
- Single billing period (no monthly/annual ratchet modeling)
- No battery degradation in objective (can be added)
- No grid export limits modeled

## Extending

To add battery degradation cost:
```python
# In objective
c[i_chg(t)] += degradation_cost * dt
c[i_dis(t)] += degradation_cost * dt
```

To model monthly ratchet (annual peak):
```python
# Track historical peak, add constraint
grid_import[t] <= max(current_epsilon, historical_annual_peak)
```
