"""Four independent 512-bit ports: ready ceiling and shared NAND supply."""
import csv
from dataclasses import asdict,replace
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from multiport_sim import MultiportConfig,MultiportSimulator
from lookup_power import PowerConfig,measure_energy

OUT=ROOT/'results/multiport_256'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base=MultiportConfig(requests=128,record_trace=False)
    rows=[];start=time.monotonic()
    conditions=[]
    for o in [100,501,502,10000]:
        conditions.append((f'ready_O{o}',replace(base,scenario='ready',outstanding=o)))
    for channels in [4,32,64,107,128]:
        conditions.append((f'nand_{channels}ch',replace(base,scenario='none',chips=channels,channels=channels,outstanding=10000)))
    conditions += [('nand_small_window',replace(base,scenario='none',outstanding=502)),
                   ('nand_legacy_mapping',replace(base,scenario='none',mapping='striped',outstanding=10000)),
                   ('nand_long',replace(base,requests=512,scenario='none',outstanding=10000))]
    for index,(label,cfg) in enumerate(conditions):
        for design in ['fast','slow']:
            c=replace(cfg,lookup_clock_mhz=1000,lookup_us=0,lookup_slots=2000) if design=='fast' else cfg
            sim=MultiportSimulator(c);m,_=sim.run()
            clean={k:json.dumps(v) if isinstance(v,list) else v for k,v in m.items()}
            variants=[('same_voltage_gated',PowerConfig()),('same_voltage_always_on',PowerConfig(clock_gating=False))]
            if design=='slow':variants.append(('lower_voltage_gated',PowerConfig(lookup_voltage_v=.8)))
            for variant,power in variants:
                energy=measure_energy(sim,power)
                rows.append(dict(case=label,design=design,scenario=c.scenario,requests=c.requests,
                                 chips=c.chips,channels=c.channels,mapping=c.mapping,host_ports=c.host_ports,
                                 axi_width_bits=c.axi_width_bits,axi_clock_mhz=c.axi_clock_mhz,
                                 outstanding_per_port=c.outstanding,lookup_slots_per_port=c.lookup_slots,
                                 lookup_pipelines_per_port=c.lookup_pipelines,lookup_clock_mhz=c.lookup_clock_mhz,
                                 lookup_us=c.lookup_us,power_variant=variant,lookup_voltage_v=power.lookup_voltage_v,
                                 **clean,**energy))
            print(f'{index+1}/{len(conditions)} {label} {design}: full={m["throughput_gbps"]:.3f}, tail={m["tail_throughput_gbps"]:.3f} GB/s ({time.monotonic()-start:.1f}s)',flush=True)
    with (OUT/'sweep.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    sources=['axi_burst_sim.py','multiport_sim.py','lookup_power.py','test_multiport.py',
             'experiments/run_multiport_256.py']
    manifest=dict(base_config=asdict(base),performance_cases=len(conditions)*2,energy_rows=len(rows),
                  runtime_seconds=time.monotonic()-start,tests=43,legacy_conditions=32,
                  source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
                  power_coefficients=asdict(PowerConfig()),
                  semantics='Four independent AR/R ports. Outstanding/lookup slots/pipelines are per port. Burst IDs round-robin over ports, FIFO return within each port; request completion is max of all constituent returns. Global page striping shares NAND/buffer. No cross-port global return barrier. Fast slots are 4x slow, pipelines equal. Tail uses aggregate completion window after half the bursts have completed, not a fitted steady-state rate. Shared background coefficient is fixed; NAND channel leakage, fabric arbitration, host protocol and PHY power are not calibrated.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for design in ['fast','slow']:
        c=replace(base,scenario='ready')
        if design=='fast':c=replace(c,lookup_clock_mhz=1000,lookup_us=0,lookup_slots=2000)
        (OUT/f'config_{design}_ready.json').write_text(json.dumps(asdict(c),indent=2)+'\n')
    print(OUT,flush=True)


if __name__=='__main__':main()
