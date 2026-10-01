import sys,csv,json,hashlib,platform,time
from pathlib import Path
from dataclasses import replace,asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from axi_burst_sim import Config,Simulator

def write(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 out=Path(__file__).resolve().parents[1]/'results/axi_tr3';out.mkdir(parents=True,exist_ok=True)
 base=Config(requests=32);rows=[];start=time.time()
 for mapping,channels in [('single',1),('striped',4)]:
  for period in [0.,100.]:
   for scenario in ['none','ready','late','mixed']:
    for delay in [0.,.5,1.,2.,3.,5.,10.]:
     for outstanding in [1,2,4,8,16,32,64]:
      c=replace(base,mapping=mapping,channels=channels,period_us=period,scenario=scenario,lookup_us=delay,outstanding=outstanding)
      s=Simulator(c);m,r=s.run();rows.append(dict(mapping=mapping,channels=channels,period_us=period,scenario=scenario,lookup_us=delay,outstanding=outstanding,**m))
      if mapping=='striped' and period==0 and scenario=='mixed' and delay==3 and outstanding==16:
       keys=list(dict.fromkeys(k for x in s.trace for k in x))
       with (out/'example_events.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(s.trace)
       write(out/'example_requests.csv',r)
    print(f'{mapping} period={period:g} scenario={scenario}: {len(rows)} cases',flush=True)
 write(out/'sweep.csv',rows)
 (out/'manifest.json').write_text(json.dumps(dict(config=asdict(base),cases=len(rows),requests_per_case=32,python=platform.python_version(),runtime_seconds=time.time()-start,source_sha256=hashlib.sha256((out.parents[1]/'axi_burst_sim.py').read_bytes()).hexdigest()),indent=2))
 print(f'Completed {len(rows)} cases in {time.time()-start:.1f}s',flush=True)
if __name__=='__main__':main()
