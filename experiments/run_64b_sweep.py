"""Reproducible 64B AXI extension of the existing burst simulator."""
import argparse
import csv
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from axi_burst_sim import Config, Simulator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests', type=int, default=32)
    parser.add_argument('--out', type=Path, default=ROOT / 'results/axi_64b_tr2p08')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    base = Config(requests=args.requests, burst_bytes=64, tr_us=2.08,
                  axi_clock_mhz=1000, outstanding=100)
    rows = []
    start = time.monotonic()
    for mapping, channels in [('striped', 4), ('single', 1)]:
        for scenario in ['ready', 'none', 'late', 'mixed']:
            for outstanding in [100, 200, 250, 251, 300, 400, 500]:
                for lookup in [0., .5]:
                    cfg = replace(base, mapping=mapping, channels=channels,
                                  scenario=scenario, outstanding=outstanding, lookup_us=lookup)
                    sim = Simulator(cfg)
                    metrics, _ = sim.run()
                    middle = sim.total // 2
                    # Tail measurement excludes initial fill but remains a finite-run metric.
                    tail_span = sim.bursts[sim.total-1]['rlast'] - sim.bursts[middle-1]['rlast']
                    latencies = sorted(b['rlast']-b['ar'] for b in sim.bursts.values())
                    row = dict(mapping=mapping, channels=channels, scenario=scenario,
                               outstanding=outstanding, lookup_us=lookup, **metrics,
                               tail_throughput_gbps=(sim.total-middle)*cfg.burst_bytes/tail_span/1000,
                               p99_burst_latency_us=latencies[__import__('math').ceil(.99*len(latencies))-1],
                               first_burst_latency_us=sim.bursts[0]['rlast']-sim.bursts[0]['ar'])
                    rows.append(row)
            print(f'{mapping} {scenario}: {len(rows)} cases, {time.monotonic()-start:.1f}s', flush=True)
    with (args.out/'sweep.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    sources = ['axi_burst_sim.py', 'experiments/run_64b_sweep.py', 'test_axi_64b.py']
    manifest = dict(base_config=asdict(base), outstanding=[100,200,250,251,300,400,500],
                    lookup_us=[0,.5], cases=len(rows), python=platform.python_version(),
                    elapsed_seconds=time.monotonic()-start,
                    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    source_sha256={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},
                    interpretation='64B AXI burst within sequential 64KiB logical requests; 16KiB NAND pages unchanged; 500ns parallel per-burst hit/miss lookup after AR; 1GHz GUI clock profile')
    (args.out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(args.out, flush=True)


if __name__ == '__main__':
    main()
