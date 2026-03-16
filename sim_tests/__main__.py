"""
__main__.py — Entry point for the sim_tests suite.

Usage:
    python -m sim_tests                    # run all tests
    python -m sim_tests test_config        # run one module by name
    python -m sim_tests TestAdversarial    # run one class by name

Integration tests are automatically skipped when the node_agent binary
is not present at node_agent/build/node_agent.

Exit code: 0 = all non-skipped tests pass, 1 = any failure.
"""

from __future__ import annotations

import sys
import unittest


def _make_suite(filter_name: str | None = None) -> unittest.TestSuite:
    import os
    start_dir = os.path.dirname(os.path.abspath(__file__))
    loader = unittest.TestLoader()

    if filter_name is None:
        return loader.discover(start_dir=start_dir, pattern="test_*.py")

    # Try to load just the named module or class
    # Prefix with package name if needed
    target = filter_name
    if not target.startswith("sim_tests."):
        target = f"sim_tests.{target}"

    try:
        # Could be a module (e.g. "sim_tests.test_config")
        return loader.loadTestsFromName(target)
    except (ModuleNotFoundError, AttributeError):
        # Fall back to discovering all and letting verbosity show the skip
        return loader.discover(start_dir=start_dir, pattern="test_*.py")


def main() -> None:
    filter_name = sys.argv[1] if len(sys.argv) > 1 else None

    suite = _make_suite(filter_name)
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stderr)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
