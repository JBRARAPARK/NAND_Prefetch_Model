"""Independent port queue recurrences, shared NAND progress and energy checks."""
from dataclasses import replace
import math
import unittest

from axi_burst_sim import Config, Simulator
from multiport_sim import MultiportConfig, MultiportSimulator
from lookup_power import PowerConfig, measure_energy


class MultiportChecks(unittest.TestCase):
    def config(self,**kwargs):
        return replace(MultiportConfig(requests=2,scenario='ready'),**kwargs)

    def test_independent_port_clock_fifo_recurrence(self):
        for ports in [1,2,4]:
            for slots,outstanding,pipelines,delay in [(1,8,1,0),(4,16,2,.5),(500,501,2,.5)]:
                with self.subTest(ports=ports,slots=slots,delay=delay):
                    c=self.config(host_ports=ports,lookup_slots=slots,outstanding=outstanding,
                                  lookup_pipelines=pipelines,lookup_us=delay)
                    sim=MultiportSimulator(c);m,_=sim.run()
                    for port in range(ports):
                        ars,starts,dones,returns=[],[],[],[]
                        for i,bid in enumerate(range(port,sim.total,ports)):
                            ar=max(ars[-1]+.001 if i else 0,
                                   returns[i-outstanding] if i>=outstanding else 0)
                            earliest=max(ar,dones[i-slots] if i>=slots else 0,
                                         starts[i-pipelines]+.002 if i>=pipelines else 0)
                            start=math.ceil(earliest*500-1e-7)/500
                            done=start+delay;last=max(done,returns[-1] if i else 0)+.001
                            ars.append(ar);starts.append(start);dones.append(done);returns.append(last)
                            b=sim.bursts[bid]
                            for key,value in [('ar',ar),('lookup_start',start),('rlast',last)]:
                                self.assertAlmostEqual(b[key]-c.first_demand_us,value,places=6)
                        self.assertLessEqual(m['port_peak_lookup_active'][port],slots)
                        self.assertLessEqual(m['port_peak_outstanding'][port],outstanding)

    def test_256_gbps_ceiling_and_ready_boundary(self):
        c=self.config(requests=8,lookup_us=0,lookup_clock_mhz=1000,lookup_slots=2000)
        sim=MultiportSimulator(c);m,_=sim.run()
        self.assertAlmostEqual(m['throughput_gbps'],256,places=5)
        self.assertEqual(m['host_ceiling_gbps'],256)
        for tp in m['port_throughput_gbps']:self.assertAlmostEqual(tp,64,places=5)
        slow=MultiportSimulator(replace(c,lookup_clock_mhz=500,lookup_us=.5,lookup_slots=500))
        sm,_=slow.run()
        self.assertAlmostEqual(sm['tail_throughput_gbps'],256,places=5)
        below=MultiportSimulator(replace(slow.c,outstanding=501))
        bm,_=below.run();self.assertLess(bm['tail_throughput_gbps'],256-.1)
        one=MultiportSimulator(replace(slow.c,lookup_pipelines=1))
        om,_=one.run();self.assertAlmostEqual(om['tail_throughput_gbps'],128,places=5)

    def test_global_page_striping_uses_all_128_channels(self):
        sim=MultiportSimulator(self.config(requests=32))
        m,_=sim.run()
        self.assertEqual(m['used_nand_channels'],128)
        counts=[sum(p['ch']==i for p in sim.pages.values()) for i in range(128)]
        self.assertEqual(counts,[1]*128)

    def test_one_port_matches_legacy_metrics_requests_and_energy(self):
        for scenario in ['ready','none','late','mixed']:
            kwargs=dict(requests=2,scenario=scenario,burst_bytes=64,axi_width_bits=512,
                        axi_clock_mhz=1000,chips=4,channels=4,tr_us=2.08,
                        mapping='striped',lookup_clock_mhz=500,lookup_us=.5,
                        lookup_slots=4,lookup_pipelines=2,outstanding=100)
            old=Simulator(Config(**kwargs));new=MultiportSimulator(MultiportConfig(host_ports=1,**kwargs))
            before,requests=old.run();after,new_requests=new.run()
            self.assertEqual(requests,new_requests)
            for k,v in before.items():self.assertEqual(v,after[k],k)
            self.assertEqual(measure_energy(old),measure_energy(new))

    def test_shared_nand_merges_pages_and_small_buffer_finishes(self):
        c=self.config(scenario='mixed',buffer_bytes=16384,lookup_slots=4,outstanding=100)
        sim=MultiportSimulator(c);m,requests=sim.run()
        self.assertEqual(m['nand_bytes'],c.requests*c.request_bytes)
        self.assertLessEqual(m['buffer_peak_bytes'],16384)
        self.assertEqual(len([e for e in sim.trace if e['event']=='nand_issue']),c.requests*4)
        for r in requests:
            bids=range(r['request']*sim.br,(r['request']+1)*sim.br)
            self.assertEqual(r['full_us'],max(sim.bursts[i]['rlast'] for i in bids))
        for p in range(c.host_ports):
            returned=[e['burst'] for e in sim.trace if e['event']=='rlast' and e['port']==p]
            self.assertEqual(returned,list(range(p,sim.total,c.host_ports)))

    def test_no_global_return_barrier_between_ports(self):
        c=self.config(requests=2,page_bytes=65536,request_bytes=65536,burst_bytes=4096,
                      host_ports=2,lookup_us=0,lookup_clock_mhz=1000,outstanding=100)
        sim=MultiportSimulator(c);sim.run()
        # Both ports return concurrently within each page; cross-port return
        # order is allowed while each port preserves its accepted burst order.
        self.assertEqual(sim.bursts[0]['r_start'],sim.bursts[1]['r_start'])
        self.assertEqual(sim.bursts[0]['rlast'],sim.bursts[1]['rlast'])
        delayed=MultiportSimulator(c)
        delayed.ports[0].lanes=[(c.first_demand_us+1,j) for j in range(c.lookup_pipelines)]
        delayed.run()
        self.assertLess(delayed.bursts[1]['rlast'],delayed.bursts[0]['rlast'])

    def test_multiport_energy_conservation_and_single_shared_nand_charge(self):
        sim=MultiportSimulator(self.config(scenario='none',outstanding=10000));m,_=sim.run()
        e=measure_energy(sim)
        self.assertEqual(e['measured_nand_bytes'],sim.c.requests*sim.c.request_bytes)
        self.assertAlmostEqual(e['total_energy_eu'],e['mean_total_power_eu_per_us']*m['completion_span_us'])
        self.assertLessEqual(e['lookup_clock_duty'],1)
        lower=measure_energy(sim,PowerConfig(lookup_voltage_v=.8))
        self.assertEqual(e['nand_energy_eu'],lower['nand_energy_eu'])
        self.assertAlmostEqual(lower['lookup_operation_energy_eu'],e['lookup_operation_energy_eu']*.64)

    def test_invalid_port_count(self):
        for value in [0,-1,1.5,True]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                MultiportSimulator(self.config(host_ports=value))


if __name__=='__main__':unittest.main()
