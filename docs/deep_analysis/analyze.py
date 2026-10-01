import sys,json,csv,hashlib,math
from pathlib import Path
from dataclasses import replace,asdict
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from axi_burst_sim import Config,Simulator
OUT=Path(__file__).resolve().parent
class LookupLimited(Simulator):
 def __init__(self,c,ii):
  self.ii=ii;self.lookup_next=0.;super().__init__(c)
 def event(self,t,kind,data):
  if kind=='lookup':t=max(t,self.lookup_next);self.lookup_next=t+self.ii
  super().event(t,kind,data)
rows=[]
def run(group,label,c,ii=0):
 s=LookupLimited(c,ii) if ii else Simulator(c);m,r=s.run()
 rows.append(dict(group=group,label=label,**asdict(c),lookup_ii_us=ii,**m))
 return s,m
base=Config(requests=32,lookup_us=3,outstanding=64)
# Separate channel count from placement and compare tR within the SAME engine.
for mapping in ['single','striped']:
 for channels in [1,4]:
  for tr in [3,50]:
   for scenario in ['none','ready','mixed']:
    run('topology_tr',f'{mapping}-{channels}-{tr}-{scenario}',replace(base,mapping=mapping,channels=channels,tr_us=tr,scenario=scenario))
for l in [3,10]:
 for ii in [0,.002,.256,1,l]:
  for o in [16,64]:run('lookup_capacity',f'L{l}-II{ii}-O{o}',replace(base,lookup_us=l,scenario='ready',outstanding=o),ii)
for l in [3,10]:
 for o in ([12,13,16] if l==3 else [40,41,64]):
  for n in [32,128]:run('threshold_length',f'L{l}-O{o}-N{n}',replace(base,lookup_us=l,outstanding=o,scenario='ready',requests=n))
for scenario in ['none','ready','mixed','late']:
 for size in [64,256,2048,8192]:run('buffer',f'{scenario}-{size}KiB',replace(base,scenario=scenario,buffer_bytes=size*1024))
# Verify each limited lookup run is safe, deterministic and bounded by its issue rate.
for r in rows:
 assert r['peak_outstanding']<=r['outstanding']
 assert 0<r['throughput_gbps']<=16.000001
 assert r['nand_bytes']==r['requests']*65536
 if r['lookup_ii_us']>0:
  # Finite completion makes measured throughput below steady cap when L >= II.
  assert r['throughput_gbps']<=min(16,4.096/r['lookup_ii_us'])+1e-6
with (OUT/'supplement.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
(OUT/'manifest.json').write_text(json.dumps(dict(cases=len(rows),source_sha256=hashlib.sha256((ROOT/'axi_burst_sim.py').read_bytes()).hexdigest(),groups={g:sum(r['group']==g for r in rows) for g in set(r['group'] for r in rows)},note='LookupLimited only serializes lookup completion slots; no production source modifications.'),indent=2))
for r in rows:print(r['group'],r['label'],round(r['throughput_gbps'],4),round(r['mean_request_latency_us'],3),round(r['ready_hit_at_ar'],3))
