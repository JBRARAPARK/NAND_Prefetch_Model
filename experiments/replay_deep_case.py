"""Replay one measured config, optionally retaining a detailed event trace."""
import argparse,csv,json,sys
from pathlib import Path
from dataclasses import asdict,replace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from deep_prefetch_sim import DeepConfig,DeepSimulator
from multiport_sim import MultiportConfig,MultiportSimulator
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',required=True)
p.add_argument('--configs',type=Path,default=ROOT/'results/deep_prefetch/configs.json')
p.add_argument('--out',type=Path,required=True);p.add_argument('--trace',action='store_true');a=p.parse_args()
cases=json.loads(a.configs.read_text());entry=next((e for e in cases if e['case']==a.case),None)
if entry is None:p.error('case not present in configs.json')
c=(MultiportConfig if entry['legacy'] else DeepConfig)(**entry['config']);c=replace(c,record_trace=a.trace)
s=(MultiportSimulator if entry['legacy'] else DeepSimulator)(c);metrics,requests=s.run();a.out.mkdir(parents=True,exist_ok=True)
for filename,data in [('config.json',asdict(c)),('summary.json',metrics)]:
 (a.out/filename).write_text(json.dumps(data,indent=2)+'\n')
for filename,rows in [('requests.csv',requests),('events.csv',s.trace)]:
 if rows:
  with (a.out/filename).open('w',newline='') as f:
   w=csv.DictWriter(f,list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
print(json.dumps(metrics,indent=2))
