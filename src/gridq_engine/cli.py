"""Command-line interface for GridQ engine."""

from pathlib import Path

import typer

from gridq_engine import __version__

app = typer.Typer(
    help="GridQ Behind-the-Meter Optimization Engine",
    no_args_is_help=True,
)


@app.command()
def version():
    """Show GridQ version."""
    typer.echo(f"GridQ Engine v{__version__}")


@app.command()
def validate(bundle_path: str):
    """Validate a run bundle.

    Args:
        bundle_path: Path to bundle directory
    """
    from gridq_engine.io.bundle import validate_bundle

    try:
        validate_bundle(bundle_path)
        typer.secho(f"✓ Bundle at {bundle_path} is valid", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"✗ Bundle validation failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command()
def backtest(bundle_path: str):
    """Run backtest on a bundle.

    Args:
        bundle_path: Path to bundle directory
    """
    from gridq_engine.runners.backtest import run_backtest

    try:
        run_backtest(bundle_path)
        typer.secho(f"\n✓ Backtest completed successfully", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"\n✗ Backtest failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command()
def init_bundle(
    bundle_path: str,
    template: str = typer.Option("pv_battery_tou", help="Template name"),
):
    """Initialize a new run bundle from template.

    Args:
        bundle_path: Path to new bundle directory
        template: Template name (currently only supports manual creation)
    """
    typer.secho(
        f"Bundle initialization from templates not yet implemented.\n"
        f"Please create bundle manually or copy from examples/bundles/",
        fg=typer.colors.YELLOW,
    )
    typer.secho(
        f"\nRequired files:\n"
        f"  - site_config.yaml\n"
        f"  - run_config.yaml\n"
        f"  - timeseries.parquet",
        fg=typer.colors.BLUE,
    )
    raise typer.Exit(1)


@app.command()
def report(bundle_path: str):
    """Generate report from backtest results.

    Args:
        bundle_path: Path to bundle directory
    """
    import json

    bundle_path_obj = Path(bundle_path)

    # Check if results exist
    metrics_file = bundle_path_obj / "metrics.json"
    if not metrics_file.exists():
        typer.secho(
            f"✗ No results found in bundle. Run backtest first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    # Load and display metrics
    with open(metrics_file) as f:
        metrics = json.load(f)

    typer.echo("\n" + "=" * 60)
    typer.echo("BACKTEST RESULTS")
    typer.echo("=" * 60)

    typer.echo(f"\nCost Analysis:")
    typer.echo(f"  Baseline cost:    £{metrics['baseline_cost_gbp']:.2f}")
    typer.echo(f"  Optimized cost:   £{metrics['optimal_cost_gbp']:.2f}")
    typer.echo(f"  Savings:          £{metrics['savings_gbp']:.2f} ({metrics['savings_pct']:.1f}%)")

    typer.echo(f"\nPeak Demand:")
    typer.echo(f"  Baseline peak:    {metrics['baseline_peak_import_kw']:.2f} kW")
    typer.echo(f"  Optimized peak:   {metrics['optimal_peak_import_kw']:.2f} kW")
    typer.echo(f"  Reduction:        {metrics['peak_reduction_kw']:.2f} kW")

    typer.echo(f"\nBattery Utilization:")
    typer.echo(f"  Throughput:       {metrics['battery_throughput_kwh']:.2f} kWh")
    typer.echo(f"  Cycles:           {metrics['battery_cycles']:.2f}")

    typer.echo(f"\nEnergy Flows:")
    typer.echo(f"  Total import:     {metrics['total_import_kwh']:.2f} kWh")
    typer.echo(f"  Total export:     {metrics['total_export_kwh']:.2f} kWh")

    typer.echo("\n" + "=" * 60 + "\n")

    typer.secho("✓ Report generated", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
