import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=Path('results'); rows=list(csv.DictReader(open(p/'sweep.csv')))
fig,axes=plt.subplots(1,3,figsize=(15,4.5))
for mapping in ['single','striped']:
    for ch in [1,4]:
        rr=[r for r in rows if r['mapping']==mapping and int(r['channels'])==ch and r['policy']=='fixed' and float(r['delay_us'])==0]
        axes[0].plot([float(r['lead_us']) for r in rr],[float(r['mean_full_stall_us']) for r in rr],marker='o',label=f'{mapping}, {ch} channel(s)')
for pol in ['none','fixed','adaptive']:
    rr=[r for r in rows if r['mapping']=='striped' and int(r['channels'])==4 and r['policy']==pol and (pol!='fixed' or float(r['lead_us'])==60)]
    axes[1].plot([float(r['delay_us']) for r in rr],[float(r['mean_full_stall_us']) for r in rr],marker='o',label=pol)
    rr=[r for r in rows if r['mapping']=='striped' and int(r['channels'])==4 and r['policy']==pol and (pol!='fixed' or float(r['lead_us'])==60)]
    axes[2].plot([float(r['delay_us']) for r in rr],[float(r['buffer_mean_bytes'])/1024 for r in rr],marker='o',label=pol)
for ax,title,x,y in zip(axes,['Prefetch lead vs completion','When target information arrives','Buffer credit occupancy'],['Prefetch lead (us)','Target known delay from hint (us)','Target known delay from hint (us)'],['Mean demand-to-full AXI return (us)','Mean demand-to-full AXI return (us)','Mean reserved + resident buffer (KiB)']):
    ax.set(title=title,xlabel=x,ylabel=y);ax.grid(alpha=.25);ax.legend(fontsize=8)
fig.suptitle('TLC sensitivity model: 64KiB, tR=50us assumption, 16KiB/page, QD1',fontsize=12)
fig.tight_layout();fig.savefig(p/'comparison.png',dpi=160)
