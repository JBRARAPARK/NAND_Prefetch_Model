"""Assumption-based energy accounting in relative energy units (EU).

No coefficients are device measurements. Lookup voltage scales switching
energy only; leakage and the fixed AXI/NAND domain do not implicitly scale.
The observation window is first AR through final RLAST, excluding warmup.
"""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class PowerConfig:
    reference_voltage_v: float = 1.0
    lookup_voltage_v: float = 1.0
    clock_gating: bool = True
    clock_eu_per_cycle: float = 1.0
    slot_clock_eu_per_cycle: float = .002
    pipeline_clock_eu_per_cycle: float = .05
    lookup_eu_per_operation: float = 8.0
    queue_eu_per_transition: float = .5
    leakage_eu_per_us: float = 100.0
    slot_leakage_eu_per_us: float = .1
    pipeline_leakage_eu_per_us: float = 1.0
    background_eu_per_us: float = 200.0
    axi_eu_per_byte: float = .05
    nand_eu_per_byte: float = .5


def _merged(intervals):
    result=[]
    for start,end in sorted(intervals):
        if end<=start:continue
        if result and start<=result[-1][1]+1e-10:
            result[-1]=(result[-1][0],max(end,result[-1][1]))
        else:result.append((start,end))
    return result


def measure_energy(sim, power=PowerConfig()):
    """Account clock edges, operations and elapsed time after Simulator.run().

    Gated engine remains enabled from queued AR through lookup completion,
    including each lane's initiation interval. Gate opens on the next clock
    edge. Entire engine clock tree is gated together, not individually by slot.
    Clock and operation coefficients cover disjoint switching categories.
    NAND transfer energy is charged at transfer_done within the window.
    """
    c=sim.c
    if c.lookup_clock_mhz is None or c.lookup_slots is None:
        raise ValueError('energy accounting requires a lookup clock and finite slots')
    if sim.next_r!=sim.total:
        raise ValueError('run the simulator to completion before measuring energy')
    for name,value in asdict(power).items():
        if name=='clock_gating':
            if type(value) is not bool:raise ValueError('clock_gating must be bool')
        elif isinstance(value,bool) or not math.isfinite(value) or value<0:
            raise ValueError(f'{name} must be finite and nonnegative')
    if min(power.reference_voltage_v,power.lookup_voltage_v)<=0:
        raise ValueError('voltages must be positive')
    first=min(b['ar'] for b in sim.bursts.values())
    last=max(b['rlast'] for b in sim.bursts.values());span=last-first
    port_count=getattr(c,'host_ports',1)
    groups=[[] for _ in range(port_count)]
    for b in sim.bursts.values():groups[b.get('port',0)].append(b)
    interval_groups=[]
    for bursts in groups:
        if power.clock_gating:
            ii=c.lookup_ii_cycles/c.lookup_clock_mhz
            intervals=_merged((max(first,sim.lookup_clock_edge(b['ar'])),
                               min(last,max(sim.lookup_clock_edge(b['lookup_complete_us']),
                                            b['lookup_start']+ii))) for b in bursts)
        else:intervals=[(first,last)]
        interval_groups.append(intervals)
    def edge_index(t):
        return math.ceil((t-c.first_demand_us)*c.lookup_clock_mhz-1e-4)
    cycles=sum(edge_index(end)-edge_index(start) for intervals in interval_groups for start,end in intervals)
    enabled=sum(end-start for intervals in interval_groups for start,end in intervals)
    voltage_scale=(power.lookup_voltage_v/power.reference_voltage_v)**2
    clock_eu=cycles*(power.clock_eu_per_cycle+c.lookup_slots*power.slot_clock_eu_per_cycle+
                     c.lookup_pipelines*power.pipeline_clock_eu_per_cycle)*voltage_scale
    operation_eu=sim.total*power.lookup_eu_per_operation*voltage_scale
    # One FIFO enqueue and one dequeue per burst; waiting creates no poll events.
    queue_eu=2*sim.total*power.queue_eu_per_transition*voltage_scale
    leakage_eu=span*port_count*(power.leakage_eu_per_us+c.lookup_slots*power.slot_leakage_eu_per_us+
                    c.lookup_pipelines*power.pipeline_leakage_eu_per_us)
    background_eu=span*power.background_eu_per_us
    axi_bytes=c.requests*c.request_bytes
    # Page-ready occurs after ECC, so transfer completion is earlier by ecc_us.
    nand_bytes=sum(c.page_bytes for p in sim.pages.values()
                   if first<=p['ready']-c.ecc_us<=last)
    axi_eu=axi_bytes*power.axi_eu_per_byte;nand_eu=nand_bytes*power.nand_eu_per_byte
    lookup_eu=clock_eu+operation_eu+queue_eu+leakage_eu
    total_eu=lookup_eu+background_eu+axi_eu+nand_eu
    return dict(lookup_clock_cycles=cycles,lookup_clock_enabled_us=enabled,
                lookup_clock_duty=enabled/(span*port_count),clock_energy_eu=clock_eu,
                lookup_operation_energy_eu=operation_eu,queue_energy_eu=queue_eu,
                lookup_leakage_energy_eu=leakage_eu,background_energy_eu=background_eu,
                axi_energy_eu=axi_eu,nand_energy_eu=nand_eu,
                measured_nand_bytes=nand_bytes,lookup_energy_eu=lookup_eu,
                total_energy_eu=total_eu,mean_lookup_power_eu_per_us=lookup_eu/span,
                mean_total_power_eu_per_us=total_eu/span,
                energy_eu_per_byte=total_eu/axi_bytes)
