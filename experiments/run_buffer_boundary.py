"""Buffer boundary confirmation at the same 512-request saturated workload."""
import csv,json,time,hashlib,sys
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from deep_prefetch_sim import DeepConfig,DeepSimulator
OUT=ROOT/'results/deep_prefetch'
rows=[r for r in csv.DictReader((OUT/'sweep.csv').open()) if not r['case'].startswith('buffer_')]
configs=[r for r in json.loads((OUT/'configs.json').read_text()) if not r['case'].startswith('buffer_')]
print('Estimated ~80s: three buffer cases (~19s each) plus two allocation checks (~8-14s)',flush=True)
conditions=[(f'buffer_{mib}MiB',DeepConfig(requests=512,record_trace=False,outstanding=10000,buffer_bytes=int(mib*1048576)),'buffer_boundary') for mib in (2,2.25,2.5)]
for mode,o in [('demand',10000),('online',128)]:
 conditions.append((f'buffer_allocation64_{mode}',DeepConfig(requests=512,record_trace=False,outstanding=o,buffer_bytes=2*1048576,total_descriptors=2008,period_us=1.024,mode=mode),'same_total'))
for label,c,comparison in conditions:
 t=time.monotonic();m,_=DeepSimulator(c).run()
 rows.append(dict(case=label,comparison=comparison,mode=c.mode,requests=c.requests,outstanding=c.outstanding,period_us=c.period_us,buffer_budget_bytes=c.buffer_bytes,total_descriptors=c.total_descriptors,accuracy=c.accuracy,lead_us=c.lead_us,prefetch_limit=c.prefetch_limit,throttle=c.throttle,runtime_s=time.monotonic()-t,**{k:v for k,v in m.items() if not isinstance(v,list)}))
 configs.append(dict(case=label,legacy=False,config=asdict(c)));print(label,m['middle_gbps'],m['late_gbps'],flush=True)
with (OUT/'sweep.csv').open('w',newline='') as f:
 fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
(OUT/'configs.json').write_text(json.dumps(configs,indent=2))
manifest=json.loads((OUT/'manifest.json').read_text());manifest['cases']=len(rows);manifest['runtime_s']=sum(float(r['runtime_s']) for r in rows)
p='experiments/run_buffer_boundary.py';manifest['source_sha256'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
