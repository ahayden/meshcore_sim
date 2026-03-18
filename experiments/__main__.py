"""
python3 -m experiments [options]

Run one or more routing-variant experiments and print a comparison table.

Examples
--------
# All scenarios, all available binaries:
    python3 -m experiments

# One scenario, all binaries:
    python3 -m experiments --scenario grid/3x3

# One scenario, one binary:
    python3 -m experiments --scenario grid/3x3 --binary nexthop

# List available scenarios:
    python3 -m experiments --list
"""

from __future__ import annotations

import argparse
import os
import sys

from experiments.compare import compare
from experiments.runner import run_scenario
from experiments.scenarios import (
    ALL_BINARIES,
    ALL_SCENARIOS,
    BASELINE_BINARY,
    NEXTHOP_BINARY,
    SCENARIO_BY_NAME,
    available_binaries,
)

_BINARY_ALIASES: dict[str, str] = {
    "baseline":       BASELINE_BINARY,
    "node_agent":     BASELINE_BINARY,
    "nexthop":        NEXTHOP_BINARY,
    "nexthop_agent":  NEXTHOP_BINARY,
}


def _resolve_binary(name: str) -> str:
    """Resolve a short alias or path to an absolute binary path."""
    if name in _BINARY_ALIASES:
        return _BINARY_ALIASES[name]
    return os.path.abspath(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m experiments",
        description="Compare routing variant experiments.",
    )
    parser.add_argument(
        "--scenario", "-s",
        metavar="NAME",
        help="Run only this scenario (e.g. 'grid/3x3').  Default: all.",
    )
    parser.add_argument(
        "--binary", "-b",
        metavar="NAME_OR_PATH",
        action="append",
        dest="binaries",
        help=(
            "Binary to include.  May be a short alias (baseline, nexthop) or "
            "a file path.  May be repeated.  Default: all available binaries."
        ),
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available scenarios and binaries, then exit.",
    )
    args = parser.parse_args(argv)

    # --list
    if args.list:
        print("Available scenarios:")
        for s in ALL_SCENARIOS:
            print(f"  {s.name}")
        print("\nAvailable binaries:")
        for b in ALL_BINARIES:
            exists = "✓" if (os.path.isfile(b) and os.access(b, os.X_OK)) else "✗ (not built)"
            print(f"  {os.path.basename(b):<22}  {exists}  {b}")
        return 0

    # Resolve scenarios.
    if args.scenario:
        sc = SCENARIO_BY_NAME.get(args.scenario)
        if sc is None:
            print(f"error: unknown scenario {args.scenario!r}", file=sys.stderr)
            print(f"       available: {', '.join(SCENARIO_BY_NAME)}", file=sys.stderr)
            return 1
        scenarios = [sc]
    else:
        scenarios = ALL_SCENARIOS

    # Resolve binaries.
    if args.binaries:
        binaries = [_resolve_binary(b) for b in args.binaries]
    else:
        binaries = available_binaries()
        if not binaries:
            print("error: no binaries found.  Build node_agent and/or privatemesh/nexthop first.",
                  file=sys.stderr)
            return 1

    missing = [b for b in binaries if not (os.path.isfile(b) and os.access(b, os.X_OK))]
    if missing:
        for b in missing:
            print(f"error: binary not found or not executable: {b}", file=sys.stderr)
        return 1

    # Run.
    for scenario in scenarios:
        results = []
        for binary in binaries:
            print(f"\nRunning: {scenario.name}  binary={os.path.basename(binary)} …",
                  flush=True)
            result = run_scenario(scenario, binary)
            results.append(result)
            print(f"  done in {result.elapsed_s:.1f}s  "
                  f"delivery={result.delivery_rate*100:.0f}%  "
                  f"avg_witness={result.avg_witness_count:.1f}")

        if len(results) >= 2:
            compare(results, scenario_name=scenario.name).print()
        elif results:
            compare(results, scenario_name=scenario.name).print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
