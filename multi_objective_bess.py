#!/usr/bin/env python3
"""
Multi-Objective BESS Optimizer: Energy Cost vs Peak Demand

Bi-objective optimization for battery dispatch that simultaneously considers:
  1. Energy cost (arbitrage): Minimize time-varying import/export costs
  2. Power cost (peak demand): Minimize maximum grid import for demand charges

Uses the epsilon-constraint method to generate the Pareto front:
  - Fix peak demand to target values (epsilon)
  - Minimize energy cost subject to grid_import <= epsilon
  - Sweep epsilon to trace the efficient frontier

References:
  - Epsilon-constraint: https://www.supplychaindataanalytics.com/augmented-epsilon-constraint-method-multi-goal-optimization-with-pulp-in-python/
  - Multi-objective battery optimization: https://www.sciencedirect.com/science/article/pii/S0306261919302478
  - pymoo library: https://pymoo.org/
"""

import numpy as np
from dataclasses import dataclass
from scipy.optimize import linprog
from typing import Optional


@dataclass
class Config:
    """Site and battery configuration."""
    # Battery
    capacity_kwh: float = 10.0
    max_charge_kw: float = 5.0
    max_discharge_kw: float = 5.0
    efficiency: float = 0.95
    min_soc_frac: float = 0.1
    max_soc_frac: float = 0.9
    initial_soc_frac: float = 0.5
    # Costs
    demand_charge_per_kw: float = 15.0  # £/kW/month
    # Time
    timestep_hours: float = 0.25  # 15 min


@dataclass
class ParetoPoint:
    """Single point on the Pareto front."""
    energy_cost: float      # £ (arbitrage component)
    peak_demand_kw: float   # kW (for demand charge)
    total_cost: float       # £ (energy + demand charge)
    dispatch: Optional[np.ndarray] = None  # [grid_import, grid_export, charge, discharge, soc]


def generate_data(hours: int = 24, seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic load, PV, and price profiles."""
    np.random.seed(seed)
    T = int(hours / 0.25)
    h = np.array([(i * 0.25) % 24 for i in range(T)])

    # Load: base + daily pattern + evening peak
    load = 2.0 + 2.0 * np.maximum(np.sin((h - 6) * np.pi / 12), 0) + 1.5 * np.exp(-((h - 18)**2) / 4)
    load = np.maximum(load + np.random.normal(0, 0.2, T), 0.5)

    # PV: bell curve 7am-5pm
    pv = np.where((h >= 7) & (h <= 17), 8.0 * np.sin((h - 7) * np.pi / 10)**2, 0)
    pv = np.maximum(pv + np.random.normal(0, 0.1, T), 0)

    # Prices: ToU (peak 4-9pm £0.30, day £0.15, night £0.10)
    import_price = np.where((h >= 16) & (h < 21), 0.30, np.where((h >= 7) & (h < 16), 0.15, 0.10))
    export_price = np.full(T, 0.05)

    return load, pv, import_price, export_price


def solve_with_peak_limit(
    cfg: Config,
    load: np.ndarray,
    pv: np.ndarray,
    import_price: np.ndarray,
    export_price: np.ndarray,
    peak_limit: float,
) -> Optional[ParetoPoint]:
    """Solve LP minimizing energy cost with peak demand constraint.

    Variables: [grid_import, grid_export, charge, discharge, soc] each of length T
    """
    T = len(load)
    dt = cfg.timestep_hours
    n = 5 * T  # total variables

    # Index helpers
    def i_imp(t): return t
    def i_exp(t): return T + t
    def i_chg(t): return 2*T + t
    def i_dis(t): return 3*T + t
    def i_soc(t): return 4*T + t

    # Objective: minimize energy cost only (peak is constrained)
    c = np.zeros(n)
    for t in range(T):
        c[i_imp(t)] = import_price[t] * dt
        c[i_exp(t)] = -export_price[t] * dt

    # Equality constraints: energy balance + SOC dynamics
    A_eq = np.zeros((2*T, n))
    b_eq = np.zeros(2*T)

    min_soc = cfg.min_soc_frac * cfg.capacity_kwh
    max_soc = cfg.max_soc_frac * cfg.capacity_kwh
    init_soc = cfg.initial_soc_frac * cfg.capacity_kwh

    for t in range(T):
        # Energy balance: -import + export + charge - discharge = pv - load
        A_eq[t, i_imp(t)] = -1
        A_eq[t, i_exp(t)] = 1
        A_eq[t, i_chg(t)] = 1
        A_eq[t, i_dis(t)] = -1
        b_eq[t] = pv[t] - load[t]

        # SOC dynamics: soc[t] - charge*eff*dt + discharge*dt/eff - soc[t-1] = 0
        A_eq[T+t, i_soc(t)] = 1
        A_eq[T+t, i_chg(t)] = -cfg.efficiency * dt
        A_eq[T+t, i_dis(t)] = dt / cfg.efficiency
        if t == 0:
            b_eq[T+t] = init_soc
        else:
            A_eq[T+t, i_soc(t-1)] = -1

    # Inequality constraints: SOC bounds
    A_ub = np.zeros((2*T, n))
    b_ub = np.zeros(2*T)
    for t in range(T):
        A_ub[t, i_soc(t)] = 1          # soc <= max
        b_ub[t] = max_soc
        A_ub[T+t, i_soc(t)] = -1       # -soc <= -min
        b_ub[T+t] = -min_soc

    # Variable bounds (peak limit applied to grid_import)
    bounds = (
        [(0, peak_limit) for _ in range(T)] +           # grid_import <= peak_limit
        [(0, None) for _ in range(T)] +                  # grid_export
        [(0, cfg.max_charge_kw) for _ in range(T)] +     # charge
        [(0, cfg.max_discharge_kw) for _ in range(T)] +  # discharge
        [(0, cfg.capacity_kwh) for _ in range(T)]        # soc
    )

    result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')

    if not result.success:
        return None

    x = result.x
    actual_peak = np.max(x[:T])
    dispatch = x.reshape(5, T)

    return ParetoPoint(
        energy_cost=result.fun,
        peak_demand_kw=actual_peak,
        total_cost=result.fun + actual_peak * cfg.demand_charge_per_kw,
        dispatch=dispatch,
    )


def compute_pareto_front(
    cfg: Config,
    load: np.ndarray,
    pv: np.ndarray,
    import_price: np.ndarray,
    export_price: np.ndarray,
    n_points: int = 20,
) -> list[ParetoPoint]:
    """Generate Pareto front using epsilon-constraint method.

    Sweeps peak demand limit from minimum feasible to maximum net load.
    """
    # Find bounds: max needed (no battery) and min feasible
    net_load = load - pv
    peak_max = max(np.max(net_load), 0.1)  # Upper bound: no battery case

    # Binary search for minimum feasible peak
    peak_min = 0.0
    for _ in range(20):
        mid = (peak_min + peak_max) / 2
        if solve_with_peak_limit(cfg, load, pv, import_price, export_price, mid):
            peak_max = mid
        else:
            peak_min = mid
    peak_min = peak_max  # Minimum feasible

    # Also find unconstrained optimum (energy-only)
    unconstrained = solve_with_peak_limit(cfg, load, pv, import_price, export_price, 1000)
    if unconstrained:
        peak_max = max(unconstrained.peak_demand_kw * 1.1, peak_min * 1.5)

    # Sweep epsilon values
    front = []
    epsilons = np.linspace(peak_min, peak_max, n_points)

    for eps in epsilons:
        point = solve_with_peak_limit(cfg, load, pv, import_price, export_price, eps)
        if point and (not front or abs(point.energy_cost - front[-1].energy_cost) > 1e-6):
            front.append(point)

    return front


def select_operating_point(front: list[ParetoPoint], preference: float = 0.5) -> ParetoPoint:
    """Select point from Pareto front based on preference.

    preference: 0 = minimize energy cost (accept high peak)
                1 = minimize peak demand (accept high energy cost)
                0.5 = balanced (minimize total cost)
    """
    if preference == 0.5:
        return min(front, key=lambda p: p.total_cost)

    # Normalize objectives to [0,1]
    e_min = min(p.energy_cost for p in front)
    e_max = max(p.energy_cost for p in front)
    p_min = min(p.peak_demand_kw for p in front)
    p_max = max(p.peak_demand_kw for p in front)

    def score(pt):
        e_norm = (pt.energy_cost - e_min) / (e_max - e_min + 1e-9)
        p_norm = (pt.peak_demand_kw - p_min) / (p_max - p_min + 1e-9)
        return (1 - preference) * e_norm + preference * p_norm

    return min(front, key=score)


def print_front(front: list[ParetoPoint], cfg: Config):
    """Display Pareto front results."""
    print("\n" + "="*70)
    print("PARETO FRONT: Energy Cost vs Peak Demand")
    print("="*70)
    print(f"{'Peak (kW)':<12} {'Energy (£)':<12} {'Demand (£)':<12} {'Total (£)':<12}")
    print("-"*70)
    for p in front:
        demand_cost = p.peak_demand_kw * cfg.demand_charge_per_kw
        print(f"{p.peak_demand_kw:<12.2f} {p.energy_cost:<12.2f} {demand_cost:<12.2f} {p.total_cost:<12.2f}")
    print("="*70)


def plot_pareto(front: list[ParetoPoint], selected: ParetoPoint, cfg: Config):
    """Plot Pareto front with selected operating point."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("Install matplotlib for visualization")
        return

    energy = [p.energy_cost for p in front]
    peak = [p.peak_demand_kw for p in front]
    total = [p.total_cost for p in front]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Pareto front
    ax1 = axes[0]
    ax1.plot(peak, energy, 'b-o', markersize=6, label='Pareto Front')
    ax1.plot(selected.peak_demand_kw, selected.energy_cost, 'r*', markersize=15, label='Selected')
    ax1.set_xlabel('Peak Demand (kW)')
    ax1.set_ylabel('Energy Cost (£)')
    ax1.set_title('Pareto Front: Energy vs Peak')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Total cost curve
    ax2 = axes[1]
    ax2.plot(peak, total, 'g-o', markersize=6)
    ax2.axvline(selected.peak_demand_kw, color='r', linestyle='--', label=f'Selected: {selected.total_cost:.2f}')
    ax2.set_xlabel('Peak Demand (kW)')
    ax2.set_ylabel('Total Cost (£)')
    ax2.set_title(f'Total Cost (demand charge: £{cfg.demand_charge_per_kw}/kW)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('pareto_front.png', dpi=150)
    print("\nPlot saved: pareto_front.png")
    plt.close()


def plot_dispatch(selected: ParetoPoint, load: np.ndarray, pv: np.ndarray, import_price: np.ndarray):
    """Plot the dispatch schedule for selected operating point."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return

    if selected.dispatch is None:
        return

    T = len(load)
    hours = np.arange(T) * 0.25
    grid_imp, grid_exp, charge, discharge, soc = selected.dispatch

    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)

    # Power flows
    ax1 = axes[0]
    ax1.fill_between(hours, 0, load, alpha=0.3, label='Load', color='red')
    ax1.fill_between(hours, 0, pv, alpha=0.3, label='PV', color='orange')
    ax1.plot(hours, grid_imp, 'b-', label='Grid Import', linewidth=1.5)
    ax1.axhline(selected.peak_demand_kw, color='b', linestyle='--', alpha=0.5, label=f'Peak: {selected.peak_demand_kw:.1f}kW')
    ax1.set_ylabel('Power (kW)')
    ax1.set_title('Power Flows')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Battery
    ax2 = axes[1]
    ax2.fill_between(hours, 0, charge, alpha=0.5, label='Charge', color='green')
    ax2.fill_between(hours, 0, -discharge, alpha=0.5, label='Discharge', color='purple')
    ax2.set_ylabel('Battery (kW)')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    # SOC and price
    ax3 = axes[2]
    ax3.plot(hours, soc, 'purple', label='SOC', linewidth=1.5)
    ax3.set_ylabel('SOC (kWh)', color='purple')
    ax3b = ax3.twinx()
    ax3b.plot(hours, import_price, 'k-', alpha=0.4, label='Price')
    ax3b.set_ylabel('Price (£/kWh)')
    ax3.set_xlabel('Hour')
    ax3.set_title('State of Charge & Price')
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('dispatch_schedule.png', dpi=150)
    print("Plot saved: dispatch_schedule.png")
    plt.close()


def main():
    """Run multi-objective optimization example."""
    print("Multi-Objective BESS Optimizer")
    print("="*50)

    # Configuration
    cfg = Config(
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        efficiency=0.95,
        demand_charge_per_kw=15.0,  # £/kW/month
    )

    print(f"\nBattery: {cfg.capacity_kwh}kWh, {cfg.max_charge_kw}kW")
    print(f"Demand charge: £{cfg.demand_charge_per_kw}/kW/month")

    # Generate data
    load, pv, import_price, export_price = generate_data(hours=24)
    print(f"Horizon: 24h ({len(load)} timesteps)")
    print(f"Peak net load: {np.max(load - pv):.1f}kW")

    # Compute Pareto front
    print("\nComputing Pareto front...")
    front = compute_pareto_front(cfg, load, pv, import_price, export_price, n_points=15)
    print(f"Found {len(front)} Pareto-optimal points")

    # Display front
    print_front(front, cfg)

    # Select operating points for different preferences
    print("\n--- Operating Point Selection ---")
    for pref, name in [(0.0, "Min Energy"), (0.5, "Min Total"), (1.0, "Min Peak")]:
        sel = select_operating_point(front, pref)
        print(f"{name:12}: Peak={sel.peak_demand_kw:.2f}kW, Energy=£{sel.energy_cost:.2f}, Total=£{sel.total_cost:.2f}")

    # Default selection: minimize total cost
    selected = select_operating_point(front, 0.5)

    # Key insight
    e_only = select_operating_point(front, 0.0)
    p_only = select_operating_point(front, 1.0)
    print(f"\n--- Trade-off Analysis ---")
    print(f"Energy-only optimum:  Peak={e_only.peak_demand_kw:.2f}kW, Cost=£{e_only.total_cost:.2f}")
    print(f"Peak-only optimum:    Peak={p_only.peak_demand_kw:.2f}kW, Cost=£{p_only.total_cost:.2f}")
    print(f"Balanced optimum:     Peak={selected.peak_demand_kw:.2f}kW, Cost=£{selected.total_cost:.2f}")

    if e_only.peak_demand_kw > p_only.peak_demand_kw:
        reduction = e_only.peak_demand_kw - p_only.peak_demand_kw
        energy_penalty = p_only.energy_cost - e_only.energy_cost
        print(f"\nPeak reduction potential: {reduction:.2f}kW at +£{energy_penalty:.2f} energy cost")

    # Plot
    plot_pareto(front, selected, cfg)
    plot_dispatch(selected, load, pv, import_price)

    return front, selected


if __name__ == "__main__":
    front, selected = main()
