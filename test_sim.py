import unittest
from dataclasses import replace
from sim import Config, Simulator

class Checks(unittest.TestCase):
    def baseline(self,**kw):
        return replace(Config(),requests=1,command_us=0,turnaround_us=0,ecc_us=0,**kw)

    def test_analytic_shared_channel(self):
        c=self.baseline();s=Simulator(c);m,r=s.run()
        expected=c.tr_us+4*c.page_bytes/(c.nand_io_gbps*1000)
        ready=max(t['ready'] for t in s.tasks.values())-c.first_demand_us
        self.assertAlmostEqual(ready,expected)

    def test_independent_channels(self):
        c=self.baseline(mapping='striped',channels=4);s=Simulator(c);s.run()
        self.assertAlmostEqual(max(t['ready'] for t in s.tasks.values())-c.first_demand_us,c.tr_us+c.page_bytes/(c.nand_io_gbps*1000))

    def test_serial_plane(self):
        c=self.baseline(plane_parallel=False);s=Simulator(c);s.run()
        self.assertAlmostEqual(max(t['ready'] for t in s.tasks.values())-c.first_demand_us,4*(c.tr_us+c.page_bytes/(c.nand_io_gbps*1000)))

    def test_inorder_qd_and_capacity(self):
        c=replace(Config(),requests=12,period_us=1,host_qd=4,buffer_bytes=65536,tr_cv=.5,mapping='striped',channels=4)
        s=Simulator(c);s.run()
        done=[(t['request'],t['chunk']) for t in s.trace if t['event']=='axi_done']
        self.assertEqual(done,[(i,k) for i in range(c.requests) for k in range(4)])
        self.assertLessEqual(s.peak,c.buffer_bytes)
        for r in s.reqs:
            outstanding=sum(o['accepted']<=r['accepted']<o['returned'][-1] for o in s.reqs)
            self.assertLessEqual(outstanding,c.host_qd)

    def test_delayed_knowledge_blocks_issue(self):
        c=self.baseline(policy='fixed',lead_us=200,target_known_delay_us=280,mapping_delay_us=5)
        s=Simulator(c);s.run()
        self.assertTrue(all(t['issue']>=485 for t in s.tasks.values()))

    def test_wrong_speculation_costs_reads(self):
        c=self.baseline(policy='fixed',lead_us=200,speculative=True,accuracy=0,target_known_delay_us=280)
        s=Simulator(c);m,r=s.run()
        self.assertEqual(m['wasted_bytes'],65536)
        self.assertEqual(m['nand_bytes'],131072)
        self.assertEqual(r[0]['prediction_hit'],False)

    def test_lookup_delay(self):
        c=self.baseline(policy='fixed',lead_us=120)
        m,_=Simulator(c).run();m2,_=Simulator(replace(c,hit_lookup_delay_us=5)).run()
        self.assertAlmostEqual(m2['mean_full_stall_us']-m['mean_full_stall_us'],5)

    def test_ready_prefetch_reduces_stall(self):
        c=self.baseline(policy='fixed',lead_us=120);m,_=Simulator(c).run()
        self.assertEqual(m['ready_hit_rate'],1)
        self.assertLess(m['mean_full_stall_us'],5)

if __name__=='__main__': unittest.main()
