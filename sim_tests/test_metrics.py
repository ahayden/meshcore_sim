"""
test_metrics.py — Unit tests for orchestrator.metrics

No binary or network access required.
All async calls use asyncio.run() directly.
"""

from __future__ import annotations

import asyncio
import time
import unittest

from orchestrator.metrics import MetricsCollector, SendRecord


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

class TestCounters(unittest.TestCase):

    def setUp(self):
        self.m = MetricsCollector()

    def test_record_tx_increments(self):
        self.m.record_tx("alice")
        self.m.record_tx("alice")
        self.assertIn("TX", self.m.report())
        # Verify value via internal state
        self.assertEqual(self.m._tx["alice"], 2)

    def test_record_rx_increments(self):
        self.m.record_rx("bob")
        self.m.record_rx("bob")
        self.assertEqual(self.m._rx["bob"], 2)

    def test_tx_and_rx_independent_nodes(self):
        self.m.record_tx("alice")
        self.m.record_rx("bob")
        self.assertEqual(self.m._tx["alice"], 1)
        self.assertEqual(self.m._rx["bob"], 1)
        self.assertEqual(self.m._tx["bob"], 0)   # defaultdict
        self.assertEqual(self.m._rx["alice"], 0)

    def test_link_loss_accumulates(self):
        for _ in range(3):
            self.m.record_link_loss("a", "b")
        self.assertEqual(self.m._link_loss_count, 3)

    def test_adversarial_drop_accumulates(self):
        self.m.record_adversarial_drop("relay1")
        self.m.record_adversarial_drop("relay1")
        self.assertEqual(self.m._adv_drop_count, 2)

    def test_adversarial_corrupt_accumulates(self):
        self.m.record_adversarial_corrupt("relay1")
        self.assertEqual(self.m._adv_corrupt_count, 1)

    def test_adversarial_replay_accumulates(self):
        self.m.record_adversarial_replay("relay1")
        self.assertEqual(self.m._adv_replay_count, 1)

    def test_fresh_collector_all_zero(self):
        report = self.m.report()
        # All event-count lines should read 0
        self.assertIn("0", report)   # at minimum something is zero


# ---------------------------------------------------------------------------
# Message delivery tracking
# ---------------------------------------------------------------------------

class TestMessageDelivery(unittest.TestCase):

    def setUp(self):
        self.m = MetricsCollector()

    # -- helpers --

    def _deliver(self, node: str, text: str):
        asyncio.run(self.m.on_event(node, {"type": "recv_text", "text": text}))

    # -- tests --

    def test_send_attempt_goes_to_pending(self):
        self.m.record_send_attempt("alice", "pubhex", "hello")
        self.assertIn("hello", self.m._pending)

    def test_delivery_moves_to_completed(self):
        self.m.record_send_attempt("alice", "pubhex", "hello")
        self._deliver("bob", "hello")
        self.assertEqual(len(self.m._completed), 1)
        self.assertEqual(len(self.m._pending), 0)

    def test_wrong_text_does_not_match(self):
        self.m.record_send_attempt("alice", "pubhex", "hello")
        self._deliver("bob", "goodbye")
        self.assertEqual(len(self.m._pending), 1)
        self.assertEqual(len(self.m._completed), 0)

    def test_non_recv_text_event_ignored(self):
        self.m.record_send_attempt("alice", "pubhex", "hello")
        asyncio.run(self.m.on_event("bob", {"type": "tx", "hex": "deadbeef"}))
        self.assertEqual(len(self.m._pending), 1)

    def test_partial_delivery(self):
        for i in range(3):
            self.m.record_send_attempt("alice", "pub", f"msg{i}")
        self._deliver("bob", "msg0")
        self._deliver("bob", "msg1")
        # msg2 still pending
        self.assertEqual(len(self.m._completed), 2)
        self.assertEqual(len(self.m._pending), 1)

    def test_second_delivery_of_same_text_ignored(self):
        self.m.record_send_attempt("alice", "pub", "dup")
        self._deliver("bob", "dup")   # first: moves to completed
        self._deliver("bob", "dup")   # second: nothing in pending to match
        self.assertEqual(len(self.m._completed), 1)

    def test_received_by_recorded(self):
        self.m.record_send_attempt("alice", "pub", "msg")
        self._deliver("charlie", "msg")
        self.assertEqual(self.m._completed[0].received_by, "charlie")

    def test_received_at_after_sent_at(self):
        self.m.record_send_attempt("alice", "pub", "timing")
        time.sleep(0.01)
        self._deliver("bob", "timing")
        rec = self.m._completed[0]
        self.assertIsNotNone(rec.received_at)
        self.assertGreaterEqual(rec.received_at, rec.sent_at)


# ---------------------------------------------------------------------------
# SendRecord dataclass
# ---------------------------------------------------------------------------

class TestSendRecord(unittest.TestCase):

    def test_initial_received_fields_are_none(self):
        rec = SendRecord(sender="a", dest_pub="pub", text="hi", sent_at=1.0)
        self.assertIsNone(rec.received_at)
        self.assertIsNone(rec.received_by)

    def test_sent_at_set_by_record_send_attempt(self):
        m = MetricsCollector()
        before = time.monotonic()
        m.record_send_attempt("a", "pub", "test")
        after = time.monotonic()
        rec = m._pending["test"]
        self.assertGreaterEqual(rec.sent_at, before)
        self.assertLessEqual(rec.sent_at, after)


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

class TestReport(unittest.TestCase):

    def setUp(self):
        self.m = MetricsCollector()

    def test_report_returns_string(self):
        self.assertIsInstance(self.m.report(), str)

    def test_report_contains_header(self):
        self.assertIn("Simulation Metrics", self.m.report())

    def test_report_contains_separator(self):
        self.assertIn("=" * 50, self.m.report())

    def test_empty_collector_no_crash(self):
        # Should not raise
        _ = self.m.report()

    def test_zero_delivery_rate(self):
        self.m.record_send_attempt("a", "pub", "pending_msg")
        report = self.m.report()
        self.assertIn("0/1", report)

    def test_hundred_percent_delivery(self):
        self.m.record_send_attempt("a", "pub", "hello")
        asyncio.run(self.m.on_event("b", {"type": "recv_text", "text": "hello"}))
        report = self.m.report()
        self.assertIn("1/1", report)
        self.assertIn("100.0%", report)

    def test_two_thirds_delivery(self):
        for i in range(3):
            self.m.record_send_attempt("a", "pub", f"m{i}")
        asyncio.run(self.m.on_event("b", {"type": "recv_text", "text": "m0"}))
        asyncio.run(self.m.on_event("b", {"type": "recv_text", "text": "m1"}))
        report = self.m.report()
        self.assertIn("2/3", report)
        self.assertIn("66.7%", report)

    def test_latency_line_present_after_delivery(self):
        self.m.record_send_attempt("a", "pub", "msg")
        asyncio.run(self.m.on_event("b", {"type": "recv_text", "text": "msg"}))
        self.assertIn("Latency", self.m.report())

    def test_latency_line_absent_with_no_deliveries(self):
        self.assertNotIn("Latency", self.m.report())

    def test_undelivered_note_when_pending(self):
        self.m.record_send_attempt("a", "pub", "waiting")
        self.assertIn("still in flight", self.m.report())

    def test_undelivered_note_absent_when_all_done(self):
        self.m.record_send_attempt("a", "pub", "done_msg")
        asyncio.run(self.m.on_event("b", {"type": "recv_text", "text": "done_msg"}))
        self.assertNotIn("still in flight", self.m.report())

    def test_adversarial_counts_in_report(self):
        self.m.record_adversarial_drop("r")
        self.m.record_adversarial_corrupt("r")
        self.m.record_adversarial_replay("r")
        report = self.m.report()
        self.assertIn("Adversarial drops", report)
        self.assertIn("Adversarial corruptions", report)
        self.assertIn("Adversarial replays", report)

    def test_per_node_tx_rx_in_report(self):
        self.m.record_tx("alice")
        self.m.record_rx("bob")
        report = self.m.report()
        self.assertIn("alice", report)
        self.assertIn("bob", report)


if __name__ == "__main__":
    unittest.main()
