"""Independent FIFO/clock equations and energy conservation checks."""
from dataclasses import replace
import math
import unittest

from axi_burst_sim import Config, Simulator
from lookup_power import PowerConfig, measure_energy


class LookupClockChecks(unittest.TestCase):
    def test_clocked_fifo_matches_independent_recurrence(self):
        for frequency in (500,800,1000):
            for delay in (0,.5):
                for slots,pipelines,ii in ((1,1,1),(4,2,3),(64,1,1),(250,2,1)):
                    with self.subTest(frequency=frequency,delay=delay,slots=slots,
                                      pipelines=pipelines,ii=ii):
                        c=Config(requests=1,burst_bytes=64,scenario='ready',
                                 axi_clock_mhz=1000,lookup_clock_mhz=frequency,
                                 lookup_slots=slots,lookup_pipelines=pipelines,
                                 lookup_ii_cycles=ii,lookup_us=delay,outstanding=251)
                        sim=Simulator(c);metrics,_=sim.run()
                        ars,starts,done,returns=[],[],[],[]
                        for i in range(sim.total):
                            ar=max(ars[-1]+.001 if i else 0,
                                   returns[i-c.outstanding] if i>=c.outstanding else 0)
                            earliest=max(ar,done[i-slots] if i>=slots else 0,
                                         starts[i-pipelines]+ii/frequency if i>=pipelines else 0)
                            start=math.ceil(earliest*frequency-1e-7)/frequency
                            finish=start+delay
                            returned=max(finish,returns[-1] if i else 0)+.002
                            ars.append(ar);starts.append(start);done.append(finish);returns.append(returned)
                        self.assertAlmostEqual(metrics['completion_span_us'],returns[-1],places=6)
                        for i,b in sim.bursts.items():
                            self.assertAlmostEqual(b['lookup_start']-c.first_demand_us,starts[i],places=6)
                        self.assertLessEqual(metrics['peak_lookup_active'],slots)

    def test_zero_service_is_still_limited_by_clock_and_ii(self):
        base=Config(requests=2,burst_bytes=64,scenario='ready',axi_clock_mhz=1000,
                    lookup_us=0,lookup_slots=64,lookup_clock_mhz=500,lookup_ii_cycles=2,
                    outstanding=500)
        one=Simulator(base);two=Simulator(replace(base,lookup_pipelines=2))
        a,_=one.run();b,_=two.run()
        self.assertAlmostEqual(a['completion_span_us'],(one.total-1)*.004+.002,places=6)
        self.assertAlmostEqual(b['completion_span_us'],two.total*.002,places=6)

    def test_clocked_miss_merging_and_small_buffer_progress(self):
        c=Config(requests=2,burst_bytes=64,scenario='mixed',axi_clock_mhz=1000,
                 lookup_us=.5,lookup_slots=4,lookup_clock_mhz=500,lookup_ii_cycles=3,
                 outstanding=500,buffer_bytes=16384)
        sim=Simulator(c);metrics,_=sim.run()
        self.assertEqual(metrics['nand_bytes'],2*65536)
        self.assertLessEqual(metrics['buffer_peak_bytes'],c.buffer_bytes)
        self.assertLessEqual(metrics['peak_lookup_active'],4)
        issue={e['page']:e['time_us'] for e in sim.trace if e['event']=='nand_issue'}
        for pid,p in sim.pages.items():
            if not p['prefetch']:
                self.assertGreaterEqual(issue[pid],sim.bursts[pid*sim.bp]['lookup_complete_us'])

    def test_invalid_clock_parameters(self):
        for key,values in [('lookup_clock_mhz',[0,-1,float('inf'),float('nan'),True]),
                           ('lookup_ii_cycles',[0,-1,1.5,True]),
                           ('lookup_pipelines',[0,-1,1.5,True])]:
            for value in values:
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    Simulator(replace(Config(),**{key:value}))


class EnergyChecks(unittest.TestCase):
    def simulation(self,**kwargs):
        c=replace(Config(requests=1,request_bytes=128,page_bytes=128,burst_bytes=64,
                         scenario='ready',axi_clock_mhz=1000,lookup_slots=1,
                         lookup_clock_mhz=500,lookup_us=0,outstanding=1),**kwargs)
        sim=Simulator(c);sim.run();return sim

    def test_hand_calculated_energy_and_window(self):
        sim=self.simulation()
        p=PowerConfig(clock_eu_per_cycle=2,slot_clock_eu_per_cycle=0,
                      pipeline_clock_eu_per_cycle=0,lookup_eu_per_operation=3,
                      queue_eu_per_transition=.5,leakage_eu_per_us=100,
                      slot_leakage_eu_per_us=0,pipeline_leakage_eu_per_us=0,
                      background_eu_per_us=200,axi_eu_per_byte=.1)
        e=measure_energy(sim,p)
        self.assertEqual(e['lookup_clock_cycles'],2)
        self.assertAlmostEqual(e['total_energy_eu'],26,places=6)
        self.assertAlmostEqual(e['energy_eu_per_byte'],26/128,places=6)
        self.assertAlmostEqual(e['mean_total_power_eu_per_us'],26/.004,places=4)
        self.assertEqual(e['measured_nand_bytes'],0)

    def test_voltage_scales_only_lookup_switching(self):
        sim=self.simulation(lookup_us=.5)
        a=measure_energy(sim);b=measure_energy(sim,PowerConfig(lookup_voltage_v=.8))
        for key in ('clock_energy_eu','lookup_operation_energy_eu','queue_energy_eu'):
            self.assertAlmostEqual(b[key],a[key]*.64)
        for key in ('lookup_leakage_energy_eu','background_energy_eu','axi_energy_eu','nand_energy_eu'):
            self.assertEqual(a[key],b[key])
        self.assertAlmostEqual(b['total_energy_eu']/a['total_energy_eu'],
                               b['mean_total_power_eu_per_us']/a['mean_total_power_eu_per_us'])

    def test_gating_and_energy_power_time_identity(self):
        sim=self.simulation(lookup_us=0,lookup_clock_mhz=1000,outstanding=1,period_us=0)
        gated=measure_energy(sim);on=measure_energy(sim,PowerConfig(clock_gating=False))
        self.assertEqual(gated['lookup_clock_cycles'],2)
        self.assertEqual(on['lookup_clock_cycles'],4)
        span=sim.bursts[sim.total-1]['rlast']-sim.bursts[0]['ar']
        self.assertAlmostEqual(gated['total_energy_eu'],gated['mean_total_power_eu_per_us']*span)
        for key in ('lookup_operation_energy_eu','queue_energy_eu','lookup_leakage_energy_eu'):
            self.assertEqual(gated[key],on[key])

    def test_prefetch_transfer_excluded_demand_transfer_counted(self):
        ready=self.simulation();miss=self.simulation(scenario='none',lookup_us=.5)
        self.assertEqual(measure_energy(ready)['measured_nand_bytes'],0)
        self.assertEqual(measure_energy(miss)['measured_nand_bytes'],128)

    def test_measurement_requires_completed_clocked_finite_model(self):
        with self.assertRaises(ValueError):measure_energy(Simulator(Config()))
        with self.assertRaises(ValueError):
            measure_energy(Simulator(Config(lookup_clock_mhz=500,lookup_slots=1)))
        sim=self.simulation()
        for kwargs in ({'lookup_voltage_v':0},{'clock_eu_per_cycle':-1},
                       {'background_eu_per_us':float('nan')},{'clock_gating':1}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                measure_energy(sim,PowerConfig(**kwargs))


if __name__=='__main__':unittest.main()
