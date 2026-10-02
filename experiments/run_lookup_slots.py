"""Finite lookup concurrency sweep using the existing AXI/NAND simulator."""
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
from axi_burst_sim import Config,Simulator

SLOTS=[1,4,16,64,100,128,200,249,250,251,500,None]
OUTSTANDING=[100,200,300,400,500]
SCENARIOS=['ready','none','late','mixed']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests',type=int,default=32)
    parser.add_argument('--out',type=Path,default=ROOT/'results/lookup_slots_64b')
    args=parser.parse_args()
    if args.requests<1:parser.error('--requests must be positive')
    args.out.mkdir(parents=True,exist_ok=True)
    base=Config(requests=args.requests,burst_bytes=64,tr_us=2.08,axi_clock_mhz=1000,
                lookup_us=.5,mapping='striped',channels=4)
    rows=[];start=time.monotonic()
    for scenario in SCENARIOS:
        for outstanding in OUTSTANDING:
            conditions=[(n,.5) for n in SLOTS]+[(None,0.)]
            for slots,delay in conditions:
                c=replace(base,scenario=scenario,outstanding=outstanding,lookup_slots=slots,lookup_us=delay)
                sim=Simulator(c);metrics,_=sim.run()
                n=sim.total;middle=n//2
                lat=sorted(b['rlast']-b['ar'] for b in sim.bursts.values())
                row=dict(scenario=scenario,outstanding=outstanding,
                         lookup_slots='unlimited' if slots is None else slots,lookup_us=delay,
                         **metrics,p99_burst_latency_us=lat[math.ceil(.99*n)-1],
                         tail_throughput_gbps=(n-middle)*64/(sim.bursts[n-1]['rlast']-sim.bursts[middle-1]['rlast'])/1000)
                rows.append(row)
                if scenario=='ready' and outstanding==500 and slots==4:
                    sample=[]
                    for bid in range(16):
                        b=sim.bursts[bid]
                        sample.append(dict(burst=bid,**{k:round(b[k]-c.first_demand_us,9) for k in
                                                     ['ar','lookup_start','lookup_complete_us','r_start','rlast']}))
                    with (args.out/'example_timeline.csv').open('w',newline='') as f:
                        w=csv.DictWriter(f,fieldnames=list(sample[0]));w.writeheader();w.writerows(sample)
            print(f'{scenario} O={outstanding}: {len(rows)} cases ({time.monotonic()-start:.1f}s)',flush=True)
    with (args.out/'sweep.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    paths=['axi_burst_sim.py','test_lookup_slots.py','experiments/run_lookup_slots.py']
    manifest=dict(base_config=asdict(base),lookup_slots=SLOTS,outstanding=OUTSTANDING,scenarios=SCENARIOS,
                  lookup_us=.5,additional_baseline='unlimited lookup slots, lookup_us=0',cases=len(rows),
                  runtime_seconds=time.monotonic()-start,python=platform.python_version(),
                  base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
                  semantics='A slot is held for the full lookup service latency, released before NAND/AXI completion. FIFO waiting remains inside AR-to-RLAST outstanding. No separate lookup initiation-interval or bank-conflict model.')
    (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(args.out,flush=True)


if __name__=='__main__':main()
