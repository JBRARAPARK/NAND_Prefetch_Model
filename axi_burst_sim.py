"""Burst-level timing experiment; microseconds, bytes. Not AXI RTL.

AR is accepted one per clock, R is globally in order, outstanding retires at
RLAST. Configurable bursts within one NAND page merge into one page read.
"""
from dataclasses import dataclass, asdict
from collections import deque
import heapq
import math

@dataclass(frozen=True)
class Config:
    requests: int = 100
    request_bytes: int = 65536
    page_bytes: int = 16384
    burst_bytes: int = 4096
    chips: int = 4
    channels: int = 4
    planes: int = 6
    mapping: str = 'striped'
    tr_us: float = 3.0
    lookup_us: float = 0.0
    # None preserves the original unlimited concurrent lookup model.
    # One slot is occupied from lookup start through completion (not RLAST).
    lookup_slots: int | None = None
    # None preserves legacy timing. Clock phase is zero at first_demand_us.
    # Pipelines control admission rate; slots independently bound in-flight work.
    lookup_clock_mhz: float | None = None
    lookup_pipelines: int = 1
    lookup_ii_cycles: int = 1
    outstanding: int = 1
    scenario: str = 'none'
    period_us: float = 0.0
    first_demand_us: float = 20000.0
    early_lead_us: float = 10000.0
    late_lead_us: float = 1.5
    buffer_bytes: int = 8 * 1024 * 1024
    io_gbps: float = 2.4
    command_us: float = 0.1
    turnaround_us: float = 0.05
    ecc_us: float = 0.2
    axi_width_bits: int = 256
    axi_clock_mhz: float = 500.0

class Simulator:
    def __init__(self, c):
        if c.scenario not in ('none','ready','late','mixed'): raise ValueError('scenario')
        if c.mapping not in ('single','striped','global_striped'): raise ValueError('mapping')
        if min(c.requests,c.outstanding,c.channels,c.chips,c.planes)<=0: raise ValueError('positive sizes')
        if c.request_bytes%c.page_bytes or c.page_bytes%c.burst_bytes: raise ValueError('alignment')
        if c.burst_bytes>4096 or c.burst_bytes*8%c.axi_width_bits: raise ValueError('burst')
        if c.buffer_bytes<c.page_bytes or min(c.lookup_us,c.tr_us,c.period_us)<0: raise ValueError('timing/capacity')
        if c.lookup_slots is not None and (type(c.lookup_slots) is not int or c.lookup_slots<=0):
            raise ValueError('lookup_slots must be a positive integer or None')
        if c.lookup_clock_mhz is not None and (isinstance(c.lookup_clock_mhz,bool) or
                not math.isfinite(c.lookup_clock_mhz) or c.lookup_clock_mhz<=0):
            raise ValueError('lookup_clock_mhz must be finite and positive or None')
        for name in ('lookup_pipelines','lookup_ii_cycles'):
            if type(getattr(c,name)) is not int or getattr(c,name)<=0:
                raise ValueError(f'{name} must be a positive integer')
        self.c=c;self.now=0.;self.seq=0;self.events=[];self.trace=[]
        self.pp=c.request_bytes//c.page_bytes;self.bp=c.page_bytes//c.burst_bytes
        self.br=c.request_bytes//c.burst_bytes;self.total=c.requests*self.br
        self.pages={};self.pending_pages={};self.bursts={};self.ar_queue=deque();self.next_r=0
        self.active=0;self.peak=0;self.ar_scheduled=False;self.r_busy=False
        self.lookup_queue=deque();self.lookup_active=0;self.lookup_peak=0;self.lookup_queue_peak=0
        self.lookup_wakeup_scheduled=False
        self.lookup_lanes=[(c.first_demand_us,i) for i in range(c.lookup_pipelines)]
        self.ready_bursts=set()
        self.plane_busy=set();self.cmd_busy=set();self.io_busy=set()
        self.used=0;self.buffer_peak=0;self.nand_bytes=0
        self.hol_idle=0.;self.idle=0.;self.last=0.
        for i in range(c.requests):
            demand=c.first_demand_us+i*c.period_us;self.event(demand,'demand',i)
            early=c.scenario=='ready' or (c.scenario=='mixed' and i%2==1)
            lead=c.early_lead_us if early else c.late_lead_us
            if early or c.scenario=='late':
                if demand-lead<0:raise ValueError('negative prefetch time')
                self.event(demand-lead,'prefetch',i)
    def event(self,t,kind,data):
        self.seq+=1;heapq.heappush(self.events,(t,self.seq,kind,data))
    def log(self,event,**kw): self.trace.append(dict(time_us=self.now,event=event,**kw))
    def page(self,pid,prefetch=False):
        if pid not in self.pages:
            req,k=divmod(pid,self.pp);start=req%self.c.chips
            chip=(start+k)%self.c.chips if self.c.mapping=='striped' else start
            plane=(k//self.c.chips if self.c.mapping=='striped' else k)%self.c.planes
            if self.c.mapping=='global_striped':
                chip=pid%self.c.chips
                plane=(pid//self.c.chips)%self.c.planes
            self.pages[pid]=dict(pid=pid,req=req,state='queued',chip=chip,plane=plane,ch=chip%self.c.channels,
                                 ready=None,prefetch=prefetch,returned=0)
            self.pending_pages[pid]=self.pages[pid]
        return self.pages[pid]
    def schedule_ar(self):
        if self.ar_queue and self.active<self.c.outstanding and not self.ar_scheduled:
            self.ar_scheduled=True
            self.event(max(self.now,getattr(self,'next_ar_time',0.)),'ar',None)
    def start_lookups(self):
        """FIFO service; queued ARs still occupy AXI outstanding credits."""
        limit=self.c.lookup_slots
        while self.lookup_queue and (limit is None or self.lookup_active<limit):
            lane=None
            if self.c.lookup_clock_mhz is not None:
                next_time,lane=self.lookup_lanes[0]
                start=self.lookup_clock_edge(max(self.now,next_time))
                if start>self.now+1e-10:
                    if not self.lookup_wakeup_scheduled:
                        self.lookup_wakeup_scheduled=True
                        self.event(start,'lookup_wakeup',None)
                    break
                heapq.heapreplace(self.lookup_lanes,
                                 (self.now+self.c.lookup_ii_cycles/self.c.lookup_clock_mhz,lane))
            bid=self.lookup_queue.popleft()
            self.bursts[bid]['lookup_start']=self.now
            if lane is not None:self.bursts[bid]['lookup_pipeline']=lane
            self.lookup_active+=1;self.lookup_peak=max(self.lookup_peak,self.lookup_active)
            self.log('lookup_start',burst=bid,lookup_active=self.lookup_active)
            self.event(self.now+self.c.lookup_us,'lookup',bid)
        self.lookup_queue_peak=max(self.lookup_queue_peak,len(self.lookup_queue))
    def lookup_clock_edge(self,t):
        """First lookup-domain edge at/after t; tolerate float cancellation."""
        origin=self.c.first_demand_us
        # Existing AR/R times add small durations to a 20,000us epoch. Their
        # accumulated roundoff must not manufacture an extra lookup cycle.
        return origin+math.ceil((t-origin)*self.c.lookup_clock_mhz-1e-4)/self.c.lookup_clock_mhz
    def dispatch(self):
        c=self.c
        for p in sorted(self.pending_pages.values(),key=lambda x:x['pid']):
            if p['state']!='queued':continue
            plane=(p['chip'],p['plane'])
            # Reserve space for the oldest unreturned page to prevent HOL deadlock.
            head=self.head_page()
            reserve=0 if head in self.pages and self.pages[head]['state']!='queued' else c.page_bytes
            if self.used+c.page_bytes+(reserve if p['pid']!=head else 0)>c.buffer_bytes:continue
            if plane in self.plane_busy or p['chip'] in self.cmd_busy:continue
            self.used+=c.page_bytes;self.buffer_peak=max(self.buffer_peak,self.used)
            p['state']='command';self.plane_busy.add(plane);self.cmd_busy.add(p['chip'])
            self.log('nand_issue',page=p['pid']);self.event(self.now+c.command_us,'sense',p['pid'])
        for p in sorted(self.pending_pages.values(),key=lambda x:x['pid']):
            if p['state']=='sensed' and p['ch'] not in self.io_busy:
                self.io_busy.add(p['ch']);p['state']='transfer'
                self.event(self.now+c.page_bytes/(c.io_gbps*1000)+c.turnaround_us,'transfer_done',p['pid'])
    def head_page(self):
        return self.next_r//self.bp
    def eligible(self,bid):
        b=self.bursts.get(bid)
        return b is not None and b['lookup_done'] and self.pages.get(bid//self.bp,{}).get('ready') is not None
    def start_r(self):
        if self.r_busy or not self.eligible(self.next_r):return
        c=self.c;b=self.bursts[self.next_r];b['r_start']=self.now;self.r_busy=True
        # AR uses its own channel; R duration follows burst size and bus width.
        duration=(c.burst_bytes*8/c.axi_width_bits)/c.axi_clock_mhz
        self.event(self.now+duration,'rlast',self.next_r)
    def snapshot(self,pid):
        p=self.pages.get(pid)
        if not p or not p['prefetch']:return 'miss'
        return 'ready' if p['ready'] is not None else 'late'
    def run(self):
        c=self.c
        while self.events:
            t,_,kind,data=heapq.heappop(self.events)
            if self.next_r<self.total and self.bursts and not self.r_busy:
                self.idle+=t-self.now
                if not self.eligible(self.next_r) and self.ready_bursts:self.hol_idle+=t-self.now
            self.now=t
            if kind=='demand':
                self.ar_queue.extend(range(data*self.br,(data+1)*self.br))
            elif kind=='prefetch':
                for p in range(data*self.pp,(data+1)*self.pp):self.page(p,True)
            elif kind=='ar':
                self.ar_scheduled=False
                if self.ar_queue and self.active<c.outstanding:
                    bid=self.ar_queue.popleft();self.active+=1;self.peak=max(self.peak,self.active)
                    self.bursts[bid]=dict(ar=self.now,lookup_done=False,hit_at_ar=self.snapshot(bid//self.bp))
                    self.log('ar',burst=bid,outstanding=self.active)
                    self.next_ar_time=self.now+1/c.axi_clock_mhz
                    self.lookup_queue.append(bid)
                    self.start_lookups()
            elif kind=='lookup':
                b=self.bursts[data];b['lookup_done']=True;b['hit_at_lookup']=self.snapshot(data//self.bp)
                b['lookup_complete_us']=self.now;self.lookup_active-=1
                self.log('lookup_done',burst=data,lookup_active=self.lookup_active)
                self.page(data//self.bp)
                if self.eligible(data):self.ready_bursts.add(data)
                self.start_lookups()
            elif kind=='lookup_wakeup':
                self.lookup_wakeup_scheduled=False
                self.start_lookups()
            elif kind=='sense':
                p=self.pages[data];self.cmd_busy.remove(p['chip']);p['state']='sense'
                self.event(self.now+c.tr_us,'sensed',data)
            elif kind=='sensed':self.pages[data]['state']='sensed'
            elif kind=='transfer_done':
                p=self.pages[data];self.io_busy.remove(p['ch']);self.plane_busy.remove((p['chip'],p['plane']))
                self.nand_bytes+=c.page_bytes;p['state']='ecc';self.event(self.now+c.ecc_us,'ready',data)
            elif kind=='ready':
                p=self.pages[data];p['state']='ready';p['ready']=self.now;self.log('page_ready',page=data)
                del self.pending_pages[data]
                lo=max(self.next_r,data*self.bp)
                hi=min(self.next_r+self.active,(data+1)*self.bp)
                self.ready_bursts.update(b for b in range(lo,hi) if self.eligible(b))
            elif kind=='rlast':
                assert data==self.next_r
                b=self.bursts[data];b['rlast']=self.now;self.active-=1;self.next_r+=1;self.r_busy=False
                self.ready_bursts.discard(data)
                p=self.pages[data//self.bp];p['returned']+=1
                if p['returned']==self.bp:self.used-=c.page_bytes;p['state']='returned'
                self.log('rlast',burst=data,outstanding=self.active)
            self.schedule_ar();self.dispatch();self.start_r()
        assert self.next_r==self.total, f'deadlock {self.next_r}/{self.total}'
        assert self.active==0 and self.used==0
        assert self.lookup_active==0 and not self.lookup_queue and not self.ready_bursts
        req=[]
        for i in range(c.requests):
            bs=[self.bursts[j] for j in range(i*self.br,(i+1)*self.br)]
            demand=c.first_demand_us+i*c.period_us
            req.append(dict(request=i,demand_us=demand,first_ar_us=bs[0]['ar'],
                            first_data_us=bs[0]['r_start']+1/c.axi_clock_mhz,
                            full_us=bs[-1]['rlast'],full_latency_us=bs[-1]['rlast']-demand,
                            service_us=bs[-1]['rlast']-bs[0]['ar']))
        vals=sorted(r['full_latency_us'] for r in req);first=self.bursts[0]['ar'];last=self.bursts[self.total-1]['rlast']
        m=dict(mean_request_latency_us=sum(vals)/len(vals),p95_request_latency_us=vals[math.ceil(.95*len(vals))-1],
               mean_request_service_us=sum(r['service_us'] for r in req)/len(req),
               mean_first_data_latency_us=sum(r['first_data_us']-r['demand_us'] for r in req)/len(req),
               mean_burst_latency_us=sum(b['rlast']-b['ar'] for b in self.bursts.values())/self.total,
               throughput_gbps=c.requests*c.request_bytes/(last-first)/1000,
               completion_span_us=last-first,peak_outstanding=self.peak,buffer_peak_bytes=self.buffer_peak,
               ready_hit_at_ar=sum(b['hit_at_ar']=='ready' for b in self.bursts.values())/self.total,
               ready_hit_at_lookup=sum(b['hit_at_lookup']=='ready' for b in self.bursts.values())/self.total,
               late_hit_at_ar=sum(b['hit_at_ar']=='late' for b in self.bursts.values())/self.total,
               r_idle_us=self.idle,hol_idle_us=self.hol_idle,nand_bytes=self.nand_bytes,
               peak_lookup_active=self.lookup_peak,peak_lookup_queue=self.lookup_queue_peak,
               mean_lookup_wait_us=sum(b['lookup_start']-b['ar'] for b in self.bursts.values())/self.total,
               max_lookup_wait_us=max(b['lookup_start']-b['ar'] for b in self.bursts.values()),
               mean_ar_to_lookup_done_us=sum(b['lookup_complete_us']-b['ar'] for b in self.bursts.values())/self.total)
        return m,req
