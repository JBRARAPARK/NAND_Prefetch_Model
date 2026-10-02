"""Independent queueing equations and invariants for bounded lookup service."""
import unittest
from dataclasses import replace
from axi_burst_sim import Config, Simulator


class LookupSlotChecks(unittest.TestCase):
    def config(self, **kwargs):
        return replace(Config(requests=1, burst_bytes=64, tr_us=2.08,
                              axi_clock_mhz=1000, scenario='ready',
                              lookup_us=.5, outstanding=500), **kwargs)

    def test_finite_service_matches_independent_recurrence(self):
        for slots in [1, 4, 64, 100, 249, 250, 251, 500]:
            for outstanding in [100, 500]:
                with self.subTest(slots=slots, outstanding=outstanding):
                    sim=Simulator(self.config(lookup_slots=slots, outstanding=outstanding))
                    metrics,_=sim.run()
                    ars, dones, returns=[],[],[]
                    for i in range(sim.total):
                        ar=max(ars[-1]+.001 if i else 0,
                               returns[i-outstanding] if i>=outstanding else 0)
                        done=max(ar,dones[i-slots] if i>=slots else 0)+.5
                        last=max(done,returns[-1] if i else 0)+.002
                        ars.append(ar);dones.append(done);returns.append(last)
                    self.assertAlmostEqual(metrics['completion_span_us'],returns[-1],places=6)
                    for i,b in sim.bursts.items():
                        self.assertAlmostEqual(b['lookup_start']-sim.c.first_demand_us,dones[i]-.5,places=6)
                    self.assertLessEqual(metrics['peak_lookup_active'],slots)
                    self.assertLessEqual(metrics['peak_outstanding'],outstanding)

    def test_large_pool_is_identical_to_unlimited(self):
        for scenario in ['none','ready','late','mixed']:
            cfg=self.config(requests=2,scenario=scenario,outstanding=100)
            a,b=Simulator(cfg),Simulator(replace(cfg,lookup_slots=100))
            self.assertEqual(a.run(),b.run())
            self.assertEqual(a.trace,b.trace)

    def test_zero_latency_one_slot_does_not_throttle(self):
        a=Simulator(self.config(lookup_slots=1,lookup_us=0))
        b=Simulator(self.config(lookup_us=0))
        self.assertEqual(a.run(),b.run())

    def test_fifo_miss_issue_after_lookup_and_buffer_progress(self):
        sim=Simulator(self.config(requests=2,scenario='mixed',lookup_slots=4,buffer_bytes=16384))
        metrics,_=sim.run()
        starts=[e['burst'] for e in sim.trace if e['event']=='lookup_start']
        self.assertEqual(starts,list(range(sim.total)))
        issued={e['page']:e['time_us'] for e in sim.trace if e['event']=='nand_issue'}
        for pid,page in sim.pages.items():
            if not page['prefetch']:
                first=sim.bursts[pid*sim.bp]['lookup_complete_us']
                self.assertGreaterEqual(issued[pid],first)
        self.assertLessEqual(metrics['buffer_peak_bytes'],16384)
        self.assertLessEqual(metrics['peak_lookup_queue'],sim.c.outstanding)
        self.assertEqual(metrics['nand_bytes'],2*65536)
        self.assertTrue(all(b['lookup_complete_us']<=b['r_start'] for b in sim.bursts.values()))

    def test_queue_is_distinct_from_service(self):
        sim=Simulator(self.config(lookup_slots=1))
        metrics,_=sim.run()
        self.assertGreater(metrics['mean_lookup_wait_us'],0)
        self.assertAlmostEqual(metrics['mean_ar_to_lookup_done_us'],metrics['mean_lookup_wait_us']+.5,places=6)
        self.assertEqual(metrics['peak_lookup_active'],1)
        self.assertGreater(metrics['peak_lookup_queue'],0)

    def test_invalid_pool(self):
        for value in [0,-1,1.5,True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                Simulator(self.config(lookup_slots=value))

if __name__=='__main__':unittest.main()
