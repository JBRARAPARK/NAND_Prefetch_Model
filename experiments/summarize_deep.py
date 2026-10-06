import csv,json,html
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/deep_prefetch'
rows=list(csv.DictReader((OUT/'sweep.csv').open()))
def v(r,k):return float(r[k]) if r.get(k) else 0
colors={'demand':'#555555','ready':'#2478b4','online':'#db6b20'}
labels={'demand':'demand','ready':'oracle ready','online':'synthetic online'}
fig,axs=plt.subplots(2,2,figsize=(12,8))
for col,period in enumerate((0,1.024)):
 for mode in ('demand','ready','online'):
  rr=[r for r in rows if r['comparison']=='same_host' and r['case'].startswith('host_') and v(r,'period_us')==period and r['mode']==mode and r['throttle']=='False']
  rr.sort(key=lambda r:v(r,'outstanding'));x=[v(r,'outstanding') for r in rr]
  axs[0,col].plot(x,[v(r,'late_gbps') for r in rr],'-o',label=labels[mode],color=colors[mode])
  axs[1,col].plot(x,[v(r,'buffer_peak_bytes')/1048576 for r in rr],'-o',label=labels[mode],color=colors[mode])
 if period==0:
  lr=[r for r in rows if v(r,'requests')==512 and r['mode']=='demand' and v(r,'period_us')==0 and r['comparison']=='same_host'];lr.sort(key=lambda r:v(r,'outstanding'))
  axs[0,col].plot([v(r,'outstanding') for r in lr],[v(r,'late_gbps') for r in lr],'--s',color='#111111',label='demand, 512 requests')
 axs[0,col].set_title('Uncapped arrivals' if period==0 else '64 GB/s arrivals')
 for a in axs[:,col]:a.set_xscale('log');a.set_xlabel('AXI credits per port');a.grid(alpha=.3);a.legend()
 axs[0,col].set_ylabel('Late completion window GB/s');axs[1,col].set_ylabel('Peak reserved buffer MiB')
fig.suptitle('64 requests, accuracy=1; future-informed prefetch; ready preparation excluded',fontsize=12)
fig.tight_layout(rect=(0,0,1,.96));fig.savefig(OUT/'performance_buffer.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4))
for mode in ('ready','online'):
 rr=[r for r in rows if r['case'].startswith('host_0_') and r['mode']==mode and r['throttle']=='False']
 rr.sort(key=lambda r:v(r,'outstanding'))
 demand={r['outstanding']:r for r in rows if r['case'].startswith('host_0_') and r['mode']=='demand'}
 ax.plot([v(r,'outstanding') for r in rr],[v(r,'throughput_gbps')/v(demand[r['outstanding']],'throughput_gbps') for r in rr],'-o',label=labels[mode],color=colors[mode])
ax.set_title('64 requests; future-informed prefetch; ready preparation excluded')
ax.set_xscale('log');ax.set_xlabel('AXI credits per port');ax.set_ylabel('Full host-span throughput / demand');ax.grid(alpha=.3);ax.legend();fig.tight_layout();fig.savefig(OUT/'gain.png',dpi=170)
fig,axs=plt.subplots(1,2,figsize=(11,4))
for mode in ('demand','ready','online'):
 rr=[r for r in rows if r['comparison']=='same_total' and r['mode']==mode and v(r,'period_us')==0];rr.sort(key=lambda r:v(r,'total_descriptors'))
 axs[0].plot([v(r,'total_descriptors') for r in rr],[v(r,'throughput_gbps') for r in rr],'-o',label=labels[mode],color=colors[mode])
 axs[1].plot([v(r,'total_descriptors') for r in rr],[v(r,'p99_request_latency_us') for r in rr],'-o',label=labels[mode],color=colors[mode])
for a in axs:a.set_xscale('log');a.set_xticks([2008,40000],labels=['2,008','40,000']);a.minorticks_off();a.set_xlabel('Mixed AR/page token cap (2 MiB buffer)');a.grid(alpha=.3);a.legend()
axs[0].set_ylabel('Full host-span GB/s');axs[1].set_ylabel('Host request p99 us');fig.suptitle('Abstract mixed-token comparison; not equal hardware cost');fig.tight_layout(rect=(0,0,1,.92));fig.savefig(OUT/'equal_budget.png',dpi=170);plt.close(fig)
br=[r for r in rows if r['comparison']=='buffer_boundary' or r['case']=='long_10000_demand'];br.sort(key=lambda r:v(r,'buffer_budget_bytes'))
fig,ax=plt.subplots(figsize=(7,4));ax.plot([v(r,'buffer_budget_bytes')/1048576 for r in br],[v(r,'late_gbps') for r in br],'-o');ax.axhline(256,color='gray',linestyle='--');ax.set_xlabel('Shared buffer budget MiB (512 requests, O=10000/port)');ax.set_ylabel('Late window GB/s');ax.grid(alpha=.3);fig.tight_layout();fig.savefig(OUT/'buffer_boundary.png',dpi=170);plt.close(fig)
fields=['case','outstanding','throughput_gbps','initial_gbps','middle_gbps','late_gbps','p50_request_latency_us','p95_request_latency_us','p99_request_latency_us','buffer_peak_bytes','nand_utilization','r_utilization','prefetch_issued','prefetch_wrong','prediction_dropped','prefetch_unissued','prefetch_max_wait_us','demand_max_nand_queue_us','total_descriptor_peak','preparation_active_span_us','end_to_end_gbps']
def table(rr):
 def cell(r,k):
  val=r.get(k,'')
  if val:
   try:val=f'{float(val):.3f}'
   except ValueError:pass
  return '<td>'+html.escape(val)+'</td>'
 return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+k+'</th>' for k in fields)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(cell(r,k) for k in fields)+'</tr>' for r in rr)+'</tbody></table></div>'
manifest=json.loads((OUT/'manifest.json').read_text())
late_demand=[r for r in rows if r['case'].startswith('host_0_') and r['mode']=='demand'];sat=[v(r,'outstanding') for r in late_demand if v(r,'late_gbps')>=.95*256]
threshold=str(int(min(sat))) if sat else '미도달'
long_demand=[r for r in rows if v(r,'requests')==512 and r['mode']=='demand' and v(r,'period_us')==0 and r['comparison']=='same_host']
long_ok=[v(r,'outstanding') for r in long_demand if min(v(r,'middle_gbps'),v(r,'late_gbps'))>=.95*256]
long_threshold=str(int(min(long_ok))) if long_ok else '미도달'
summary='<p>512 host request의 중간·후반이 모두 256GB/s의 95% 이상인 최소 측정 outstanding은 포트당 '+long_threshold+'이다. 짧은 실행에서는 O=6,000도 마지막 구간만 256GB/s를 보여 단일 후반 수치가 포화 경계를 과소 추정할 수 있었다.</p>'
summary+='<p>64GB/s 입력·O=502의 긴 실행에서 demand-only는 후반 13.419GB/s, synthetic online은 64GB/s를 유지했다. 합성 online 버퍼 최고 예약은 1,261,568B(1.203MiB), demand-only는 131,072B(0.125MiB)로 9.625배이며, 전체 descriptor 최고 사용은 각각 2,076과 2,008이다. Demand 요청 p99는 1,963.173µs, online은 5.673µs였다. 이는 미래 요청을 아는 accuracy=1·lead=10µs·발행 제한 128의 합성 모델 결과이며 인과적 예측기의 성능이 아니다.</p>'
summary+='<p>O=10,000·512 host request에서 버퍼 2MiB는 후반 225.000GB/s, 2.25MiB는 252.770GB/s, 2.5MiB는 256GB/s였다. 2.5MiB 구성의 실제 최고 예약은 2,392,064B(2.28125MiB)다. 측정한 버퍼 지점 중 정확히 host 상한을 유지한 최소는 2.5MiB이며, 2.25–2.5MiB 사이의 정밀 경계는 측정하지 않았다. 95% 상한 기준이라면 2.25MiB도 충족한다.</p>'
summary+='<p>추상 혼합 토큰 상한 2,008·2MiB 버퍼·64GB/s 입력·512 request에서 demand-only 전체/후반은 13.412/13.419GB/s였다. Host credit을 포트당 128로 배분한 합성 online은 63.987/64.540GB/s, p99 9.787µs, descriptor 최고 586개, 버퍼 최고 1,277,952B였다. 후반 64GB/s 초과는 초기 backlog 해소가 섞인 유한 구간 값이다. Host가 credit을 모두 점유하도록 둔 짧은 online 비교에서는 이 이득이 없어, 이 합성 모델에서는 prefetch 후보 공간을 확보하는 배분이 필요했다. AR credit과 page descriptor를 1:1로 센 결과이므로 동일 하드웨어 비용에서의 이득을 입증하지 않는다.</p>'
summary+='<p>64GB/s 입력의 짧은 demand-only 실행은 O=2,000에서 후반 53.466GB/s, O=4,000에서 64GB/s였다. 최대 포화 조건과 입력 제한 조건의 필요한 outstanding 경계가 다르다. 외부 입력은 64KiB 요청을 1.024µs마다 내보내는 batch pacing이며, 첫 요청의 초기 토큰과 종료 효과 때문에 유한 전체 평균 또는 backlog 해소 구간이 64GB/s를 조금 넘을 수 있다.</p>'
report=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>NAND 심화 모델링 결과</title><style>body{{font:16px/1.7 sans-serif;margin:32px auto;max-width:1200px;color:#17212b}}img{{max-width:100%}}.scroll{{overflow:auto}}table{{border-collapse:collapse;font-size:12px}}td,th{{border:1px solid #ccd;padding:6px;white-space:nowrap}}h2{{margin-top:36px}}</style>
<h1>NAND Prefetch 심화 모델링 결과</h1><p>기준 커밋 bf63379b7587b63e01925730f123f37a1ec33bdf. 제품 실측이 아닌 결정론적 이벤트 모델 실험이다. 총 {manifest['cases']}조건, 완료된 조건의 실행시간 합계 {manifest['runtime_s']:.1f}초(개발 중 중단·재실행·테스트 시간 제외). 아래 CSV 기반 표는 실제 실행 값만 표시한다.</p>
<div style="border:2px solid #b56b16;padding:16px;background:#fff7e8"><strong>2026-10-06 설계 검토 정정 — 합성 모델의 중간 결과</strong><p>코드·CSV의 online은 미래 요청 ID와 도착 시각을 알고 실행 시점만 host 구간으로 제한한 합성 모델이다. 인과적 online predictor는 아직 구현·검증하지 않았다. Wrong prefetch를 ready 시 즉시 폐기하는 oracle 가정도 남아 있다. same_total은 64B AR credit과 16KiB speculative page descriptor를 각각 1로 센 혼합 토큰 예산이며 동일 unique-page 수나 동일 하드웨어 비용을 뜻하지 않는다. 103조건과 56개 테스트는 현재 모델에 대한 기록이며 상세 설계 요구 전체의 검증 완료가 아니다.</p><p><a href="../../docs/deep_prefetch_review/STATUS_KO.md">검토 현황·blind spot·미완료 항목</a>. 수치 CSV는 보존하고 이번에는 설명·그래프 표시를 정정했다.</p></div>
<h2>핵심 결과와 경계의 해석</h2><p>기존 O=502 demand-only 13.408GB/s와 ready 252.145GB/s, O=10,000 demand-only 197.265GB/s·후반 256GB/s를 재현했다. 새 64 host request의 포화 실험에서 후반 25% completion window가 host 상한 256GB/s의 95% 이상인 최소 측정 outstanding은 포트당 {threshold}이다. 이는 측정 지점 사이의 정확한 경계나 무한 정상상태의 증명이 아니다. 긴 실행 결과와 함께 판단해야 한다.</p>
<p>Ready는 host 이전에 충분한 시간을 주는 이상적 데이터 준비 비교이다. Synthetic online은 첫 host 도착 이후에 발행하며 NAND 경쟁·잘못된 page 읽기·버퍼 예약을 계측한다. 미래 trace 기반 후보와 oracle 오류 폐기를 사용하므로 실제 인과적 예측·버퍼 정책의 검증은 아니다. 추가 drain 시간은 따로 기록하지만 처리량 분모에는 마지막 demand 완료까지만 포함한다. 동시 일괄 도착(period=0)에서는 host 이전 선행 시간이 없고 처음 prediction queue에 수용된 후보만 speculative 읽기를 시작한다. ready의 큰 이득을 실제 online 성능으로 해석할 수 없다.</p>
<img src="performance_buffer.png"><img src="gain.png"><img src="equal_budget.png"><img src="buffer_boundary.png">
{summary}<h2>자원과 outstanding 정의</h2><p>Outstanding은 포트별 64B AXI burst AR 수락부터 RLAST까지 유지하는 credit이다. 64KiB host request 하나는 1,024 burst·16KiB NAND page 4개이다. Host request 개수를 AXI credit 수로 계산하지 않는다. 128 channel·128 chip·chip당 6 plane, tR 2.08µs, channel 2.4GB/s, command 0.1µs, turnaround 0.05µs, ECC 0.2µs, 4×512bit×1GHz R 포트로 고정한다. Lookup은 포트별 500MHz·0.5µs·500 slot·2 pipeline이다.</p>
<p>Demand 우선은 queued NAND command와 sensed page의 channel transfer arbitration에 적용하며 이미 시작한 sense/transfer는 선점하지 않는다. 버퍼는 sense 전에 page 전체를 예약하고 마지막 구성 burst가 반환될 때 반납한다. Wrong prefetch는 미래의 미사용 여부를 아는 oracle 표시로 ready 시 반납한다. 이 가정은 실제 오류 예측의 버퍼 체류 비용을 낙관적으로 만들 수 있다. 여러 burst의 같은 page 읽기는 하나로 병합한다. Buffer 최고 점유는 resident 데이터만이 아니라 in-flight 예약까지 포함한다.</p>
<p>같은 host outstanding 실험은 기본 공유 버퍼 8MiB, prefetch in-flight limit 128 page, online prediction descriptor queue limit 128을 사용한다. same_total 비교는 공유 버퍼 2MiB와 추상 혼합 토큰 합계 2,008 또는 40,000을 고정한다. Descriptor는 host burst 1개 또는 speculative page request 1개를 하나의 추상 entry로 계산한다. 서로 다른 단위를 더한 제약이며 동일 unique-page 수 또는 실제 바이트/하드웨어 비용의 공정한 비교는 아니다. 후보 대기와 NAND 실행 중의 speculative descriptor를 세며 ready 또는 demand 승격 후 해제한다. 포트별 공정 배분과 최소 host 진행 공간을 적용한다. Host의 미수락 AR queue·workload 저장 공간은 외부 source로 취급하므로 controller SRAM 비용에 포함하지 않는다.</p>
<h2>시간창·지연·준비 비용</h2><p>전체 throughput은 첫 host AR부터 마지막 host RLAST까지이다. initial/middle/late는 완료 burst 수 기준 0–25%, 25–75%, 75–100%의 구간 처리량이다. 서로 다른 wall-clock 길이를 가진 구간이며 정상상태 후보 지표다. Period=1.024µs는 64KiB/64GB/s의 외부 입력률이다. Period=0은 모든 host request가 동시에 준비되어 최대 포화 공급을 시험한다. Request 지연 p50/p95/p99는 외부 demand 도착부터 모든 구성 burst 반환까지로, AR 이전 대기와 FIFO HOL 대기를 포함한다. 이는 순수 NAND service latency가 아니다.</p>
<p>Ready의 preparation_lead_us=10,000은 사전 시작 lead이며 end_to_end_gbps에는 이 시간도 포함하지만 마지막 demand 이후의 speculative drain은 제외한다. 따라서 whole-job 처리량과 같지 않다. preparation_active_span_us는 최초 예측 trigger부터 host 전에 ready가 된 마지막 page까지의 span, preparation_nand_bytes는 host 이전에 준비된 NAND 바이트다. 이후 유휴 slack과 실제 작업 span을 혼동하지 않아야 한다. 같은 전체 예산에서 준비 후보를 admission drop할 수 있어 ready_hit_at_ar가 1 미만이면 제한된 준비 비교이다. 합성 online의 NAND 준비는 host 시간창 안에서 실행된다. 실제 predictor 연산 비용과 후보의 인과적 발생은 아직 구현하지 않았다. NAND/R 이용률은 host 도착부터 마지막 host 완료까지의 공통 시간창으로 적분하며, wrong read 종료를 포함하는 추가 drain_us는 별도다.</p>
<h2>기아·낭비·정책 평가</h2><p>prefetch_max_wait_us는 발행된 후보의 trigger→NAND issue 최대 대기, prefetch_queue_area_us는 미발행 후보 대기의 적분, prefetch_unissued는 drain 시 남아 취소되는 후보다. 발행 대기 최댓값만으로 기아 여부를 판단하지 않고 미발행 수·admission drop도 함께 본다. demand_max_nand_queue_us는 demand로 발행된 page의 최초 생성부터 issue까지의 age이다. 예측 후보가 demand로 승격되면 예측 시점부터의 시간도 포함하므로 순수 demand 대기와 같지 않다. Demand 지연의 대표 지표는 외부 도착부터의 요청 지연 p50/p95/p99이며, host queue를 포함하는 요청 지연을 함께 비교한다. Useful ratio는 실제 speculative issue 중 최종 host가 사용하는 올바른 page 비율이고, ready hit는 별도 지표다. Accuracy는 후보별 seed=7 Bernoulli 추상 예측이며 후보는 미래 요청을 알고 생성하므로 과거 관측만 사용하는 예측기 결과가 아니다.</p>
<p>포화 억제 정책은 queued demand가 있거나 AR active가 host credit 총량의 80% 이상이면 새로운 speculative issue를 보류한다. 억제 정책의 유효성은 paired rows로 평가한다. Default accuracy=1에서는 wrong read 낭비가 없어 억제 효과가 작을 수 있고, 혼합 토큰 budget에서 host가 토큰을 먼저 모두 차지하면 미래 후보 admission이 drop되어 online 이득이 사라질 수 있다. 같은 budget의 추가 allocation 실험은 host credit을 128/포트로 제한하여 prefetch 공간을 확보한다. 이는 host outstanding을 고정한 비교와 구분한다. 정확도가 낮은 예측은 억제 여부도 짝 비교한다. 감도 실험은 accuracy 0.5/0.9·lead 2/10µs·in-flight limit 32/128을 사용한다. Lead는 외부 입력 timing이 있을 때 의미가 있으며 일괄 도착 workload에는 무료 선행 시간을 만들지 않는다.</p>
<p>정확도 90%·lead 10µs·발행 제한 128의 64GB/s 입력 실험에서, 무억제 online 전체 처리량은 26.346GB/s이고 억제 정책은 14.727GB/s였다. Wrong prefetch page 수는 26에서 15로 줄었지만 useful 준비도 함께 줄어 throughput이 악화됐다. 이 80% credit 기반 억제를 성능 개선 정책으로 권장할 근거는 얻지 못했다.</p><h2>기존 결과 재현</h2>{table([r for r in rows if r['comparison']=='legacy'])}
<h2>새 실험 전체</h2>{table([r for r in rows if r['comparison']!='legacy'])}
<h2>이론 추정 — 측정과 구분</h2><p>Host 상한은 4×64GB/s=256GB/s이다. 채널 turnaround 포함 공급 상한은 128×16,384/(16,384/2,400+0.05)/1,000 ≈304.97GB/s이다. Ready lookup의 최대 1ns clock 정렬+500ns lookup+1ns R service를 숨기는 credit은 포트당 502개다. Cold NAND 경로 0.5+0.1+2.08+6.827+0.05+0.2≈9.757µs를 64GB/s 포트로 가리는 단순 Little's law는 약 9,757 burst credit/포트와 총 약 2.50MB 전달 데이터 window를 준다. page 병합·channel queue·plane 병렬성·FIFO 때문에 이 값은 실제 경계의 해석식이 아니다. Descriptor 크기를 entry당 D bytes로 잡으면 credit 저장 비용은 최소 4×outstanding×D이며, O=502는 2,008D, O=10,000은 40,000D이다. 16/32B entry라는 가정에서는 각각 약 31.4/62.8KiB와 625/1,250KiB이다. 별도 prefetch descriptor·page metadata·lookup slot·버퍼 비용을 더해야 하며 실제 entry 크기는 측정하지 않았다. Descriptor entry 크기·SRAM bank·PHY·실제 에너지 비용은 측정하지 않았다.</p>
<h2>재현과 검증</h2><pre>cd NAND_Prefetch_Model
python3 -m unittest -q
python3 experiments/run_deep.py
python3 experiments/run_deep_extra.py
python3 experiments/run_buffer_boundary.py
MPLCONFIGDIR=/tmp/nand-mpl .venv/bin/python experiments/summarize_deep.py</pre><p>configs.json은 모든 실행 구성, sweep.csv는 계측 결과, manifest.json은 기준 commit·실행시간·소스 SHA256, estimate.json은 대규모 실행 전 추정을 보존한다. 기존 시뮬레이터 코드와 기존 결과는 수정하지 않고 별도 모델·test·runner를 추가했다. 기존 50개와 추가 6개, 합계 56 tests 및 실행마다 credit bound·최종 반환 수·버퍼 drain·NAND byte 수를 확인한다. 테스트는 현재 합성 모델 구현의 검증이며 인과적 predictor·재사용 page 수명·상세 설계 전체·RTL 또는 실제 NAND 검증이 아니다. 원래 manifest의 측정 소스 해시는 보존하고 변경 전 소스를 provenance/measurement_sources에 보관했다. review_manifest.json에 이번 설명 정정과 검증을 따로 기록한다.</p>
<h2>모델의 한계</h2><p>순차 page ID의 균등 striping workload 하나를 사용한다. Reuse·random hotspot·multi-candidate predictor·GC/program/erase·SRAM bank conflict·fabric bandwidth·AXI ID 재정렬은 측정하지 않았다. R 반환은 포트 안에서 FIFO, 포트 사이 전역 FIFO는 강제하지 않는다. 짧은 run의 후반은 이미 준비된 page와 종료 효과로 높을 수 있다. 512 host request 비교는 지속성을 확인하는 한 단계이며 무한 steady state의 확증이 아니다. 완료된 조건의 측정값을 보존하며 중간에 카운터를 최적화했으므로 기록된 runtime은 서로 다른 구현 비용을 포함한다. 동일 최종 소스의 단일 fresh sweep runtime과 같다고 해석하지 않는다. 초기 단순 선형 시간 추정은 큐 처리 비용을 과소 추정했다. 실행 중 생성된 미발행 wrong 후보는 종료 시 명시적으로 취소하여 descriptor를 반환한다. 성능 카운터 최적화와 이 정리는 작은 6조건에서 기존 지표·요청 기록·trace와 정확히 일치했다. 새 sweep은 한 seed의 모델 sensitivity이고 통계 신뢰구간을 제공하지 않는다.</p></html>'''
(OUT/'REPORT_KO.html').write_text(report)
print(OUT/'REPORT_KO.html')
