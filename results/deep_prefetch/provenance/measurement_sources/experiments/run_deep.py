"""Reproduce first, then estimate and run bounded staged sweeps."""
import sys,csv,json,time,hashlib,os
from pathlib import Path
from dataclasses import asdict,replace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from multiport_sim import MultiportConfig,MultiportSimulator
from deep_prefetch_sim import DeepConfig,DeepSimulator
OUT=ROOT/'results/deep_prefetch';OUT.mkdir(parents=True,exist_ok=True)
rows=[];configs=[];start=time.monotonic()
if os.environ.get('NAND_RESUME')=='1' and (OUT/'sweep.csv').exists():
 rows=list(csv.DictReader((OUT/'sweep.csv').open()));configs=json.loads((OUT/'configs.json').read_text())
def run(label,c,legacy=False,comparison='same_host'):
 c=replace(c,lead_us=10000) if not legacy and c.mode=='ready' else c
 if any(r['case']==label for r in rows):return
 t=time.monotonic();s=(MultiportSimulator if legacy else DeepSimulator)(c);m,req=s.run()
 row=dict(case=label,comparison=comparison,mode=c.scenario if legacy else c.mode,requests=c.requests,outstanding=c.outstanding,period_us=c.period_us,buffer_budget_bytes=c.buffer_bytes,total_descriptors=getattr(c,'total_descriptors',None),accuracy=getattr(c,'accuracy',1),lead_us=getattr(c,'lead_us',0),prefetch_limit=getattr(c,'prefetch_limit',0),throttle=getattr(c,'throttle',False),runtime_s=time.monotonic()-t,**{k:v for k,v in m.items() if not isinstance(v,list)})
 rows.append(row);configs.append(dict(case=label,legacy=legacy,config=asdict(c)))
 with (OUT/'sweep.csv').open('w',newline='') as f:
  fields=list(dict.fromkeys(k for r in rows for k in r));w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
 (OUT/'configs.json').write_text(json.dumps(configs,indent=2))
 print(label,round(row['runtime_s'],2),round(m['throughput_gbps'],3),round(m['tail_throughput_gbps'],3),flush=True)
for o in (502,10000):
 for mode in ('none','ready'):run(f'legacy_{mode}_{o}',MultiportConfig(requests=128,outstanding=o,scenario=mode,record_trace=False),True,'legacy')
# 36 host-window comparisons + 8 accuracy/lead/issue sensitivity + 6
# equal budget comparisons + 4 longer confirmation runs = 54 new runs.
mean=sum(float(r['runtime_s']) for r in rows[:4])/4
estimate=dict(measured_legacy_seconds=mean,new_cases=78,request_equivalent_cases_128=67,estimated_seconds=mean*67,method='linear requests scaling from four 128-request legacy runs; online queue overhead can increase runtime')
(OUT/'estimate.json').write_text(json.dumps(estimate,indent=2));print('ESTIMATE',estimate,flush=True)
base=DeepConfig(requests=64,record_trace=False)
for period in (0,1.024):
 for o in (128,502,2000,4000,6000,8000,10000):
  for mode,throttle in [('demand',False),('ready',False),('online',False),('online',True)]:
   run(f'host_{period}_{o}_{mode}_{throttle}',replace(base,period_us=period,outstanding=o,mode=mode,throttle=throttle))
for accuracy in (.5,.9):
 for lead in (2,10):
  for limit in (32,128):run(f'sensitivity_{accuracy}_{lead}_{limit}',replace(base,mode='online',period_us=1.024,accuracy=accuracy,lead_us=lead,prefetch_limit=limit,outstanding=502))
for budget in (2008,40000):
 for mode in ('demand','ready','online'):
  run(f'budget_{budget}_{mode}',replace(base,mode=mode,total_descriptors=budget,outstanding=10000,buffer_bytes=2*1024*1024),comparison='same_total')
for o in (502,10000):
 for mode in ('demand','online'):
  run(f'long_{o}_{mode}',replace(base,requests=512,mode=mode,outstanding=o))
for o in (502,10000):
 for mode in ('demand','online'):
  run(f'long64_{o}_{mode}',replace(base,requests=512,mode=mode,outstanding=o,period_us=1.024))
manifest=dict(baseline_commit='bf63379b7587b63e01925730f123f37a1ec33bdf',cases=len(rows),runtime_s=sum(float(r['runtime_s']) for r in rows),source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('deep_prefetch_sim.py','multiport_sim.py','axi_burst_sim.py','test_deep_prefetch.py','experiments/run_deep.py')})
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
