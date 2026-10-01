"""Generate the GUI's simulation grid (standard library only)."""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from axi_burst_sim import Config, Simulator

LOOKUPS = sorted({i / 4 for i in range(41)} | {0.768})

def simulate(case):
    scenario, mapping, channels, outstanding, lookup = case
    c = Config(requests=32, scenario=scenario, mapping=mapping,
               channels=channels, outstanding=outstanding, lookup_us=lookup)
    s = Simulator(c)
    m, _ = s.run()
    t0 = c.first_demand_us
    lanes = []
    for i in [0, 1, 2, 3, 4, 5, 6, 7, 16, 17]:
        b, p = s.bursts[i], s.pages[i // 4]
        lanes.append([i, *[round(t - t0, 6) for t in
            [b['ar'], b['ar'] + lookup, max(b['ar'] + lookup, p['ready']),
             b['r_start'], b['rlast']]]])
    return key(case), {'tp': round(m['throughput_gbps'], 4),
        'burst': round(m['mean_burst_latency_us'], 4),
        'req': round(m['mean_request_latency_us'], 4),
        'hit': round(m['ready_hit_at_ar'] * 100, 2),
        'hol': round(m['hol_idle_us'], 4), 'peak': m['buffer_peak_bytes'],
        'lanes': lanes}

def key(case):
    scenario, mapping, _, outstanding, lookup = case
    return f'{scenario}|{mapping}|{outstanding}|{lookup:g}'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--reuse-existing', action='store_true',
                        help='Reuse data.json only when model/configuration are unchanged')
    args = parser.parse_args()
    path = Path(__file__).with_name('data.json')
    cases = [(s, m, ch, o, l) for s in ['ready', 'none', 'late', 'mixed']
             for m, ch in [('striped', 4), ('single', 1)]
             for o in range(1, 65) for l in LOOKUPS]
    existing = json.loads(path.read_text()) if args.reuse_existing and path.exists() else {}
    out = {key(c): existing[key(c)] for c in cases if key(c) in existing}
    pending = [c for c in cases if key(c) not in out]
    print(f'{len(out)} reused; {len(pending)} simulations to run', flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (k, value) in enumerate(pool.map(simulate, pending, chunksize=16), 1):
            out[k] = value
            if i % 1024 == 0:
                print(f'{i}/{len(pending)} new simulations complete', flush=True)
    path.write_text(json.dumps({key(c): out[key(c)] for c in cases}, separators=(',', ':')))
    print(f'{len(out)} combinations saved', flush=True)

if __name__ == '__main__':
    main()
