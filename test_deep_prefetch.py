import unittest
from deep_prefetch_sim import DeepConfig,DeepSimulator
class DeepTests(unittest.TestCase):
    def test_modes_and_drain(self):
        for mode in ('demand','ready','online'):
            for accuracy in (0, .5, 1):
                c=DeepConfig(requests=4,mode=mode,accuracy=accuracy,period_us=1.024,buffer_bytes=8*16384,prefetch_limit=4,record_trace=True)
                s=DeepSimulator(c);m,r=s.run()
                self.assertEqual(s.active,0);self.assertEqual(s.used,0);self.assertFalse(s.pf_descriptor_ids);self.assertFalse(s.pending_pages)
                self.assertEqual(len(r),4)
                self.assertEqual(len(s.bursts),4096)
                for port in s.ports:
                    ids=[x['burst'] for x in s.trace if x['event']=='rlast' and x['port']==port.index]
                    self.assertEqual(ids,list(range(port.index,4096,4)))
    def test_budget_and_throttle(self):
        for throttle in (False,True):
            s=DeepSimulator(DeepConfig(requests=4,mode='online',accuracy=.5,total_descriptors=40,outstanding=16,prefetch_limit=8,throttle=throttle,record_trace=False))
            m,_=s.run();self.assertLessEqual(m['prefetch_peak_descriptors'],8)
    def test_merge(self):
        s=DeepSimulator(DeepConfig(requests=2,mode='online',record_trace=False))
        m,_=s.run();self.assertEqual(m['nand_bytes'],2*65536)
    def test_invalid(self):
        with self.assertRaises(ValueError):DeepSimulator(DeepConfig(accuracy=2))
    def test_exact_once_and_budget(self):
        c=DeepConfig(requests=8,mode='online',accuracy=.5,total_descriptors=80,outstanding=32,prefetch_limit=8,prediction_queue_limit=16,record_trace=True)
        s=DeepSimulator(c);m,_=s.run()
        issued=[e['page'] for e in s.trace if e['event']=='nand_issue']
        self.assertEqual(len(issued),len(set(issued)))
        self.assertLessEqual(m['total_descriptor_peak'],80)
        self.assertLessEqual(m['prediction_descriptor_peak'],16)
        self.assertEqual(sum(e['event']=='ar' for e in s.trace),s.total)
        self.assertEqual(sum(e['event']=='rlast' for e in s.trace),s.total)
    def test_throttle_starvation_observable(self):
        s=DeepSimulator(DeepConfig(requests=8,mode='online',accuracy=0,throttle=True,prefetch_limit=0,record_trace=False))
        m,_=s.run();self.assertGreater(m['prefetch_unissued'],0)
        self.assertEqual(m['nand_bytes'],8*65536)
