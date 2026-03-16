"""
test_config.py — Unit tests for orchestrator.config

No binary or network access required.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest

from orchestrator.config import (
    AdversarialConfig,
    EdgeConfig,
    NodeConfig,
    SimulationConfig,
    TopologyConfig,
    load_topology,
)
from sim_tests.helpers import TOPO_DIR


# ---------------------------------------------------------------------------
# Dataclass defaults
# ---------------------------------------------------------------------------

class TestDataclassDefaults(unittest.TestCase):

    def test_adversarial_config_defaults(self):
        cfg = AdversarialConfig(mode="drop")
        self.assertEqual(cfg.probability, 1.0)
        self.assertEqual(cfg.replay_delay_ms, 5000.0)
        self.assertEqual(cfg.corrupt_byte_count, 1)

    def test_node_config_defaults(self):
        n = NodeConfig(name="x")
        self.assertFalse(n.relay)
        self.assertIsNone(n.prv_key)
        self.assertIsNone(n.adversarial)

    def test_edge_config_defaults(self):
        e = EdgeConfig(a="x", b="y")
        self.assertEqual(e.loss, 0.0)
        self.assertEqual(e.latency_ms, 0.0)
        self.assertEqual(e.snr, 6.0)
        self.assertEqual(e.rssi, -90.0)

    def test_simulation_config_defaults(self):
        s = SimulationConfig()
        self.assertEqual(s.warmup_secs, 5.0)
        self.assertEqual(s.duration_secs, 60.0)
        self.assertEqual(s.traffic_interval_secs, 10.0)
        self.assertEqual(s.advert_interval_secs, 30.0)
        self.assertEqual(s.epoch, 0)
        self.assertEqual(s.agent_binary, "./node_agent/build/node_agent")
        self.assertIsNone(s.seed)


# ---------------------------------------------------------------------------
# Loading linear_three.json
# ---------------------------------------------------------------------------

class TestLoadTopologyLinearThree(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.topo = load_topology(os.path.join(TOPO_DIR, "linear_three.json"))

    def test_node_count(self):
        self.assertEqual(len(self.topo.nodes), 3)

    def test_node_names(self):
        names = {n.name for n in self.topo.nodes}
        self.assertEqual(names, {"alice", "relay1", "bob"})

    def test_relay_flags(self):
        by_name = {n.name: n for n in self.topo.nodes}
        self.assertTrue(by_name["relay1"].relay)
        self.assertFalse(by_name["alice"].relay)
        self.assertFalse(by_name["bob"].relay)

    def test_edge_count(self):
        self.assertEqual(len(self.topo.edges), 2)

    def test_edge_endpoints(self):
        e0 = self.topo.edges[0]
        self.assertEqual(e0.a, "alice")
        self.assertEqual(e0.b, "relay1")

    def test_edge_loss(self):
        for e in self.topo.edges:
            self.assertAlmostEqual(e.loss, 0.05)

    def test_edge_latency(self):
        for e in self.topo.edges:
            self.assertAlmostEqual(e.latency_ms, 20.0)

    def test_edge_snr(self):
        for e in self.topo.edges:
            self.assertAlmostEqual(e.snr, 8.0)

    def test_edge_rssi(self):
        for e in self.topo.edges:
            self.assertAlmostEqual(e.rssi, -85.0)

    def test_simulation_warmup(self):
        self.assertAlmostEqual(self.topo.simulation.warmup_secs, 5.0)

    def test_simulation_duration(self):
        self.assertAlmostEqual(self.topo.simulation.duration_secs, 60.0)

    def test_simulation_traffic_interval(self):
        self.assertAlmostEqual(self.topo.simulation.traffic_interval_secs, 10.0)

    def test_simulation_advert_interval(self):
        self.assertAlmostEqual(self.topo.simulation.advert_interval_secs, 20.0)

    def test_epoch_auto_set_from_wallclock(self):
        # epoch=0 in JSON → load_topology replaces it with time.time()
        self.assertGreater(self.topo.simulation.epoch, 0)

    def test_no_prv_key(self):
        for n in self.topo.nodes:
            self.assertIsNone(n.prv_key)

    def test_no_adversarial_nodes(self):
        for n in self.topo.nodes:
            self.assertIsNone(n.adversarial)


# ---------------------------------------------------------------------------
# Loading adversarial.json
# ---------------------------------------------------------------------------

class TestLoadTopologyAdversarial(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.topo = load_topology(os.path.join(TOPO_DIR, "adversarial.json"))
        cls.by_name = {n.name: n for n in cls.topo.nodes}

    def test_adversarial_node_has_config(self):
        self.assertIsNotNone(self.by_name["evil_relay"].adversarial)

    def test_adversarial_mode(self):
        self.assertEqual(self.by_name["evil_relay"].adversarial.mode, "corrupt")

    def test_adversarial_probability(self):
        self.assertAlmostEqual(self.by_name["evil_relay"].adversarial.probability, 0.5)

    def test_adversarial_corrupt_byte_count(self):
        self.assertEqual(self.by_name["evil_relay"].adversarial.corrupt_byte_count, 2)

    def test_non_adversarial_nodes_clean(self):
        self.assertIsNone(self.by_name["sender"].adversarial)
        self.assertIsNone(self.by_name["receiver"].adversarial)


# ---------------------------------------------------------------------------
# Loading from inline JSON (edge cases)
# ---------------------------------------------------------------------------

class TestLoadTopologyFromInlineJSON(unittest.TestCase):
    """Write temporary JSON files and verify edge-case parsing."""

    def _load(self, data: dict) -> TopologyConfig:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name
        try:
            return load_topology(path)
        finally:
            os.unlink(path)

    def test_missing_nodes_key_gives_empty(self):
        topo = self._load({})
        self.assertEqual(topo.nodes, [])
        self.assertEqual(topo.edges, [])

    def test_missing_simulation_key_uses_defaults(self):
        topo = self._load({"nodes": [], "edges": []})
        # duration_secs default is 60.0
        self.assertAlmostEqual(topo.simulation.duration_secs, 60.0)

    def test_epoch_explicit_nonzero_preserved(self):
        topo = self._load({"simulation": {"epoch": 1_000_000}})
        self.assertEqual(topo.simulation.epoch, 1_000_000)

    def test_epoch_zero_replaced_by_wallclock(self):
        before = int(time.time())
        topo = self._load({"simulation": {"epoch": 0}})
        self.assertGreaterEqual(topo.simulation.epoch, before)

    def test_seed_none_by_default(self):
        topo = self._load({})
        self.assertIsNone(topo.simulation.seed)

    def test_seed_integer_preserved(self):
        topo = self._load({"simulation": {"seed": 99}})
        self.assertEqual(topo.simulation.seed, 99)

    def test_prv_key_preserved(self):
        key = "ab" * 64   # 128 hex chars
        topo = self._load({"nodes": [{"name": "x", "prv_key": key}]})
        self.assertEqual(topo.nodes[0].prv_key, key)

    def test_relay_default_false(self):
        topo = self._load({"nodes": [{"name": "x"}]})
        self.assertFalse(topo.nodes[0].relay)

    def test_relay_true_parsed(self):
        topo = self._load({"nodes": [{"name": "r", "relay": True}]})
        self.assertTrue(topo.nodes[0].relay)

    def test_adversarial_replay_mode_parsed(self):
        topo = self._load({
            "nodes": [{
                "name": "r",
                "relay": True,
                "adversarial": {
                    "mode": "replay",
                    "probability": 0.75,
                    "replay_delay_ms": 2000.0,
                },
            }]
        })
        adv = topo.nodes[0].adversarial
        self.assertIsNotNone(adv)
        self.assertEqual(adv.mode, "replay")
        self.assertAlmostEqual(adv.probability, 0.75)
        self.assertAlmostEqual(adv.replay_delay_ms, 2000.0)

    def test_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("this is not json{{{")
            path = f.name
        try:
            with self.assertRaises(json.JSONDecodeError):
                load_topology(path)
        finally:
            os.unlink(path)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_topology("/nonexistent/path/topology.json")


if __name__ == "__main__":
    unittest.main()
