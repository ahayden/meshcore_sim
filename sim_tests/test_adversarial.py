"""
test_adversarial.py — Unit tests for orchestrator.adversarial

No binary or network access required.
"""

from __future__ import annotations

import random
import unittest

from orchestrator.adversarial import AdversarialFilter
from orchestrator.config import AdversarialConfig


def _make(mode: str, **kwargs) -> tuple[AdversarialFilter, random.Random]:
    rng = random.Random(42)
    cfg = AdversarialConfig(mode=mode, **kwargs)
    return AdversarialFilter(cfg, rng), rng


# ---------------------------------------------------------------------------
# should_apply — probability gating
# ---------------------------------------------------------------------------

class TestShouldApply(unittest.TestCase):

    def test_probability_1_always_applies(self):
        f, _ = _make("drop", probability=1.0)
        self.assertTrue(all(f.should_apply() for _ in range(100)))

    def test_probability_0_never_applies(self):
        f, _ = _make("drop", probability=0.0)
        self.assertFalse(any(f.should_apply() for _ in range(100)))

    def test_probability_half_approximately(self):
        rng = random.Random(0)
        cfg = AdversarialConfig(mode="drop", probability=0.5)
        f = AdversarialFilter(cfg, rng)
        hits = sum(f.should_apply() for _ in range(10_000))
        self.assertGreater(hits, 4500)
        self.assertLess(hits, 5500)


# ---------------------------------------------------------------------------
# Drop mode
# ---------------------------------------------------------------------------

class TestDropMode(unittest.TestCase):

    def setUp(self):
        self.f, _ = _make("drop", probability=1.0)

    def test_returns_none(self):
        self.assertIsNone(self.f.filter_packet("deadbeef01020304", now=0.0))

    def test_returns_none_empty_payload(self):
        self.assertIsNone(self.f.filter_packet("", now=0.0))

    def test_does_not_populate_replay_buffer(self):
        self.f.filter_packet("deadbeef", now=0.0)
        self.assertEqual(self.f.drain_replays(now=9999.0), [])


# ---------------------------------------------------------------------------
# Corrupt mode
# ---------------------------------------------------------------------------

class TestCorruptMode(unittest.TestCase):

    HEX_16 = "00112233445566778899aabbccddeeff"   # 16 bytes

    def setUp(self):
        self.f, _ = _make("corrupt", probability=1.0, corrupt_byte_count=1)

    def test_returns_string_not_none(self):
        result = self.f.filter_packet(self.HEX_16, now=0.0)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)

    def test_same_length_as_input(self):
        result = self.f.filter_packet(self.HEX_16, now=0.0)
        self.assertEqual(len(result), len(self.HEX_16))

    def test_valid_hex(self):
        result = self.f.filter_packet(self.HEX_16, now=0.0)
        try:
            bytes.fromhex(result)
        except ValueError:
            self.fail("corrupt output is not valid hex")

    def test_differs_from_original(self):
        result = self.f.filter_packet(self.HEX_16, now=0.0)
        # With 16 bytes and seed=42, at least one byte will flip
        self.assertNotEqual(result, self.HEX_16)

    def test_does_not_affect_replay_buffer(self):
        self.f.filter_packet(self.HEX_16, now=0.0)
        self.assertEqual(self.f.drain_replays(now=9999.0), [])

    def test_empty_payload_passthrough(self):
        # Guard branch: empty hex → return original ""
        result = self.f.filter_packet("", now=0.0)
        self.assertEqual(result, "")

    def test_corrupt_byte_count_2_flips_more_bits(self):
        """Over many trials, count=2 should flip strictly more bytes than count=1."""
        hex_payload = "00" * 32   # 32 zero bytes

        def count_flipped_bits(original: str, modified: str) -> int:
            orig_b = bytes.fromhex(original)
            mod_b  = bytes.fromhex(modified)
            return sum(bin(a ^ b).count("1") for a, b in zip(orig_b, mod_b))

        rng1 = random.Random(0)
        rng2 = random.Random(0)
        f1 = AdversarialFilter(AdversarialConfig(mode="corrupt", corrupt_byte_count=1), rng1)
        f2 = AdversarialFilter(AdversarialConfig(mode="corrupt", corrupt_byte_count=2), rng2)

        bits1 = sum(count_flipped_bits(hex_payload, f1.filter_packet(hex_payload, 0.0)) for _ in range(200))
        bits2 = sum(count_flipped_bits(hex_payload, f2.filter_packet(hex_payload, 0.0)) for _ in range(200))

        self.assertGreater(bits2, bits1,
            "count=2 should flip more bits on average than count=1")


# ---------------------------------------------------------------------------
# Replay mode
# ---------------------------------------------------------------------------

class TestReplayMode(unittest.TestCase):

    PAYLOAD = "cafebabe12345678"

    def setUp(self):
        self.f, _ = _make("replay", probability=1.0, replay_delay_ms=1000.0)

    def test_original_suppressed(self):
        result = self.f.filter_packet(self.PAYLOAD, now=0.0)
        self.assertIsNone(result)

    def test_not_in_buffer_before_deadline(self):
        self.f.filter_packet(self.PAYLOAD, now=0.0)
        self.assertEqual(self.f.drain_replays(now=0.999), [])

    def test_drained_after_deadline(self):
        self.f.filter_packet(self.PAYLOAD, now=0.0)
        ready = self.f.drain_replays(now=1.0)
        self.assertEqual(ready, [self.PAYLOAD])

    def test_exact_deadline_boundary(self):
        self.f.filter_packet(self.PAYLOAD, now=0.0)
        self.assertEqual(self.f.drain_replays(now=0.9999), [])
        self.assertEqual(self.f.drain_replays(now=1.0000), [self.PAYLOAD])

    def test_drain_removes_from_buffer(self):
        self.f.filter_packet(self.PAYLOAD, now=0.0)
        self.f.drain_replays(now=1.0)           # drains it
        self.assertEqual(self.f.drain_replays(now=9999.0), [])  # gone

    def test_multiple_packets_partial_drain(self):
        self.f.filter_packet("aaaa", now=0.0)   # due at 1.0
        self.f.filter_packet("bbbb", now=0.5)   # due at 1.5
        # Only the first should be ready at now=1.2
        ready = self.f.drain_replays(now=1.2)
        self.assertEqual(ready, ["aaaa"])
        # The second arrives later
        ready2 = self.f.drain_replays(now=2.0)
        self.assertEqual(ready2, ["bbbb"])

    def test_replay_preserves_exact_bytes(self):
        self.f.filter_packet(self.PAYLOAD, now=0.0)
        ready = self.f.drain_replays(now=1.0)
        self.assertEqual(ready[0], self.PAYLOAD)


# ---------------------------------------------------------------------------
# Unknown / unsupported mode
# ---------------------------------------------------------------------------

class TestUnknownMode(unittest.TestCase):

    def test_unknown_mode_passes_through(self):
        cfg = AdversarialConfig(mode="intercept", probability=1.0)
        f = AdversarialFilter(cfg, random.Random(0))
        result = f.filter_packet("deadbeef", now=0.0)
        self.assertEqual(result, "deadbeef")


if __name__ == "__main__":
    unittest.main()
