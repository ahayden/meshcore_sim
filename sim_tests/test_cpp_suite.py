"""
test_cpp_suite.py — Run the C++ meshcore_tests binary as part of the
Python test suite, so `python3 -m sim_tests` covers everything.

Each test method runs one named filter group, matching the CTest targets
defined in tests/CMakeLists.txt.  A failure in any group shows the
C++ stdout (which already contains per-test PASS/FAIL lines) as the
assertion message, making it easy to see which C++ test broke.

Skipped automatically when the C++ binary is absent.
"""

from __future__ import annotations

import os
import subprocess
import unittest

# ---------------------------------------------------------------------------
# Binary path
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPP_BINARY  = os.path.join(_REPO_ROOT, "tests", "build", "meshcore_tests")


def _cpp_binary_available() -> bool:
    return os.path.isfile(CPP_BINARY) and os.access(CPP_BINARY, os.X_OK)


_SKIP = unittest.skipUnless(
    _cpp_binary_available(),
    "C++ meshcore_tests binary not found at %s — run: "
    "cd tests && cmake -S . -B build && cmake --build build" % CPP_BINARY,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(filter_arg: str | None = None) -> tuple[int, str]:
    """Run the binary with an optional name filter; return (returncode, output)."""
    cmd = [CPP_BINARY]
    if filter_arg:
        cmd.append(filter_arg)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


# ---------------------------------------------------------------------------
# Test class — one method per named group
# ---------------------------------------------------------------------------

@_SKIP
class TestCppSuite(unittest.TestCase):
    """
    Runs the C++ meshcore_tests binary once per named filter group.
    This gives fine-grained failure reporting: a SHA-256 regression
    appears as TestCppSuite.test_sha256 rather than a single monolithic
    failure.
    """

    def _assert_group(self, group: str) -> None:
        rc, output = _run(group)
        self.assertEqual(
            rc, 0,
            msg=f"C++ test group '{group}' failed:\n\n{output}",
        )

    def test_sha256(self):
        self._assert_group("sha256")

    def test_hmac(self):
        self._assert_group("hmac")

    def test_aes128(self):
        self._assert_group("aes128")

    def test_ed25519(self):
        self._assert_group("ed25519")

    def test_ecdh(self):
        self._assert_group("ecdh")

    def test_encrypt(self):
        self._assert_group("encrypt")

    def test_packet(self):
        self._assert_group("packet")

    def test_tables(self):
        self._assert_group("tables")

    def test_all(self):
        """
        Runs the full suite without a filter as a final sanity check.
        If any group above passes but this fails, there is a new test
        whose group name doesn't match any filter above.
        """
        rc, output = _run(None)
        self.assertEqual(
            rc, 0,
            msg=f"C++ full suite failed:\n\n{output}",
        )


if __name__ == "__main__":
    unittest.main()
