import unittest
from dataclasses import replace
from axi_burst_sim import Config, Simulator

class BurstChecks(unittest.TestCase):
    def run_case(self,**kw):
        s=Simulator(replace(Config(),requests=2,**kw));m,r=s.run();return s,m,r
    def test_ready_transfer_floor(self):
        _,m,_=self.run_case(scenario='ready',outstanding=16)
        self.assertAlmostEqual(m['completion_span_us'],2*65536/16000,places=7)
        self.assertEqual(m['ready_hit_at_ar'],1)
    def test_lookup_serial_cost(self):
        _,m,_=self.run_case(scenario='ready',lookup_us=3,outstanding=1)
        self.assertAlmostEqual(m['completion_span_us'],32*(3+.256),places=7)
    def test_window_hides_lookup(self):
        _,m,_=self.run_case(scenario='ready',lookup_us=3,outstanding=16)
        self.assertAlmostEqual(m['completion_span_us'],3+32*.256,places=7)
    def test_outstanding_and_return_order(self):
        s,m,_=self.run_case(scenario='mixed',lookup_us=1,outstanding=32)
        self.assertEqual([r['burst'] for r in s.trace if r['event']=='rlast'],list(range(32)))
        self.assertEqual(m['peak_outstanding'],32)
        self.assertTrue(all(0<=r['outstanding']<=32 for r in s.trace if 'outstanding' in r))
        self.assertGreater(m['hol_idle_us'],0)
    def test_page_read_merge(self):
        _,m,_=self.run_case(outstanding=64,lookup_us=1)
        self.assertEqual(m['nand_bytes'],2*65536)
    def test_no_nand_before_lookup(self):
        s,_,_=self.run_case(lookup_us=5,outstanding=16)
        self.assertGreaterEqual(min(x['time_us'] for x in s.trace if x['event']=='nand_issue'),20005)
    def test_analytic_one_page(self):
        _,m,_=self.run_case(request_bytes=16384,period_us=100,outstanding=4)
        expected=.1+3+16384/2400+.05+.2+4*.256
        self.assertAlmostEqual(m['mean_request_latency_us'],expected,places=7)
    def test_small_buffer_progress(self):
        s,m,_=self.run_case(buffer_bytes=16384,outstanding=32,scenario='mixed')
        self.assertLessEqual(m['buffer_peak_bytes'],16384)
    def test_tr_change_only_miss_path(self):
        _,a,_=self.run_case(tr_us=3,scenario='ready',outstanding=16)
        _,b,_=self.run_case(tr_us=50,scenario='ready',outstanding=16)
        self.assertAlmostEqual(a['completion_span_us'],b['completion_span_us'])

if __name__=='__main__':unittest.main()
