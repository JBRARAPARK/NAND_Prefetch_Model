"""64GB/s target: ahead-of-demand versus post-AR decision latency."""
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from multiport_sim import MultiportConfig,MultiportSimulator

OUT=ROOT/'results/prefetch_decision_64'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    cases=[]
    # Ready-hit capacity: saturated arrivals isolate outstanding retirement.
    for ns,threshold,recommended in [(0,126,128),(100,151,160),(200,176,192),(300,201,224)]:
        for o in sorted({threshold-1,threshold,recommended}):
            cases.append((f'host_ready_{ns}ns_O{o}',MultiportConfig(
                requests=128,scenario='ready',outstanding=o,
                host_decision_us=ns/1000,record_trace=False)))
    # Predict 10us before each request; feed an actual 64GB/s request stream.
    for ns in [0,100,200,300]:
        cases.append((f'ahead_stream_{ns}ns',MultiportConfig(
            requests=512,scenario='ready',period_us=65536/64000,
            early_lead_us=10,prefetch_decision_us=ns/1000,
            outstanding=128,record_trace=False)))
    # An insufficient lead exposes only residual NAND wait, not an automatic
    # addition of the whole decision delay to every burst's lookup latency.
    nand_us=.1+2.08+16384/2400+.05+.2
    for ns in [0,100,200,300]:
        cases.append((f'ahead_short_lead_{ns}ns',MultiportConfig(
            requests=512,scenario='ready',period_us=65536/64000,
            early_lead_us=nand_us-.5,prefetch_decision_us=ns/1000,
            outstanding=128,record_trace=False)))
    # No prefetch: saturated NAND reference, and an optional decision stage
    # that remains in the host path even when speculative reads are disabled.
    for ns in [0,100,200,300]:
        cases.append((f'cold_host_{ns}ns',MultiportConfig(
            requests=512,scenario='none',outstanding=2560,
            host_decision_us=ns/1000,record_trace=False)))
    # An 8MiB observation has finite-window variation at the estimated bound.
    for ns,o in [(100,152),(300,202)]:
        cases.append((f'host_ready_{ns}ns_O{o}',MultiportConfig(
            requests=128,scenario='ready',outstanding=o,
            host_decision_us=ns/1000,record_trace=False)))
    rows=[];start=time.monotonic()
    configs={}
    for label,c in cases:
        sim=MultiportSimulator(c);m,_=sim.run();configs[label]=asdict(c)
        row=dict(case=label,scenario=c.scenario,requests=c.requests,
                 transfer_mib=c.requests*c.request_bytes/1048576,
                 period_us=c.period_us,early_lead_us=c.early_lead_us,
                 prefetch_decision_ns=c.prefetch_decision_us*1000,
                 host_decision_ns=c.host_decision_us*1000,
                 outstanding_per_port=c.outstanding,outstanding_total=c.outstanding*c.host_ports,
                 full_gbps=m['throughput_gbps'],tail_gbps=m['tail_throughput_gbps'],
                 ready_hit_at_ar=m['ready_hit_at_ar'],ready_hit_at_lookup=m['ready_hit_at_lookup'],
                 mean_burst_latency_us=m['mean_burst_latency_us'],
                 mean_ar_to_lookup_done_us=m['mean_ar_to_lookup_done_us'],
                 buffer_peak_bytes=m['buffer_peak_bytes'])
        rows.append(row)
        print(f'{len(rows)}/{len(cases)} {label}: full={row["full_gbps"]:.4f}, '
              f'tail={row["tail_gbps"]:.4f} GB/s ({time.monotonic()-start:.1f}s)',flush=True)
        del sim
    with (OUT/'sweep.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (OUT/'configs.json').write_text(json.dumps(configs,indent=2)+'\n')
    sources=['axi_burst_sim.py','multiport_sim.py','test_prefetch_decision.py',
             'experiments/run_prefetch_decision.py']
    manifest=dict(target_aggregate_gbps=64,host_ports=4,burst_bytes=64,
                  lookup_clock_mhz=500,lookup_us=.5,lookup_slots_per_port=500,
                  lookup_pipelines_per_port=2,cases=len(rows),tests=50,
                  runtime_seconds=time.monotonic()-start,
                  source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
                  semantics='Decision delays are independent, fixed and fully pipelined. Ahead delay postpones speculative page issue; demand misses may issue first. Host delay holds AXI outstanding before lookup, but not lookup slots. They represent alternative placements; do not count the same decision twice. Host delay also applies with prefetch disabled when explicitly configured. Stream cases offer 64GB/s; their measured throughput is not saturated capacity. Tail is the aggregate common window after half the bursts complete. No decision unit bandwidth, resource cap, prediction accuracy or power is calibrated.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
