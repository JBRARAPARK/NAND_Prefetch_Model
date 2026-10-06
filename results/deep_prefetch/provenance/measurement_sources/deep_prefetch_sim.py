"""Online prefetch extension; legacy simulator remains unchanged. Times in us."""
from dataclasses import dataclass
import random
import heapq
import math
from multiport_sim import MultiportConfig, MultiportSimulator

@dataclass(frozen=True)
class DeepConfig(MultiportConfig):
    mode: str = 'demand'
    accuracy: float = 1.0
    lead_us: float = 10.0
    prefetch_limit: int = 128
    prediction_queue_limit: int = 128
    throttle: bool = False
    total_descriptors: int | None = None
    seed: int = 7

class DeepSimulator(MultiportSimulator):
    def __init__(self,c):
        if c.mode not in ('demand','ready','online') or not 0<=c.accuracy<=1 or c.lead_us<0 or c.prefetch_limit<0:
            raise ValueError('prefetch parameters')
        if c.total_descriptors is not None and c.total_descriptors<c.host_ports+1:raise ValueError('descriptor budget')
        if not math.isfinite(c.lead_us) or type(c.prediction_queue_limit) is not int or c.prediction_queue_limit<0 or type(c.prefetch_limit) is not int:raise ValueError('prediction resources')
        super().__init__(c)
        self.pf_inflight_ids=set();self.pf_descriptor_ids=set();self.rng=random.Random(c.seed);self.pf_issued=0;self.pf_wrong=0;self.pf_suppressed=0;self.prediction_dropped=0
        self.pf_wait=[];self.demand_wait=[];self.pf_queue_area=0.;self.pf_live_peak=0
        self.nand_area=0.;self.r_area=0.;self.buf_area=0.;self.prep_end=0.;self.host_end=0.;self.descriptor_peak=0;self.prediction_peak=0
        self.windows=[];self.last_account=0.
        # Replace only prediction events. Ready starts in advance; online begins
        # at the first host arrival, with no free warm-up or oracle-ready pages.
        self.events=[e for e in self.events if e[2]!='prefetch'];heapq.heapify(self.events)
        if c.mode!='demand':
            for i in range(c.requests):
                target=c.first_demand_us+i*c.period_us
                when=target-c.lead_us if c.mode=='ready' else max(c.first_demand_us,target-c.lead_us)
                self.event(when,'prefetch',i)
    def pf_live(self):
        return len(self.pf_inflight_ids)
    def pf_descriptors(self):
        return len(self.pf_descriptor_ids)
    def port_credit_available(self,p):
        return self.c.total_descriptors is None or p.active<(self.c.total_descriptors-self.pf_descriptors())//self.c.host_ports
    def host_credit_available(self):
        return self.c.total_descriptors is None or self.active+self.pf_live()<self.c.total_descriptors
    def schedule_host_ar(self):
        for p in self.ports:
            if p.ar_queue and p.active<self.c.outstanding and self.port_credit_available(p) and not p.ar_scheduled:
                p.ar_scheduled=True;self.event(max(self.now,p.next_ar_time),'ar',p.index)
    def page(self,pid,prefetch=False):
        new=pid not in self.pages
        p=super().page(pid,prefetch)
        if new:p.update(created=self.now,demand=not prefetch,wrong=False,issued_pf=False)
        if new and prefetch:self.pf_descriptor_ids.add(pid)
        if not prefetch:
            p['demand']=True;self.pf_descriptor_ids.discard(pid)
        return p
    def predict(self,i):
        c=self.c
        for k in range(self.pp):
            correct=self.rng.random()<self.c.accuracy
            pid=i*self.pp+k if correct else self.c.requests*self.pp+i*self.pp+k
            if pid in self.pages:continue
            if self.pf_descriptors()>=(c.requests*self.pp if c.mode=='ready' else c.prediction_queue_limit) or (self.c.total_descriptors is not None and self.active+self.pf_descriptors()>=self.c.total_descriptors-self.c.host_ports):
                self.prediction_dropped+=1;continue
            p=self.page(pid,True);p['wrong']=not correct
    def dispatch(self):
        c=self.c;head=self.head_page()
        # Demand first at command AND shared channel arbitration; nonpreemptive.
        ordered=sorted(self.pending_pages.values(),key=lambda p:(not p['demand'],p['pid']))
        queued_demand=sum(p['demand'] and p['state']=='queued' for p in ordered)
        for p in ordered:
            if p['state']!='queued':continue
            pf=not p['demand']
            if pf:
                if self.pf_live()>=c.prefetch_limit:continue
                if c.throttle and (queued_demand>0 or self.active>=.8*c.host_ports*c.outstanding):
                    self.pf_suppressed+=1;continue
                if c.total_descriptors is not None and self.active+self.pf_live()>=c.total_descriptors-c.host_ports:continue
            plane=(p['chip'],p['plane'])
            reserve=0 if head in self.pages and self.pages[head]['state']!='queued' else c.page_bytes
            if self.used+c.page_bytes+(reserve if p['pid']!=head else 0)>c.buffer_bytes:continue
            if plane in self.plane_busy or p['chip'] in self.cmd_busy:continue
            self.used+=c.page_bytes;self.buffer_peak=max(self.buffer_peak,self.used)
            if not pf:queued_demand-=1
            p['state']='command';p['issued_pf']=pf;p['issue']=self.now
            (self.pf_wait if pf else self.demand_wait).append(self.now-p['created'])
            if pf:
                self.pf_inflight_ids.add(p['pid']);self.pf_issued+=1;self.pf_wrong+=p['wrong']
            self.pf_live_peak=max(self.pf_live_peak,self.pf_live())
            self.plane_busy.add(plane);self.cmd_busy.add(p['chip'])
            self.log('nand_issue',page=p['pid']);self.event(self.now+c.command_us,'sense',p['pid'])
        for p in ordered:
            if p['state']=='sensed' and p['ch'] not in self.io_busy:
                self.io_busy.add(p['ch']);p['state']='transfer'
                self.event(self.now+c.page_bytes/(c.io_gbps*1000)+c.turnaround_us,'transfer_done',p['pid'])
    def account(self,t):
        self.descriptor_peak=max(self.descriptor_peak,self.active+self.pf_descriptors())
        self.prediction_peak=max(self.prediction_peak,self.pf_descriptors())
        if self.c.total_descriptors is not None:assert self.active+self.pf_descriptors()<=self.c.total_descriptors
        lo=max(self.now,self.c.first_demand_us);dt=max(0,t-lo)
        state=(len(self.io_busy),sum(p.r_busy for p in self.ports),self.used)
        if dt:
            if self.windows and self.windows[-1][2:]==state:
                a,b,*old=self.windows[-1];self.windows[-1]=(a,t,*state)
            else:self.windows.append((lo,t,*state))
        self.nand_area+=dt*len(self.io_busy);self.r_area+=dt*sum(p.r_busy for p in self.ports)
        self.buf_area+=dt*self.used
        self.pf_queue_area+=(t-self.now)*sum(p['prefetch'] and not p['demand'] and p['state']=='queued' for p in self.pending_pages.values())
    def extra_metrics(self,m,req):
        c=self.c;first=c.first_demand_us;end=max(r['full_us'] for r in req);span=end-first
        self.nand_area=sum(max(0,min(b,end)-a)*n for a,b,n,r,u in self.windows)
        self.r_area=sum(max(0,min(b,end)-a)*r for a,b,n,r,u in self.windows)
        self.buf_area=sum(max(0,min(b,end)-a)*u for a,b,n,r,u in self.windows)
        vals=sorted(r['full_latency_us'] for r in req)
        m.update(p50_request_latency_us=vals[math.ceil(.5*len(vals))-1],p99_request_latency_us=vals[math.ceil(.99*len(vals))-1],
            nand_utilization=self.nand_area/(span*c.channels),r_utilization=self.r_area/(span*c.host_ports),
            buffer_mean_bytes=self.buf_area/span,total_descriptor_peak=self.descriptor_peak,prediction_descriptor_peak=self.prediction_peak,prediction_dropped=self.prediction_dropped,prefetch_issued=self.pf_issued,prefetch_wrong=self.pf_wrong,
            useful_prefetch_ratio=(self.pf_issued-self.pf_wrong)/self.pf_issued if self.pf_issued else 0,
            waste_prefetch_ratio=self.pf_wrong/self.pf_issued if self.pf_issued else 0,
            prefetch_peak_descriptors=self.pf_live_peak,prefetch_queue_area_us=self.pf_queue_area,
            prefetch_max_wait_us=max(self.pf_wait,default=0),demand_max_nand_queue_us=max(self.demand_wait,default=0),
            prefetch_unissued=sum(p['prefetch'] and 'issue' not in p for p in self.pages.values()),
            preparation_nand_bytes=sum(c.page_bytes for p in self.pages.values() if p['ready'] is not None and p['ready']<first),
            preparation_active_span_us=max((p['ready']-(first-c.lead_us) for p in self.pages.values() if p['ready'] is not None and p['ready']<first),default=0),
            preparation_lead_us=c.lead_us if c.mode=='ready' else 0,
            end_to_end_gbps=c.requests*c.request_bytes/(end-(first-c.lead_us if c.mode=='ready' else first))/1000,
            drain_us=self.now-end)
        times=sorted(b['rlast'] for b in self.bursts.values())
        for label,a,b in [('initial',0,.25),('middle',.25,.75),('late',.75,1)]:
            ia=int(a*len(times));ib=int(b*len(times));start=first if ia==0 else times[ia-1]
            m[label+'_gbps']=(ib-ia)*c.burst_bytes/(times[ib-1]-start)/1000
        assert len(self.bursts)==self.total and all('rlast' in b for b in self.bursts.values())
        assert self.nand_bytes==(c.requests*self.pp+self.pf_wrong)*c.page_bytes
        assert all(p.peak<=c.outstanding for p in self.ports)
        assert self.buffer_peak<=c.buffer_bytes
        return m

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
            self.account(t)
            self.now=t;nand_changed=False
            if kind=='demand':
                for bid in range(data*self.br,(data+1)*self.br):
                    self.ports[bid%c.host_ports].ar_queue.append(bid)
            elif kind=='prefetch':
                self.predict(data);nand_changed=True
            elif kind=='ar':
                p=self.ports[data];p.ar_scheduled=False
                if p.ar_queue and p.active<c.outstanding and self.port_credit_available(p):
                    bid=p.ar_queue.popleft();p.active+=1;p.peak=max(p.peak,p.active)
                    self.active+=1;self.peak=max(self.peak,self.active);p.returns.append(bid)
                    self.bursts[bid]=dict(port=p.index,ar=self.now,lookup_done=False,
                                          hit_at_ar=self.snapshot(bid//self.bp),
                                          decision_complete_us=self.now+c.host_decision_us)
                    self.log('ar',burst=bid,port=p.index,outstanding=p.active)
                    p.next_ar_time=self.now+1/c.axi_clock_mhz
                    if c.host_decision_us:self.event(self.now+c.host_decision_us,'host_decision',bid)
                    else:p.lookup_queue.append(bid);self.start_port_lookups(p)
            elif kind=='host_decision':
                p=self.ports[self.bursts[data]['port']]
                self.log('host_decision_done',burst=data,port=p.index)
                p.lookup_queue.append(data);self.start_port_lookups(p)
            elif kind=='lookup':
                b=self.bursts[data];p=self.ports[b['port']]
                b['lookup_done']=True;b['hit_at_lookup']=self.snapshot(data//self.bp)
                b['lookup_complete_us']=self.now;p.lookup_active-=1;self.lookup_active-=1
                self.log('lookup_done',burst=data,port=p.index,lookup_active=p.lookup_active)
                nand_changed=True
                self.page(data//self.bp)['demand']=True
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
                nand_changed=True
                self.pf_descriptor_ids.discard(data);self.pf_inflight_ids.discard(data)
                page=self.pages[data];page['state']='ready';page['ready']=self.now
                self.log('page_ready',page=data);del self.pending_pages[data]
                if page.get('wrong'):
                    self.used-=c.page_bytes;page['state']='discarded';nand_changed=True
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
        # Cancel candidates that never issued; no host work is cancelled.
        for pid,p in list(self.pending_pages.items()):
            assert p['state']=='queued' and p['wrong'] and not p['demand']
            p['state']='cancelled';del self.pending_pages[pid]
        self.pf_descriptor_ids.clear()
        assert not self.pf_inflight_ids and not self.pending_pages
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
                     mean_host_decision_us=c.host_decision_us,
                     prefetch_decision_us=c.prefetch_decision_us,
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
        return self.extra_metrics(metrics,requests),requests
