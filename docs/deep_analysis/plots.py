from pathlib import Path
import sys,csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from axi_burst_sim import Config,Simulator
D=Path(__file__).resolve().parent
r=list(csv.DictReader((ROOT/'results/axi_tr3/sweep.csv').open()));s=list(csv.DictReader((D/'supplement.csv').open()))
plt.rcParams.update({'font.family':['AppleGothic','DejaVu Sans'],'font.size':10,'axes.unicode_minus':False})
def get(scen,l,n,period=0):return next(x for x in r if x['mapping']=='striped' and float(x['period_us'])==period and x['scenario']==scen and float(x['lookup_us'])==l and int(x['outstanding'])==n)
def save(fig,name):fig.tight_layout();fig.savefig(D/(name+'.png'),dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(7,3.2))
for l in [0,1,3,5,10]:
 ns=[1,2,4,8,16,32,64];ax.plot(ns,[float(get('ready',l,n)['throughput_gbps']) for n in ns],marker='o',label=f'조회 {l}µs')
ax.set(xscale='log',xticks=ns,xlabel='Burst outstanding 한도',ylabel='Demand 구간 처리량 (GB/s)');ax.get_xaxis().set_major_formatter(plt.ScalarFormatter());ax.grid(alpha=.2);ax.legend(ncol=2);save(fig,'window')
fig,ax=plt.subplots(figsize=(7,3.2))
for sc,label in [('none','모두 miss'),('ready','준비된 hit'),('mixed','hit 50%'),('late','1.5µs 전 발행')]:
 ns=[1,2,4,8,16,32,64];ax.plot(ns,[float(get(sc,3,n,100)['mean_request_latency_us']) for n in ns],marker='o',label=label)
ax.set(xscale='log',xticks=ns,xlabel='Burst outstanding 한도',ylabel='평균 64KiB 반환 지연 (µs)');ax.get_xaxis().set_major_formatter(plt.ScalarFormatter());ax.grid(alpha=.2);ax.legend();save(fig,'lightload')
fig,ax=plt.subplots(figsize=(7,3))
for o in [16,64]:
 a=[x for x in s if x['group']=='lookup_capacity' and float(x['lookup_us'])==3 and int(x['outstanding'])==o]
 ax.plot([float(x['lookup_ii_us']) for x in a],[float(x['throughput_gbps']) for x in a],marker='o',linestyle='--' if o==64 else '-',label=f'Outstanding {o}')
ax.set(xlabel='조회 시작 간격 II (µs)',ylabel='Demand 구간 처리량 (GB/s)');ax.grid(alpha=.2);ax.legend();save(fig,'lookup')
fig,ax=plt.subplots(figsize=(7,3.2))
for sc,label in [('none','모두 miss'),('ready','조기 prefetch'),('mixed','교대 prefetch'),('late','늦은 prefetch')]:
 a=[x for x in s if x['group']=='buffer' and x['scenario']==sc];ax.plot([int(x['buffer_bytes'])/1024 for x in a],[float(x['throughput_gbps']) for x in a],marker='o',label=label)
ax.set(xscale='log',xticks=[64,256,2048,8192],xlabel='버퍼 용량 (KiB)',ylabel='Demand 구간 처리량 (GB/s)');ax.get_xaxis().set_major_formatter(plt.ScalarFormatter());ax.grid(alpha=.2);ax.legend(ncol=2);save(fig,'buffer')
sm=Simulator(Config(requests=4,scenario='mixed',lookup_us=3,outstanding=64));sm.run()
fig,ax=plt.subplots(figsize=(7,3.4));ids=[0,4,8,12,16,20,24,28]
for y,bid in enumerate(ids):
 b=sm.bursts[bid];ar=b['ar']-20000;lookup=ar+3;ready=max(lookup,sm.pages[bid//4]['ready']-20000);start=b['r_start']-20000
 for a,z,col,lab in [(ar,lookup,'#9abdd9','조회'),(lookup,ready,'#e6b978','NAND 대기'),(ready,start,'#d08383','반환 순서 대기'),(start,b['rlast']-20000,'#327565','R 전송')]:
  if z>a:ax.barh(y,z-a,left=a,color=col,label=lab if y==0 else None)
ax.set(yticks=range(8),yticklabels=[f'Burst {b} '+('miss' if b<16 else 'hit') for b in ids],xlabel='첫 demand 이후 시간 (µs)');ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=c,label=l) for c,l in [('#9abdd9','조회'),('#e6b978','NAND 대기'),('#d08383','반환 순서 대기'),('#327565','R 전송')]],loc='upper center',bbox_to_anchor=(.5,1.18),ncol=4,fontsize=8)
save(fig,'timeline')
print('charts complete')
