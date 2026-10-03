"""Independent AXI ports sharing NAND and buffer resources.

All burst IDs round-robin over ports. AR admission, lookup resources and ordered
R return are local to each port; a logical request completes after all its bursts.
Config.outstanding, lookup_slots and lookup_pipelines are PER PORT.
"""
from collections import deque
from dataclasses import dataclass, field
import heapq
import math

from axi_burst_sim import Config, Simulator


@dataclass(frozen=True)
class MultiportConfig(Config):
    host_ports: int = 4
    axi_width_bits: int = 512
    axi_clock_mhz: float = 1000.0
    burst_bytes: int = 64
    chips: int = 128
    channels: int = 128
    planes: int = 6
    mapping: str = 'global_striped'
    tr_us: float = 2.08
    lookup_clock_mhz: float | None = 500.0
    lookup_us: float = .5
    lookup_slots: int | None = 500
    lookup_pipelines: int = 2
    # 500ns service + up to 1ns lookup-edge wait + 1ns R return.
    outstanding: int = 502
    record_trace: bool = True


@dataclass
class Port:
    index: int
    next_bid: int
    lanes: list
    ar_queue: deque = field(default_factory=deque)
    returns: deque = field(default_factory=deque)
    lookup_queue: deque = field(default_factory=deque)
    active: int = 0
    peak: int = 0
    lookup_active: int = 0
    lookup_peak: int = 0
    queue_peak: int = 0
    ar_scheduled: bool = False
    wake_scheduled: bool = False
    r_busy: bool = False
    next_ar_time: float = 0.


class MultiportSimulator(Simulator):
    def __init__(self,c):
        if type(c.host_ports) is not int or c.host_ports<=0:
            raise ValueError('host_ports must be a positive integer')
        if type(c.record_trace) is not bool:raise ValueError('record_trace must be bool')
        if min(c.axi_clock_mhz,c.io_gbps)<=0:raise ValueError('positive clocks and bandwidth')
        super().__init__(c)
        self.ports=[Port(i,i,[(c.first_demand_us,j) for j in range(c.lookup_pipelines)])
                    for i in range(c.host_ports)]
        self.port_idle=[0.]*c.host_ports;self.port_hol_idle=[0.]*c.host_ports
        self.port_ready=[set() for _ in self.ports]
        self.channel_busy_us=[0.]*c.channels

    def log(self,event,**kw):
        if self.c.record_trace:super().log(event,**kw)

    def head_page(self):
        heads=[p.next_bid//self.bp for p in self.ports if p.next_bid<self.total]
        return min(heads,default=self.total//self.bp)

    def schedule_host_ar(self):
        for p in self.ports:
            if p.ar_queue and p.active<self.c.outstanding and not p.ar_scheduled:
                p.ar_scheduled=True
                self.event(max(self.now,p.next_ar_time),'ar',p.index)

    def start_port_lookups(self,p):
        c=self.c
        while p.lookup_queue and (c.lookup_slots is None or p.lookup_active<c.lookup_slots):
            lane=None
            if c.lookup_clock_mhz is not None:
                next_time,lane=p.lanes[0]
                start=self.lookup_clock_edge(max(self.now,next_time))
                if start>self.now+1e-10:
                    if not p.wake_scheduled:
                        p.wake_scheduled=True;self.event(start,'lookup_wakeup',p.index)
                    break
                heapq.heapreplace(p.lanes,(self.now+c.lookup_ii_cycles/c.lookup_clock_mhz,lane))
            bid=p.lookup_queue.popleft();b=self.bursts[bid];b['lookup_start']=self.now
            if lane is not None:b['lookup_pipeline']=lane
            p.lookup_active+=1;p.lookup_peak=max(p.lookup_peak,p.lookup_active)
            self.lookup_active+=1;self.lookup_peak=max(self.lookup_peak,self.lookup_active)
            self.log('lookup_start',burst=bid,port=p.index,lookup_active=p.lookup_active)
            self.event(self.now+c.lookup_us,'lookup',bid)
        p.queue_peak=max(p.queue_peak,len(p.lookup_queue))
        self.lookup_queue_peak=max(self.lookup_queue_peak,sum(len(q.lookup_queue) for q in self.ports))

    def start_r(self):
        for p in self.ports:
            if p.r_busy or not p.returns or not self.eligible(p.returns[0]):continue
            bid=p.returns[0];self.bursts[bid]['r_start']=self.now;p.r_busy=True
            duration=(self.c.burst_bytes*8/self.c.axi_width_bits)/self.c.axi_clock_mhz
            self.event(self.now+duration,'rlast',bid)

    def run(self):
        c=self.c
        while self.events:
            t,_,kind,data=heapq.heappop(self.events)
            for p in self.ports:
                if p.returns and not p.r_busy:
                    self.port_idle[p.index]+=t-self.now
                    head=p.returns[0]
                    if not self.eligible(head) and self.port_ready[p.index]:
                        self.port_hol_idle[p.index]+=t-self.now
            self.now=t;nand_changed=False
            if kind=='demand':
                for bid in range(data*self.br,(data+1)*self.br):
                    self.ports[bid%c.host_ports].ar_queue.append(bid)
            elif kind=='prefetch':
                for pid in range(data*self.pp,(data+1)*self.pp):self.page(pid,True)
                nand_changed=True
            elif kind=='ar':
                p=self.ports[data];p.ar_scheduled=False
                if p.ar_queue and p.active<c.outstanding:
                    bid=p.ar_queue.popleft();p.active+=1;p.peak=max(p.peak,p.active)
                    self.active+=1;self.peak=max(self.peak,self.active);p.returns.append(bid)
                    self.bursts[bid]=dict(port=p.index,ar=self.now,lookup_done=False,
                                          hit_at_ar=self.snapshot(bid//self.bp))
                    self.log('ar',burst=bid,port=p.index,outstanding=p.active)
                    p.next_ar_time=self.now+1/c.axi_clock_mhz
                    p.lookup_queue.append(bid);self.start_port_lookups(p)
            elif kind=='lookup':
                b=self.bursts[data];p=self.ports[b['port']]
                b['lookup_done']=True;b['hit_at_lookup']=self.snapshot(data//self.bp)
                b['lookup_complete_us']=self.now;p.lookup_active-=1;self.lookup_active-=1
                self.log('lookup_done',burst=data,port=p.index,lookup_active=p.lookup_active)
                nand_changed=data//self.bp not in self.pages
                self.page(data//self.bp)
                if self.eligible(data):
                    self.ready_bursts.add(data);self.port_ready[p.index].add(data)
                self.start_port_lookups(p)
            elif kind=='lookup_wakeup':
                p=self.ports[data];p.wake_scheduled=False;self.start_port_lookups(p)
            elif kind=='sense':
                page=self.pages[data];self.cmd_busy.remove(page['chip']);page['state']='sense'
                self.event(self.now+c.tr_us,'sensed',data);nand_changed=True
            elif kind=='sensed':
                self.pages[data]['state']='sensed';nand_changed=True
            elif kind=='transfer_done':
                page=self.pages[data];self.io_busy.remove(page['ch'])
                self.plane_busy.remove((page['chip'],page['plane']))
                self.channel_busy_us[page['ch']]+=c.page_bytes/(c.io_gbps*1000)+c.turnaround_us
                self.nand_bytes+=c.page_bytes;page['state']='ecc'
                self.event(self.now+c.ecc_us,'ready',data);nand_changed=True
            elif kind=='ready':
                page=self.pages[data];page['state']='ready';page['ready']=self.now
                self.log('page_ready',page=data);del self.pending_pages[data]
                for bid in range(data*self.bp,(data+1)*self.bp):
                    if bid in self.bursts and 'rlast' not in self.bursts[bid] and self.eligible(bid):
                        self.ready_bursts.add(bid);self.port_ready[bid%c.host_ports].add(bid)
            elif kind=='rlast':
                b=self.bursts[data];p=self.ports[b['port']]
                assert p.returns.popleft()==data
                b['rlast']=self.now;p.active-=1;self.active-=1
                p.next_bid=data+c.host_ports;self.next_r+=1;p.r_busy=False
                self.ready_bursts.discard(data)
                self.port_ready[p.index].discard(data)
                page=self.pages[data//self.bp];page['returned']+=1
                if page['returned']==self.bp:
                    self.used-=c.page_bytes;page['state']='returned';nand_changed=True
                self.log('rlast',burst=data,port=p.index,outstanding=p.active)
            self.schedule_host_ar()
            if nand_changed:self.dispatch()
            self.start_r()
        assert self.next_r==self.total,f'deadlock {self.next_r}/{self.total}'
        assert self.active==self.lookup_active==self.used==0
        assert not self.ready_bursts
        assert all(not p.ar_queue and not p.returns and not p.lookup_queue for p in self.ports)
        requests=[]
        for i in range(c.requests):
            bs=[self.bursts[j] for j in range(i*self.br,(i+1)*self.br)]
            demand=c.first_demand_us+i*c.period_us
            ar=min(b['ar'] for b in bs);last=max(b['rlast'] for b in bs)
            first_data=min(b['r_start']+1/c.axi_clock_mhz for b in bs)
            requests.append(dict(request=i,demand_us=demand,first_ar_us=ar,
                                 first_data_us=first_data,full_us=last,
                                 full_latency_us=last-demand,service_us=last-ar))
        first=min(b['ar'] for b in self.bursts.values());last=max(b['rlast'] for b in self.bursts.values())
        latency=sorted(r['full_latency_us'] for r in requests)
        metrics=dict(throughput_gbps=c.requests*c.request_bytes/(last-first)/1000,
                     completion_span_us=last-first,host_ceiling_gbps=c.host_ports*c.axi_width_bits*c.axi_clock_mhz/8000,
                     mean_request_latency_us=sum(latency)/len(latency),
                     p95_request_latency_us=latency[math.ceil(.95*len(latency))-1],
                     mean_request_service_us=sum(r['service_us'] for r in requests)/c.requests,
                     mean_first_data_latency_us=sum(r['first_data_us']-r['demand_us'] for r in requests)/c.requests,
                     mean_burst_latency_us=sum(b['rlast']-b['ar'] for b in self.bursts.values())/self.total,
                     peak_outstanding=self.peak,peak_lookup_active=self.lookup_peak,
                     peak_lookup_queue=self.lookup_queue_peak,buffer_peak_bytes=self.buffer_peak,nand_bytes=self.nand_bytes,
                     ready_hit_at_ar=sum(b['hit_at_ar']=='ready' for b in self.bursts.values())/self.total,
                     ready_hit_at_lookup=sum(b['hit_at_lookup']=='ready' for b in self.bursts.values())/self.total,
                     late_hit_at_ar=sum(b['hit_at_ar']=='late' for b in self.bursts.values())/self.total,
                     mean_lookup_wait_us=sum(b['lookup_start']-b['ar'] for b in self.bursts.values())/self.total,
                     max_lookup_wait_us=max(b['lookup_start']-b['ar'] for b in self.bursts.values()),
                     mean_ar_to_lookup_done_us=sum(b['lookup_complete_us']-b['ar'] for b in self.bursts.values())/self.total,
                     r_idle_us=sum(self.port_idle),hol_idle_us=sum(self.port_hol_idle),
                     used_nand_channels=len({p['ch'] for p in self.pages.values()}),
                     nand_raw_ceiling_gbps=c.channels*c.io_gbps,
                     port_peak_outstanding=[p.peak for p in self.ports],
                     port_peak_lookup_active=[p.lookup_peak for p in self.ports])
        port_throughput=[];port_tail=[]
        for p in self.ports:
            bids=range(p.index,self.total,c.host_ports)
            count=len(bids)
            if not count:port_throughput.append(0.);port_tail.append(0.);continue
            port_throughput.append(count*c.burst_bytes/(last-first)/1000)
            if count<2:port_tail.append(0.);continue
            middle=count//2;end=self.bursts[bids[-1]]['rlast']
            begin=self.bursts[bids[middle-1]]['rlast']
            port_tail.append((count-middle)*c.burst_bytes/(end-begin)/1000)
        metrics['port_throughput_gbps']=port_throughput
        # Independent port windows; also report a common aggregate tail window.
        metrics['sum_port_tail_throughput_gbps']=sum(port_tail)
        completion_times=sorted(b['rlast'] for b in self.bursts.values())
        cutoff=completion_times[max(0,self.total//2-1)]
        tail_bytes=sum(c.burst_bytes for b in self.bursts.values() if b['rlast']>cutoff)
        metrics['tail_throughput_gbps']=tail_bytes/(last-cutoff)/1000 if last>cutoff else 0.
        return metrics,requests


def main():
    import argparse
    import csv
    import json
    from pathlib import Path
    from dataclasses import asdict,replace
    from lookup_power import measure_energy
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,help='MultiportConfig JSON')
    parser.add_argument('--out',type=Path,default=Path('results/multiport_manual'))
    parser.add_argument('--trace',action='store_true',help='record full event trace')
    args=parser.parse_args()
    c=MultiportConfig(**json.loads(args.config.read_text())) if args.config else MultiportConfig(record_trace=False)
    if args.trace:c=replace(c,record_trace=True)
    sim=MultiportSimulator(c);metrics,requests=sim.run()
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'config.json').write_text(json.dumps(asdict(c),indent=2)+'\n')
    (args.out/'summary.json').write_text(json.dumps(metrics,indent=2)+'\n')
    if c.lookup_clock_mhz is not None and c.lookup_slots is not None:
        (args.out/'energy.json').write_text(json.dumps(measure_energy(sim),indent=2)+'\n')
    for name,rows in [('requests.csv',requests),('events.csv',sim.trace)]:
        if not rows:continue
        with (args.out/name).open('w',newline='') as f:
            fields=list(dict.fromkeys(k for row in rows for k in row))
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(json.dumps(metrics,indent=2))


if __name__=='__main__':main()
