"""Discrete-event NAND read model. Time unit: microsecond; sizes: bytes.

Architectural model, not an AXI pin-level or NAND product model.
"""
from dataclasses import dataclass, asdict, replace
import heapq, random, json, argparse, csv, math
from pathlib import Path

@dataclass
class Config:
    request_bytes: int = 65536
    page_bytes: int = 16384
    chips: int = 4
    banks_per_chip: int = 1
    planes_per_bank: int = 6
    channels: int = 1
    mapping: str = 'single'
    chips_per_request: int = 4
    stripe_bytes: int = 16384
    plane_parallel: bool = True
    page_buffers_per_plane: int = 1
    cache_read: bool = False
    tr_us: float = 50.0
    tr_cv: float = 0.0
    die_tr_factors: tuple = (1.0, 1.0, 1.0, 1.0)
    estimate_tr_us: float = 50.0
    command_us: float = 0.1
    nand_io_gbps: float = 2.4
    turnaround_us: float = 0.05
    ecc_us: float = 0.2
    retry_probability: float = 0.0
    retry_us: float = 50.0
    buffer_bytes: int = 262144
    policy: str = 'none'
    lead_us: float = 60.0
    target_known_delay_us: float = 0.0
    mapping_delay_us: float = 0.0
    hit_lookup_delay_us: float = 0.0
    accuracy: float = 1.0
    speculative: bool = False
    host_qd: int = 1
    requests: int = 100
    period_us: float = 100.0
    first_demand_us: float = 500.0
    hint_horizon_us: float = 300.0
    axi_width_bits: int = 256
    axi_clock_mhz: float = 500.0
    axi_max_beats: int = 128
    axi_ready_fraction: float = 1.0
    completion_mode: str = 'partial'
    compute_chunk_us: float = 2.0
    seed: int = 7

    def validate(self):
        assert self.request_bytes % self.page_bytes == 0
        assert self.stripe_bytes % self.page_bytes == 0
        assert self.chips >= self.chips_per_request > 0
        assert self.channels > 0 and self.banks_per_chip > 0
        assert self.planes_per_bank > 0 and self.page_buffers_per_plane > 0
        assert self.buffer_bytes >= self.request_bytes, 'full request capacity required for deadlock-free baseline'
        assert self.host_qd > 0 and self.requests > 0
        assert 0 < self.axi_ready_fraction <= 1
        assert self.axi_max_beats * self.axi_width_bits // 8 <= 4096
        assert self.policy in ('none', 'fixed', 'adaptive')
        assert self.mapping in ('single', 'striped', 'mixed')
        assert self.completion_mode in ('partial', 'full')
        assert self.nand_io_gbps > 0 and self.axi_clock_mhz > 0
        assert 0 <= self.accuracy <= 1 and 0 <= self.retry_probability <= 1
        for name in ('lead_us','target_known_delay_us','mapping_delay_us','hit_lookup_delay_us','tr_us','command_us','ecc_us','turnaround_us','period_us'):
            assert getattr(self,name) >= 0, name

class Simulator:
    def __init__(self, c):
        c.validate(); self.c = c; self.now = 0.; self.events = []; self.serial = 0
        self.rng = random.Random(c.seed); self.tasks = {}; self.reqs = []
        self.used = 0; self.peak = 0; self.area = 0.; self.last_occ = 0.
        self.occupancy = []; self.trace = []; self.active = 0; self.next_return = 0
        self.axi_busy = False; self.nand_bytes = 0; self.wasted_bytes = 0
        self.plane_busy = set(); self.pb = {}; self.cmd_busy = set(); self.io_busy = set()
        self.sense_time = 0.; self.io_time = 0.; self.chunks = c.request_bytes // c.page_bytes
        for i in range(c.requests):
            demand = c.first_demand_us + i*c.period_us
            t0 = demand - c.hint_horizon_us
            known = t0+c.target_known_delay_us
            correct = (self.rng.random() < c.accuracy) if c.speculative else True
            target = i*2; candidate = target if correct else target+1
            # Ground truth is workload-private until known; policy receives candidate only.
            r = dict(id=i,target=target,candidate=candidate,demand=demand,t0=t0,
                     known=known,map_ready=known+c.mapping_delay_us,correct=correct,
                     accepted=None,lookup=None,lookup_complete=False,returned=[],compute_end=0.,hit='miss')
            self.reqs.append(r)
            self.event(demand,'demand',i)
            self.event(known,'known',i)
            if c.policy != 'none':
                pages = self.placement(candidate)
                for k,place in enumerate(pages):
                    if c.policy == 'fixed': desired = demand-c.lead_us
                    else:
                        # Estimate completion including serialized pages on each channel.
                        same_channel = sum(1 for prev in pages[:k+1] if prev[3]==place[3])
                        same_plane = sum(1 for prev in pages[:k] if prev[:3]==place[:3])
                        desired = demand-(same_plane+1)*c.estimate_tr_us-c.command_us-c.ecc_us-same_channel*(c.page_bytes/(c.nand_io_gbps*1000)+c.turnaround_us)
                    earliest = t0+c.mapping_delay_us if c.speculative else r['map_ready']
                    self.event(max(0.,desired,earliest),'prefetch',(i,k,candidate))

    def placement(self, addr):
        c=self.c; start=(addr//2)%c.chips; out=[]
        for k in range(self.chunks):
            stripe=k*c.page_bytes//c.stripe_bytes
            if c.mapping=='single': chip=start
            elif c.mapping=='striped': chip=(start+stripe%c.chips_per_request)%c.chips
            else: chip=random.Random(c.seed+addr*7919+k).randrange(c.chips)
            local=sum(1 for x in out if x[0]==chip)
            bank=(local//c.planes_per_bank)%c.banks_per_chip
            plane=local%c.planes_per_bank if c.plane_parallel else 0
            out.append((chip,bank,plane,chip%c.channels))
        return out

    def event(self,t,kind,data):
        self.serial+=1; heapq.heappush(self.events,(t,self.serial,kind,data))

    def record(self,kind,task=None,**extra):
        row=dict(time_us=self.now,event=kind)
        if task: row.update(request=task['request'],address=task['address'],chunk=task['chunk'],chip=task['place'][0],bank=task['place'][1],plane=task['place'][2],channel=task['place'][3])
        row.update(extra); self.trace.append(row)

    def occupy(self,delta):
        self.area+=self.used*(self.now-self.last_occ); self.last_occ=self.now
        self.used+=delta; assert 0<=self.used<=self.c.buffer_bytes
        self.peak=max(self.peak,self.used); self.occupancy.append((self.now,self.used))

    def task(self,i,k,addr,prefetch):
        key=(addr,k)
        if key not in self.tasks:
            self.tasks[key]=dict(key=key,request=i,address=addr,chunk=k,place=self.placement(addr)[k],
                                 state='queued',prefetch=prefetch,needed=not prefetch,discard=False,reserved=False)
        elif not prefetch: self.tasks[key]['needed']=True
        return self.tasks[key]

    def dispatch(self):
        c=self.c
        # Head request receives buffer credit before speculative or later demand work.
        ordered=sorted(self.tasks.values(),key=lambda t:(0 if t['needed'] else 1,t['request'],t['chunk']))
        for t in ordered:
            if t['state']!='queued' or t['discard']: continue
            # Never reserve credits for later demands while the head needs missing chunks.
            head=self.reqs[self.next_return] if self.next_return<len(self.reqs) else None
            if head and t['request']!=self.next_return:
                missing=sum(1 for k in range(self.chunks) if not self.tasks.get((head['target'],k),{}).get('reserved',False) and k>=len(head['returned']))
                if self.used+c.page_bytes+missing*c.page_bytes>c.buffer_bytes: continue
            chip,bank,plane,ch=t['place']; p=(chip,bank,plane); b=(chip,bank)
            if p in self.plane_busy or b in self.cmd_busy: continue
            if self.pb.get(p,0)>=c.page_buffers_per_plane or self.used+c.page_bytes>c.buffer_bytes: continue
            self.occupy(c.page_bytes); t['reserved']=True; t['state']='command';t['issue']=self.now
            self.pb[p]=self.pb.get(p,0)+1; self.plane_busy.add(p); self.cmd_busy.add(b)
            self.record('issue',t);self.event(self.now+c.command_us,'sense_start',t['key'])

    def transfer(self):
        c=self.c
        for t in sorted(self.tasks.values(),key=lambda t:(not t['needed'],t['request'],t['chunk'])):
            ch=t['place'][3]
            if t['state']!='sensed' or ch in self.io_busy: continue
            self.io_busy.add(ch); t['state']='transfer'; dur=c.page_bytes/(c.nand_io_gbps*1000)+c.turnaround_us
            self.io_time+=dur;self.record('transfer',t);self.event(self.now+dur,'transfer_done',t['key'])

    def release(self,t):
        if t['reserved']: self.occupy(-self.c.page_bytes);t['reserved']=False

    def returns(self):
        if self.axi_busy or self.next_return>=len(self.reqs): return
        c=self.c;r=self.reqs[self.next_return]
        if not r['lookup_complete']: return
        k=len(r['returned']);t=self.tasks.get((r['target'],k))
        if not t or t['state']!='ready': return
        if c.completion_mode=='full' and k==0 and any(self.tasks.get((r['target'],j),{}).get('state')!='ready' for j in range(self.chunks)): return
        self.axi_busy=True;t['state']='returning'
        bytes_per_beat=c.axi_width_bits//8; beats=math.ceil(c.page_bytes/bytes_per_beat)
        bursts=math.ceil(beats/c.axi_max_beats)
        # Sequential bursts with one address-cycle overhead; no interleaving.
        dur=(beats/c.axi_ready_fraction+bursts)/c.axi_clock_mhz
        self.record('axi_start',t,bursts=bursts); self.event(self.now+dur,'return_done',t['key'])

    def run(self):
        c=self.c
        while self.events:
            self.now,_,kind,data=heapq.heappop(self.events)
            if kind=='known':
                r=self.reqs[data]; self.record('target_known',request=data)
                for t in self.tasks.values():
                    if t['request']==data and t['address']!=r['target']:
                        t['discard']=True
                        if t['state']=='ready':
                            self.wasted_bytes+=c.page_bytes;t['waste_counted']=True
                            self.release(t);t['state']='discarded'
                        elif t['state']=='queued': t['state']='cancelled'
            elif kind=='prefetch':
                i,k,addr=data;r=self.reqs[i]
                if self.now<r['known'] or addr==r['target']: self.task(i,k,addr,True)
            elif kind=='demand':
                r=self.reqs[data]
                # Ordered acceptance, bounded host demand QD. Retry on retirement/target event.
                self.accept_demands()
            elif kind=='lookup':
                r=self.reqs[data]; states=[self.tasks.get((r['target'],k),{}).get('state') for k in range(self.chunks)]
                r['lookup_complete']=True
                r['hit']='ready' if all(s=='ready' for s in states) else ('late' if any(s in ('queued','command','sense','sensed','transfer','ecc','ready') for s in states) else 'miss')
                self.record('lookup',request=data,hit=r['hit'])
                for k in range(self.chunks): self.task(data,k,r['target'],False)
            elif kind=='sense_start':
                t=self.tasks[data]; self.cmd_busy.remove(t['place'][:2]);t['state']='sense'
                factor=c.die_tr_factors[t['place'][0]%len(c.die_tr_factors)]
                # Counter-based per-page random stream: policies see identical media samples.
                rng=random.Random(c.seed+t['address']*104729+t['chunk']*997)
                tr=c.tr_us*factor*max(.01,1+rng.gauss(0,c.tr_cv))
                if rng.random()<c.retry_probability: tr+=c.retry_us
                self.sense_time+=tr;self.event(self.now+tr,'sensed',data)
            elif kind=='sensed':
                t=self.tasks[data];t['state']='sensed';self.record('sensed',t)
                if c.cache_read: self.plane_busy.remove(t['place'][:3])
            elif kind=='transfer_done':
                t=self.tasks[data];self.io_busy.remove(t['place'][3]);p=t['place'][:3]
                self.pb[p]-=1
                if not c.cache_read: self.plane_busy.remove(p)
                t['state']='ecc';self.nand_bytes+=c.page_bytes
                if t['discard']: self.wasted_bytes+=c.page_bytes;t['waste_counted']=True
                self.event(self.now+c.ecc_us,'ready',data)
            elif kind=='ready':
                t=self.tasks[data];t['state']='ready';t['ready']=self.now;self.record('ready',t)
                if t['discard']:
                    if not t.get('waste_counted'): self.wasted_bytes+=c.page_bytes;t['waste_counted']=True
                    self.release(t);t['state']='discarded'
            elif kind=='return_done':
                t=self.tasks[data];r=self.reqs[t['request']]
                assert t['request']==self.next_return and t['chunk']==len(r['returned'])
                self.axi_busy=False;t['state']='returned';r['returned'].append(self.now)
                r['compute_end']=max(r['compute_end'],self.now)+c.compute_chunk_us
                self.release(t);self.record('axi_done',t)
                if len(r['returned'])==self.chunks:self.next_return+=1;self.active-=1
            self.accept_demands();self.transfer();self.dispatch();self.returns()
        assert self.next_return==c.requests, f'deadlock: completed {self.next_return}/{c.requests}'
        rows=[]
        for r in self.reqs:
            rows.append(dict(request=r['id'],demand_us=r['demand'],accepted_us=r['accepted'],
                             first_usable_us=r['returned'][0],full_us=r['returned'][-1],
                             first_stall_us=r['returned'][0]-r['demand'],full_stall_us=r['returned'][-1]-r['demand'],
                             compute_finish_us=r['compute_end'],hit=r['hit'],prediction_hit=r['correct'] if c.speculative and c.policy!='none' else None))
        stalls=sorted(r['full_stall_us'] for r in rows)
        horizon=self.now
        self.area+=self.used*(self.now-self.last_occ)
        metrics=dict(mean_full_stall_us=sum(stalls)/len(stalls),p95_full_stall_us=stalls[math.ceil(.95*len(stalls))-1],
                     p99_full_stall_us=stalls[math.ceil(.99*len(stalls))-1],
                     mean_first_stall_us=sum(r['first_stall_us'] for r in rows)/len(rows),
                     buffer_peak_bytes=self.peak,buffer_mean_bytes=self.area/horizon,
                     nand_bytes=self.nand_bytes,wasted_bytes=self.wasted_bytes,
                     ready_hit_rate=sum(r['hit']=='ready' for r in rows)/len(rows),
                     late_hit_rate=sum(r['hit']=='late' for r in rows)/len(rows),
                     io_utilization=self.io_time/(horizon*c.channels),
                     sensing_utilization=self.sense_time/(horizon*c.chips*c.banks_per_chip*(c.planes_per_bank if c.plane_parallel else 1)))
        return metrics, rows

    def accept_demands(self):
        for r in self.reqs:
            if r['accepted'] is not None: continue
            if r['demand']>self.now or self.active>=self.c.host_qd: break
            r['accepted']=self.now;self.active+=1
            r['lookup']=max(self.now,r['map_ready'])+self.c.hit_lookup_delay_us
            self.event(r['lookup'],'lookup',r['id'])

def write_csv(path,rows):
    with open(path,'w',newline='') as f:
        keys=list(dict.fromkeys(k for r in rows for k in r))
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config');ap.add_argument('--out',default='results');ap.add_argument('--sweep',action='store_true');a=ap.parse_args()
    c=Config(**json.loads(Path(a.config).read_text())) if a.config else Config()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    if not a.sweep:
        s=Simulator(c);m,rows=s.run();write_csv(out/'requests.csv',rows);write_csv(out/'events.csv',s.trace)
        (out/'summary.json').write_text(json.dumps(dict(config=asdict(c),metrics=m),indent=2));print(json.dumps(m,indent=2));return
    rows=[]
    for mapping in ['single','striped']:
        for channels in [1,4]:
            for policy in ['none','fixed','adaptive']:
                for delay in [0.,200.,250.,280.,300.]:
                    for lead in ([0.] if policy!='fixed' else [0.,20.,40.,60.,80.,120.]):
                        cc=replace(c,mapping=mapping,channels=channels,policy=policy,target_known_delay_us=delay,lead_us=lead)
                        s=Simulator(cc);m,_=s.run();rows.append(dict(mapping=mapping,channels=channels,policy=policy,delay_us=delay,lead_us=lead,**m))
    write_csv(out/'sweep.csv',rows)
    (out/'baseline.json').write_text(json.dumps(asdict(c),indent=2))
    print(f'{len(rows)} scenarios saved to {out}')

if __name__=='__main__': main()
