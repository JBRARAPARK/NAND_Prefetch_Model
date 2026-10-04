"""Decision placement, overlap with lookup, and outstanding ownership."""
from dataclasses import replace
import unittest

from multiport_sim import MultiportConfig, MultiportSimulator


class PrefetchDecisionChecks(unittest.TestCase):
    def run_case(self, **kwargs):
        c=replace(MultiportConfig(requests=1,request_bytes=16384,
                                  scenario='ready',outstanding=128),**kwargs)
        s=MultiportSimulator(c);m,_=s.run()
        return s,m

    def test_early_decision_is_hidden_without_holding_host_credits(self):
        original,baseline=self.run_case()
        for delay in [.1,.2,.3]:
            with self.subTest(delay=delay):
                sim,m=self.run_case(prefetch_decision_us=delay)
                self.assertEqual(m['throughput_gbps'],baseline['throughput_gbps'])
                self.assertEqual(m['mean_burst_latency_us'],baseline['mean_burst_latency_us'])
                self.assertEqual(m['ready_hit_at_ar'],1)
                self.assertAlmostEqual(sim.pages[0]['ready']-original.pages[0]['ready'],delay)

    def test_insufficient_lead_exposes_decision_after_lookup(self):
        nand_us=.1+2.08+16384/2400+.05+.2
        original,_=self.run_case(early_lead_us=nand_us-.5)
        for delay in [.1,.2,.3]:
            with self.subTest(delay=delay):
                sim,m=self.run_case(early_lead_us=nand_us-.5,prefetch_decision_us=delay)
                self.assertAlmostEqual(sim.bursts[0]['rlast']-original.bursts[0]['rlast'],delay)
                self.assertEqual(m['nand_bytes'],16384)
                self.assertEqual(m['port_peak_outstanding'],[64]*4)

    def test_demand_can_read_before_speculative_decision_finishes(self):
        cold,_=self.run_case(scenario='none')
        delayed,m=self.run_case(early_lead_us=.1,prefetch_decision_us=2)
        self.assertEqual(delayed.bursts[0]['rlast'],cold.bursts[0]['rlast'])
        self.assertEqual(m['nand_bytes'],16384)
        self.assertEqual(len([e for e in delayed.trace if e['event']=='nand_issue']),1)

    def test_host_decision_holds_outstanding_and_is_pipelined(self):
        for delay in [.1,.2,.3]:
            for outstanding in [1,128]:
                with self.subTest(delay=delay,outstanding=outstanding):
                    sim,m=self.run_case(host_decision_us=delay,outstanding=outstanding)
                    self.assertEqual(m['port_peak_outstanding'],[min(64,outstanding)]*4)
                    self.assertEqual(len([e for e in sim.trace if e['event']=='host_decision_done']),sim.total)
                    for b in sim.bursts.values():
                        self.assertAlmostEqual(b['decision_complete_us']-b['ar'],delay)
                        self.assertGreaterEqual(b['lookup_start']+1e-9,b['decision_complete_us'])
                    self.assertAlmostEqual(sim.bursts[0]['rlast']-sim.c.first_demand_us,delay+.501)
                    if outstanding==128:
                        self.assertAlmostEqual(sim.bursts[4]['decision_complete_us']-
                                               sim.bursts[0]['decision_complete_us'],.001)

    def test_host_path_matches_integer_nanosecond_recurrence(self):
        for delay_ns,o in [(100,151),(200,176),(300,201)]:
            sim,_=self.run_case(requests=8,host_decision_us=delay_ns/1000,outstanding=o)
            ars,starts,dones,returns=[],[],[],[]
            for i,bid in enumerate(range(0,sim.total,4)):
                ar=max(ars[-1]+1 if i else 0,returns[i-o] if i>=o else 0)
                earliest=max(ar+delay_ns,starts[i-2]+2 if i>=2 else 0,
                             dones[i-500] if i>=500 else 0)
                start=((earliest+1)//2)*2
                last=max(start+500,returns[-1] if i else 0)+1
                ars.append(ar);starts.append(start);dones.append(start+500);returns.append(last)
                for key,value in [('ar',ar),('lookup_start',start),('rlast',last)]:
                    self.assertAlmostEqual((sim.bursts[bid][key]-sim.c.first_demand_us)*1000,
                                           value,places=5)

    def test_speculative_decision_does_not_affect_disabled_prefetch(self):
        before,bm=self.run_case(scenario='none')
        after,am=self.run_case(scenario='none',prefetch_decision_us=.3)
        self.assertEqual(bm['throughput_gbps'],am['throughput_gbps'])
        self.assertEqual(before.bursts,after.bursts)

    def test_invalid_decision_latency(self):
        for name in ['prefetch_decision_us','host_decision_us']:
            for value in [-.1,float('inf'),float('nan'),True]:
                with self.subTest(name=name,value=value),self.assertRaises(ValueError):
                    self.run_case(**{name:value})


if __name__=='__main__':unittest.main()
