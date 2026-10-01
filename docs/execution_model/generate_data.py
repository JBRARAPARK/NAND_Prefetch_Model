import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from axi_burst_sim import Config,Simulator
out={}
for scenario in ['ready','none','late','mixed']:
 for mapping,channels in [('striped',4),('single',1)]:
  for o in [1,2,4,8,16,32,64]:
   for l in [0,.5,.768,1,3,5,10]:
    c=Config(requests=32,scenario=scenario,mapping=mapping,channels=channels,outstanding=o,lookup_us=l)
    s=Simulator(c);m,_=s.run();t0=c.first_demand_us
    ids=[0,1,2,3,4,5,6,7,16,17]
    a=[]
    for i in ids:
     b=s.bursts[i];p=s.pages[i//4]
     a.append([i,round(b['ar']-t0,6),round(b['ar']+l-t0,6),round(max(b['ar']+l,p['ready'])-t0,6),round(b['r_start']-t0,6),round(b['rlast']-t0,6)])
    out[f'{scenario}|{mapping}|{o}|{l:g}']={'tp':round(m['throughput_gbps'],4),'burst':round(m['mean_burst_latency_us'],4),'req':round(m['mean_request_latency_us'],4),'hit':round(m['ready_hit_at_ar']*100,2),'hol':round(m['hol_idle_us'],4),'peak':m['buffer_peak_bytes'],'lanes':a}
Path(__file__).with_name('data.json').write_text(json.dumps(out,separators=(',',':')))
print(len(out),Path(__file__).with_name('data.json').stat().st_size)
