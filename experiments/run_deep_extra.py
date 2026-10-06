"""Paired imperfect-predictor policy checks and extended boundary points."""
import sys,csv,json,time,hashlib
from pathlib import Path
from dataclasses import asdict
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from deep_prefetch_sim import DeepConfig,DeepSimulator
OUT=ROOT/'results/deep_prefetch';rows=list(csv.DictReader((OUT/'sweep.csv').open()));configs=json.loads((OUT/'configs.json').read_text())
# Idempotent supplemental stage.
rows=[r for r in rows if not r['case'].startswith('extra_')];configs=[r for r in configs if not r['case'].startswith('extra_')]
start=time.monotonic();conditions=[]
for a in (.5,.9):
 for lead in (2,10):
  for limit in (32,128):conditions.append((f'extra_policy_{a}_{lead}_{limit}',DeepConfig(requests=64,record_trace=False,mode='online',period_us=1.024,accuracy=a,lead_us=lead,prefetch_limit=limit,outstanding=502,throttle=True)))
for o in (6000,8000):conditions.append((f'extra_long_{o}',DeepConfig(requests=512,record_trace=False,outstanding=o)))
for budget in (2008,40000):
 for mode in ('demand','ready','online'):
  conditions.append((f'extra_budget64_{budget}_{mode}',DeepConfig(requests=64,record_trace=False,outstanding=10000,total_descriptors=budget,buffer_bytes=2*1024*1024,period_us=1.024,mode=mode,lead_us=10000 if mode=='ready' else 10)))
print('Supplement estimate: 16 cases, 15 equivalent 128-request runs; ~15 seconds legacy lower bound, online overhead adds cost',flush=True)
for label,c in conditions:
 t=time.monotonic();m,_=DeepSimulator(c).run()
 rows.append(dict(case=label,comparison='same_total' if 'budget64' in label else 'same_host',mode=c.mode,requests=c.requests,outstanding=c.outstanding,period_us=c.period_us,buffer_budget_bytes=c.buffer_bytes,total_descriptors=c.total_descriptors,accuracy=c.accuracy,lead_us=c.lead_us,prefetch_limit=c.prefetch_limit,throttle=c.throttle,runtime_s=time.monotonic()-t,**{k:v for k,v in m.items() if not isinstance(v,list)}))
 configs.append(dict(case=label,legacy=False,config=asdict(c)));print(label,m['late_gbps'],flush=True)
with (OUT/'sweep.csv').open('w',newline='') as f:
 fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
(OUT/'configs.json').write_text(json.dumps(configs,indent=2))
manifest=json.loads((OUT/'manifest.json').read_text());manifest['cases']=len(rows);manifest['runtime_s']+=time.monotonic()-start
for p in ('deep_prefetch_sim.py','experiments/run_deep_extra.py','test_deep_prefetch.py'):
 manifest['source_sha256'][p]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
