"""Equal-capacity 1GHz/0ns versus 500MHz/500ns, with explicit energy assumptions."""
import argparse
import csv
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from axi_burst_sim import Config, Simulator
from lookup_power import PowerConfig, measure_energy

SLOTS=[1,4,16,64,128,200,250,500]
OUTSTANDING=[100,251,500]
SCENARIOS=['ready','none','late','mixed']
SOURCE_PATHS=['axi_burst_sim.py','lookup_power.py','test_lookup_clock_power.py',
              'experiments/run_lookup_clock_power.py','experiments/summarize_lookup_clock_power.py']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests',type=int,default=32)
    parser.add_argument('--out',type=Path,default=ROOT/'results/lookup_clock_power_64b')
    parser.add_argument('--power-config',type=Path,help='JSON overrides of relative PowerConfig coefficients')
    parser.add_argument('--slow-voltage',type=float,default=.8,
                        help='additional hypothetical slow-domain voltage, in volts')
    args=parser.parse_args()
    if args.requests<1:parser.error('--requests must be positive')
    if not math.isfinite(args.slow_voltage) or args.slow_voltage<=0:
        parser.error('--slow-voltage must be finite and positive')
    power=PowerConfig(**(json.loads(args.power_config.read_text()) if args.power_config else {}))
    # Validate supplied coefficients before executing the full sweep.
    probe=Simulator(Config(requests=1,lookup_slots=1,lookup_clock_mhz=1000))
    probe.run();measure_energy(probe,power)
    args.out.mkdir(parents=True,exist_ok=True)
    base=Config(requests=args.requests,burst_bytes=64,tr_us=2.08,axi_clock_mhz=1000,
                mapping='striped',channels=4)
    conditions=[('main',s,o,c,1,1) for s in SCENARIOS for o in OUTSTANDING for c in SLOTS]
    conditions += [('admission','ready',500,c,p,ii) for c in [64,250,500]
                   for p in [1,2] for ii in [2,4]]
    rows=[];timings={};start=time.monotonic()
    for index,(group,scenario,outstanding,slots,pipelines,ii) in enumerate(conditions):
        for design,frequency,delay in [('fast',1000,0),('slow',500,.5)]:
            c=replace(base,scenario=scenario,outstanding=outstanding,lookup_slots=slots,
                      lookup_pipelines=pipelines,lookup_ii_cycles=ii,
                      lookup_clock_mhz=frequency,lookup_us=delay)
            sim=Simulator(c);metrics,_=sim.run()
            lat=sorted(b['rlast']-b['ar'] for b in sim.bursts.values())
            metrics['p99_burst_latency_us']=lat[math.ceil(.99*sim.total)-1]
            middle=sim.total//2
            metrics['tail_throughput_gbps']=(sim.total-middle)*c.burst_bytes/(
                sim.bursts[sim.total-1]['rlast']-sim.bursts[middle-1]['rlast'])/1000
            variants=[('same_voltage_always_on',False,power.reference_voltage_v),
                      ('same_voltage_gated',True,power.reference_voltage_v)]
            if design=='slow':
                variants += [('lower_voltage_always_on',False,args.slow_voltage),
                             ('lower_voltage_gated',True,args.slow_voltage)]
            for variant,gating,voltage in variants:
                energy=measure_energy(sim,replace(power,clock_gating=gating,lookup_voltage_v=voltage))
                rows.append(dict(group=group,scenario=scenario,outstanding=outstanding,
                                 lookup_slots=slots,lookup_pipelines=pipelines,lookup_ii_cycles=ii,
                                 design=design,lookup_clock_mhz=frequency,lookup_us=delay,
                                 power_variant=variant,clock_gating=gating,lookup_voltage_v=voltage,
                                 **metrics,**energy))
            if group=='main' and scenario=='ready' and outstanding==500 and slots in (64,250):
                timings[f'{design}_C{slots}']=[dict(burst=i,**{
                    k:round(b[k]-c.first_demand_us,9) for k in
                    ('ar','lookup_start','lookup_complete_us','r_start','rlast')}) for i,b in
                    list(sim.bursts.items())[:16]]
        if (index+1)%8==0 or index==len(conditions)-1:
            print(f'{index+1}/{len(conditions)} pairs; {time.monotonic()-start:.1f}s',flush=True)
    with (args.out/'sweep.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (args.out/'example_timelines.json').write_text(json.dumps(timings,indent=2)+'\n')
    manifest=dict(base_config=asdict(base),power_coefficients=asdict(power),
                  lower_voltage_hypothesis_v=args.slow_voltage,slots=SLOTS,
                  outstanding=OUTSTANDING,scenarios=SCENARIOS,comparison_pairs=len(conditions),
                  simulator_cases=len(conditions)*2,energy_rows=len(rows),
                  runtime_seconds=time.monotonic()-start,python=platform.python_version(),
                  base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCE_PATHS},
                  semantics='Only lookup clock changes; AXI stays 1GHz. Equal slots, pipelines and II cycles within each pair. Zero latency is ideal service with clock-limited admission. Phase-aligned domains; no extra CDC delay. Demand window first AR to last RLAST excludes prefetch warmup. Relative EU coefficients are illustrative, not device watts. Voltage does not change timing or leakage automatically.')
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(args.out,flush=True)


if __name__=='__main__':main()
