"""
experiments — framework for comparing routing variants across scenarios.

Quick start:

    from experiments.scenarios import GRID_3X3, BASELINE_BINARY, NEXTHOP_BINARY
    from experiments.runner import run_scenario
    from experiments.compare import compare

    baseline = run_scenario(GRID_3X3, BASELINE_BINARY, label="baseline")
    nexthop  = run_scenario(GRID_3X3, NEXTHOP_BINARY,  label="nexthop")
    compare([baseline, nexthop]).print()

Or from the CLI:

    python3 -m experiments                            # all scenarios, all binaries
    python3 -m experiments --scenario grid/3x3        # one scenario, all binaries
    python3 -m experiments --list                     # list available scenarios
"""

from experiments.runner import Scenario, SimResult, run_scenario
from experiments.compare import ComparisonTable, compare

__all__ = [
    "Scenario",
    "SimResult",
    "run_scenario",
    "ComparisonTable",
    "compare",
]
