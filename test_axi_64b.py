"""Analytic checks for 64-byte bursts and 500ns parallel lookup."""
import unittest
from axi_burst_sim import Config, Simulator


class SmallBurstChecks(unittest.TestCase):
    def simulate(self, **kw):
        cfg = dict(requests=1, burst_bytes=64, tr_us=2.08,
                   axi_clock_mhz=1000, scenario='ready', lookup_us=.5,
                   outstanding=100)
        cfg.update(kw)
        sim = Simulator(Config(**cfg))
        metrics, _ = sim.run()
        return sim, metrics

    def test_ready_matches_independent_window_recurrence(self):
        for outstanding in (100, 200, 250, 251, 300, 400, 500):
            with self.subTest(outstanding=outstanding):
                sim, metrics = self.simulate(outstanding=outstanding)
                accepted, completed = [], []
                for i in range(1024):
                    ar = max(accepted[-1] + .001 if i else 0,
                             completed[i-outstanding] if i >= outstanding else 0)
                    done = max(ar + .5, completed[-1] if i else 0) + .002
                    accepted.append(ar)
                    completed.append(done)
                self.assertAlmostEqual(metrics['completion_span_us'], completed[-1], places=6)
                self.assertLessEqual(metrics['peak_outstanding'], outstanding)
                self.assertEqual([e['burst'] for e in sim.trace if e['event']=='rlast'], list(range(1024)))

    def test_exact_window_boundary(self):
        _, below = self.simulate(outstanding=250)
        _, at = self.simulate(outstanding=251)
        self.assertGreater(below['completion_span_us'], .5 + 1024*.002 + .001)
        self.assertAlmostEqual(at['completion_span_us'], .5 + 1024*.002, places=6)

    def test_64b_misses_merge_into_full_pages(self):
        sim, metrics = self.simulate(scenario='none', outstanding=500)
        self.assertEqual(metrics['nand_bytes'], 65536)
        self.assertEqual(len([e for e in sim.trace if e['event']=='nand_issue']), 4)
        first_issue = min(e['time_us'] for e in sim.trace if e['event']=='nand_issue')
        self.assertGreaterEqual(first_issue, sim.c.first_demand_us + .5)
        self.assertEqual(sim.used, 0)


if __name__ == '__main__':
    unittest.main()
