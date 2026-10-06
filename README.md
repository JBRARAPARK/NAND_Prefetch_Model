# NAND Prefetch and AXI Outstanding Model

[전체 구조 상세 설명 PDF · 20쪽](docs/architecture_details/NAND_Prefetch_Architecture_Detailed_KO.pdf) · [편집용 Word](docs/architecture_details/NAND_Prefetch_Architecture_Detailed_KO.docx) · [구성과 재현](docs/architecture_details/README.md)

[임원용 핵심 보고서 PDF](docs/executive_brief/NAND_Prefetch_Executive_Brief_KO.pdf) · [편집용 Word](docs/executive_brief/NAND_Prefetch_Executive_Brief_KO.docx)

## 4포트·512bit Host: 256GB/s 확장

[반영 사항 임원 보고 1쪽 PDF](docs/executive_multiport_256/NAND_4Port_256GBps_Executive_Brief_KO.pdf) · [편집용 Word](docs/executive_multiport_256/NAND_4Port_256GBps_Executive_Brief_KO.docx) · [전체 결과](results/multiport_256/RESULTS_KO.md)

`multiport_sim.py`는 독립 AR/R 포트 4개와 공유 NAND·버퍼를 모델링한다. 포트당 512bit·1GHz, 64B burst로 합계 상한 256GB/s다. `outstanding`, `lookup_slots`, `lookup_pipelines`는 포트당 값이다. 포트 내부 FIFO 반환을 보장하며 요청 완료는 모든 구성 burst의 최종 반환으로 집계한다. 포트 간 전역 반환 순서는 강제하지 않는다.

500MHz·조회 500ns에는 포트당 슬롯 500개, 파이프라인 2개, ready outstanding 502개를 권장한다. 501개는 lookup clock edge 정렬 대기를 제외한 경계다. 1GHz·0ns 비교 설계는 슬롯 4배·동일 파이프라인 수다. NAND 128채널·전체 page 분산 배치·포트당 outstanding 1만 개에서 후반부 256GB/s를 확인했다. 32MiB cold 읽기의 전체 평균은 초기 대기를 포함해 238.26GB/s다. 기존 GUI는 이전 단일 포트 결과다.

```sh
python3 -m unittest -q
python3 experiments/run_multiport_256.py
python3 experiments/summarize_multiport_256.py
python3 multiport_sim.py --config results/multiport_256/config_slow_ready.json --out scratch/multiport_ready
```

## 64GB/s 유지: 프리페치 판단 지연 100·200·300ns

[판단 지연·outstanding 결과](results/prefetch_decision_64/RESULTS_KO.md) · [전체 CSV](results/prefetch_decision_64/sweep.csv)

`MultiportConfig.prefetch_decision_us`는 예측 시점부터 speculative NAND 요청을 만들기까지의 판단 지연이다. Host AR 이전에 수행하므로 프리페치 선행 시간을 줄인다. `host_decision_us`는 AR 이후 조회 큐에 들어가기 전의 별도 판단 지연이며 outstanding을 점유한다. 같은 판단을 두 위치에 중복 설정하지 않는다. 두 값의 기본값 0은 기존 실행을 보존한다.

4포트 합계 64GB/s, 조회 500MHz·500ns 조건에서 예측 선행 시간을 10us 확보하면 판단 100·200·300ns 모두 outstanding 128개/포트로 후반 처리량 64GB/s를 유지한다. 판단이 AR 이후 조회 500ns에 추가되는 구조의 권장값은 각각 160·192·224개/포트다. 판단 단계는 고정 지연의 완전 파이프라인으로 가정하며 별도 판단 자원 제한과 에너지는 보정하지 않았다. 기존 PDF의 256GB/s 기본 구성과 구분되는 추가 실험이다.

```sh
python3 -m unittest -q
python3 experiments/run_prefetch_decision.py
```

## 조회 클럭·투입 간격·상대 파워 추가 비교

[클럭·에너지 임원 보고 1쪽 PDF](docs/executive_clock_power/NAND_Lookup_Clock_Power_Executive_Brief_KO.pdf) · [편집용 Word](docs/executive_clock_power/NAND_Lookup_Clock_Power_Executive_Brief_KO.docx)

[1GHz·0ns vs 500MHz·500ns 결과](results/lookup_clock_power_64b/RESULTS_KO.md) · [전체 CSV](results/lookup_clock_power_64b/sweep.csv) · [비교 그래프](results/lookup_clock_power_64b/comparison.png)

`lookup_clock_mhz`로 조회 클럭, `lookup_pipelines`로 독립 투입 파이프라인 수, `lookup_ii_cycles`로 파이프라인별 새 조회 투입 간격을 설정한다. 기존 `lookup_slots`는 조회 중인 건수를 제한한다. 클럭 기본값 `None`은 기존 동작을 유지한다. 0ns 조회도 클럭을 지정하면 투입 속도가 제한된다. 조회 클럭과 AXI 클럭은 독립적이다.

같은 슬롯·파이프라인 수에서 1GHz·0ns와 500MHz·500ns를 비교했다. AXI는 양쪽 모두 1GHz로 고정한다. `lookup_power.py`는 클럭 활성 횟수·조회·FIFO·누설·배경·AXI·NAND 에너지를 상대 단위 EU로 계산한다. 예시 계수이며 실제 장치의 W·J가 아니다. 클럭 gating과 추가 저전압 가정을 별도로 비교하고, 동일 작업량 에너지와 평균 파워를 구분한다. 기존 GUI 내장 결과는 이전 실험이다.

```sh
python3 -m unittest -q
python3 experiments/run_lookup_clock_power.py
python3 experiments/summarize_lookup_clock_power.py
```

## 유한 조회 슬롯: 병렬 hit/miss 조회 제한

[슬롯 제한 결과](results/lookup_slots_64b/RESULTS_KO.md) · [전체 CSV](results/lookup_slots_64b/sweep.csv) · [처리량·조회 대기 그래프](results/lookup_slots_64b/ready_heatmap.png)

`Config.lookup_slots`에 양의 정수를 지정하면 동시 조회 수를 제한한다. 기본 `None`은 기존 무제한 모델이다. 슬롯은 조회 시작부터 완료까지 점유하며, 대기 요청은 FIFO에서 AXI outstanding을 계속 차지한다. 슬롯 1/4/16/64/100/128/200/249/250/251/500/무제한과 outstanding 100–500을 비교한다.

64B·조회 500ns에서 슬롯 C개의 처리량 상한은 `0.128 × C GB/s`다. 256bit·1GHz AXI의 32GB/s를 유지하려면 ready hit에서 조회 슬롯 250개 이상과 outstanding 251개 이상이 함께 필요하다. 조회 슬롯은 물리 포트 수가 아닌 in-flight 조회 capacity이며, 독립적인 pipeline initiation interval은 아직 모델링하지 않는다.

```sh
python3 -m unittest -q
python3 experiments/run_lookup_slots.py
python3 experiments/summarize_lookup_slots.py
```

260개 조건, 26개 테스트. 평균·최대 조회 대기, 실제 조회 동시성, 큐 길이, AR→RLAST 응답 지연을 추가 계측한다. 기존 GUI의 내장 결과와는 별도다.

## 추가 실험: 64B AXI burst · tR 2.08µs · outstanding 100–500

[결과 분석](results/axi_64b_tr2p08/RESULTS_KO.md) · [전체 CSV](results/axi_64b_tr2p08/sweep.csv) · [처리량 그래프](results/axi_64b_tr2p08/throughput.png)

기존 `axi_burst_sim.py`에서 112개 조건을 실행했다. 기존 GUI와 같은 256bit·1GHz AXI에서 burst별 병렬 hit/miss 조회 0ns와 500ns를 비교한다. 64B는 AXI 읽기 단위이며, 64KiB logical request와 16KiB NAND page는 유지한다. Ready hit에서 500ns 조회를 숨기는 경계는 outstanding 251개다. 100개에서는 전체 처리량이 60.23%, 200개에서는 20.72% 감소했다. 상세 가정과 miss 경로 결과는 분석 문서를 참고한다. 기존 GUI 내장 데이터는 이 실험과 별개다.

```sh
python3 -m unittest -q
python3 experiments/run_64b_sweep.py
python3 experiments/summarize_64b.py
```

20개 검증 통과. 기존 4KiB 조건 16개에서 수정 전후 지표·요청 기록·이벤트 trace가 정확히 일치함을 확인했다.

[낮은 Outstanding에서 조회 지연의 성능 영향 한 장 자료](docs/execution_model/LOW_OUTSTANDING_LOOKUP_IMPACT_KO.docx) — hit 100%, 조회 0.5µs에서 O=1 처리량 79.6% 감소, O=2 59.3% 감소.

[경계값과 첫 AR → RLAST 쉬운 설명](docs/execution_model/BOUNDARY_AND_AR_RLAST_KO.md) — 0.384µs 경계, 첫 응답 512ns, 평균 약 513.5ns의 계산과 타임라인.

## GUI 바로 실행

[GUI 상세 안내](docs/execution_model/README.md) · [실행 HTML](docs/execution_model/index.html) · [21,504개 결과 데이터](docs/execution_model/data.json)

저장소를 받은 뒤 **`docs/execution_model/index.html`을 Chrome, Safari 또는 Edge로 열면** 대화 옆 패널과 같은 인터랙티브 GUI가 표시됩니다. Python 설치나 시뮬레이터 실행 없이 내장된 결과를 확인할 수 있습니다.

macOS에서는 저장소 루트에서:

```sh
open docs/execution_model/index.html
```

Windows에서는 해당 파일을 더블클릭하거나 ‘연결 프로그램’에서 브라우저를 선택합니다.

GitHub의 HTML 파일 페이지는 코드를 보여줍니다. 위 링크만 클릭해서는 GUI가 실행되지 않습니다. 파일 페이지의 **Download raw file**로 HTML을 저장한 뒤 브라우저에서 여세요. 저장소 전체를 `Code → Download ZIP`으로 받아 압축을 풀어도 됩니다.

상단의 **평균 AR → RLAST**는 전체 512burst의 AR 수락부터 RLAST 완료까지 걸린 시간의 평균입니다. 조회·데이터 준비·순서 대기·R 전송을 포함하며, AR 수락 전 대기는 제외합니다.

### GUI에서 확인할 내용

| 화면 | 확인 내용 |
| --- | --- |
| 실행 흐름 | 요청 → AR → hit 조회 → 순서 대기 → AXI R 반환, prefetch/NAND 경로; 블록 선택 시 상세 동작 |
| 칩과 page 배치 | 64KiB 요청의 4개 page와 chip·plane·channel 연결 |
| Burst 시간 관계 | 조회, page 준비 대기, 선행 반환 대기, R 전송의 실제 실행 타이밍 |
| 전체 파라미터 | 크기, 자원 수, NAND·AXI 타이밍과 고정 가정 |

상단에서 prefetch 조건, 칩·채널 배치, hit 조회 지연, outstanding을 선택합니다. 조회 지연은 0–10µs에서 0.25µs 단위이며, 0.384µs 경계값도 별도로 제공합니다. Outstanding은 1–64에서 1단위입니다. 화면은 **미리 실행한 21,504개 조합 중 선택한 결과**를 표시하며, 브라우저에서 Python 모델을 새로 실행하지 않습니다.

기본 선택은 tR 3µs, ready hit 100%, outstanding 4, 조회 지연 0.384µs입니다. 이 조회 지연은 초기 대기 이후 R 전송을 끊김 없이 이어갈 수 있는 경계입니다.


GUI는 AXI 클럭을 명시적으로 **1GHz**로 설정합니다. 256bit 폭에서 이론 상한은 **32GB/s**, 4KiB burst는 **128ns**, 64KiB R 전송 점유는 **2.048µs**입니다. NAND는 기존 4칩·4채널(또는 한 칩 집중·1채널), 채널당 2.4GB/s를 유지합니다. Ready hit 처리량과 NAND에서 지속적으로 공급하는 처리량은 다릅니다. 기존 보고서·CSV와 `Config` 기본값은 500MHz 기준이며 GUI와 구분해서 비교하세요.

## 최신 실험 tR 3µs

[한글 결과 분석](results/axi_tr3/RESULTS_KO.md) · [전체 CSV](results/axi_tr3/sweep.csv)

64KiB 요청을 4KiB AXI burst 16개로 분할하여 AR 수락부터 RLAST까지의 outstanding을 모델링합니다.
대상 정보 지연과 별도로 **burst별 hit/miss 조회 지연**을 변화시킵니다.
17개 검증 통과, 784개 비교 조건 실행. `sim.py`는 기존 page 단위 baseline으로 보존합니다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
sh run_axi.sh
```

- `axi_burst_sim.py`: burst 입장, 병렬 조회, NAND page 병합, 전역 in-order R 반환
- `experiments/run_axi_sweep.py`: tR 3µs 조건의 실험 생성
- `experiments/summarize_axi.py`: 한글 결과와 그래프 생성
- `test_axi_burst.py`: 해석식, outstanding 제한, 순서 대기, 버퍼 제한 검증

조회 자원은 병렬이고 burst별 조회를 수행하는 가정입니다. ready 조건은 사전 준비된 데이터의 상한 비교이며 예측기 품질을 검증하지 않습니다. 신호 수준 AXI 검증이나 특정 NAND 제품 사양 모델은 아닙니다.

---

# NAND Prefetch Model

64KiB low-QD AI reads: event-driven TLC sensitivity model, version 0.1.
Python 3.10+; simulator uses standard library. Plotting requires matplotlib.

## Run

```bash
cd /Users/bagjunbeom/Downloads/NAND_Prefetch_Model
python3 -m unittest -v
python3 sim.py --config config_tlc.json --out results/baseline
python3 sim.py --config config_tlc.json --out results --sweep
python3 plot_results.py
```

Edit config_tlc.json to select mapping, resource topology, prefetch policy,
knowledge delay, speculative accuracy, QD and completion mode.
All times are microseconds. Sizes are bytes. GB/s is decimal; KiB is binary.
Baseline is reproducible with seed 7. The sweep runs 160 cases, 100 requests each.

## Implemented

- 64KiB split into configurable pages; single-chip, striped-chip or seeded mixed placement.
- Configurable chip / bank / plane / channel topology. Chip is an abstract package;
  each bank is a modeled read scheduling unit. Default 1 bank per chip corresponds
  to a simplified 1 die / 1 LUN package, not a universal physical relationship.
- Independent plane sensing option, per-bank serialized command issue,
  per-channel serialized data transfer, finite page-buffer slots and controller credits.
- Cache-read overlap option; no-cache holds plane through transfer.
- tR variation, chip factors, configurable retry probability/penalty, ECC overhead.
- No prefetch, fixed lead, latency-estimate adaptive prefetch.
- Immediate/delayed target knowledge and physical mapping delay. Information
  cannot be used before its availability event. Speculation uses a candidate.
- Candidate accuracy and wasted NAND bytes; queued wrong candidates cancel,
  issued reads finish and are discarded. Correct in-flight reads merge with demand.
- Separate hit-lookup delay. Ready/late/miss is measured when lookup completes;
  prediction hit is separately recorded. Delay may change the observed readiness.
- Finite buffer credit allocation, reserved before sensing and released after
  host data return; head-request credit protection avoids ordering deadlock.
- Host demand QD admission, globally in-order requests and ascending chunk return.
- AXI transfer-time abstraction: width, clock, max burst beats, ready fraction.
  Baseline uses aligned 4KiB-or-smaller bursts, sequentially, without interleaving.
- Ordered partial consumption or full-read barrier. First usable chunk, full return,
  NPU compute finish, p95/p99, traffic and occupancy metrics plus event trace.

## Important boundaries

This is not a product timing specification, cycle-accurate AXI model, or RTL.
TLC reference: Micron 232-layer announcement documents 6 planes and independent
plane read plus 2.4GB/s NAND I/O. It does not establish our 16KiB page, 50us tR,
4 chips, page-buffer slots or command/ECC timings: those are model assumptions.
https://investors.micron.com/news/press-release/2022/Micron-Ships-Worlds-First-232-Layer-NAND-Extends-Technology-Leadership-07-26-2022/default.aspx

NAND I/O 2.4GB/s is configured per shared channel, not per plane. Host AXI
bandwidth is independently configured. zNAND-O 200–400GB/s and sub-3us latency
are not applied to this TLC profile. Adaptive uses an estimate, not the actual
sampled tR; queue predictions are approximate. Adaptive is not claimed optimal.

Buffer occupancy reports reserved + resident controller credits, including
reads in flight; it is not just resident SRAM data. The mean includes warmup from
simulation time zero. Latency includes host admission wait and final AXI return;
no-prefetch therefore still reflects target-known and mapping delays if late.
Host QD excludes speculative outstanding work. Speculation uses one candidate
per request; it does not represent multi-candidate MoE top-k yet.

AXI ready fraction models average throughput reduction, not a specific READY
waveform. AR/R handshakes, IDs, errors and reset behavior are not pin modeled.
Request-level global order is the requested design constraint. Partial is page
granular and error-checked before return; no reordering to first-ready arbitrary data.

## Next fidelity extensions

1. Bank-to-die/LUN explicit map and target-dependent chip assignment.
2. TLC lower/middle/upper page distribution, block/page geometry and multi-plane
   same-row restrictions; independent plane mode currently abstracts those away.
3. Per-channel command/data bus sharing and detailed cache-read protocol timings.
4. Actual AXI READY traces, AR queue timing, boundary/unaligned requests and IDs.
5. Buffer eviction / TTL and confidence admission; baseline retains correct pages.
6. Trace-driven AI compute/dependency, multi-candidate experts, predictor updates.
7. Background program/erase/GC and power/energy. Baseline is read only.

## Validation

Eight tests cover analytic shared/independent transfer, serial sensing,
in-order return at QD4, finite-buffer credit limits, delayed address availability,
wrong-speculation traffic, lookup delay and prefetched readiness.
Tests validate the model equations and invariants, not real NAND behavior.


## 심화 모델링 중간 결과와 설계 검토

[Blind spot 상세 검토 PDF](docs/deep_prefetch_review/NAND_Prefetch_Blind_Spot_상세검토.pdf) · [편집 가능한 Word](docs/deep_prefetch_review/NAND_Prefetch_Blind_Spot_상세검토.docx)

21쪽 상세 자료는 13개 blind spot, 지표 정의, 반례 테스트와 후속 구현 순서를 정리한다. 코드 검토 기준은 `4d3bb3f0eba163f0b44dd193b1db5b65958bf739`이며, 기존 측정·이론 추정·미실행 실험 제안을 구분한다. 이 문서 추가 과정에서 새 시뮬레이션은 실행하지 않았다.

[검토 현황과 미완료 항목](docs/deep_prefetch_review/STATUS_KO.md) · [한국어 결과 보고서](results/deep_prefetch/REPORT_KO.html) · [103조건 CSV](results/deep_prefetch/sweep.csv) · [재현 안내](results/deep_prefetch/README.txt)

기준 커밋 bf63379의 기존 결과 재현과 **합성 prefetch 민감도 분석**까지 완료했다. 코드·CSV의 `online`은 미래 요청과 도착 시각을 알고 host 실행 중에 발행하는 합성 모델이다. 실제 과거 관측만 사용하는 인과적 예측기는 아직 구현·검증하지 않았다. 잘못된 예측을 ready 시 즉시 폐기하는 oracle 가정도 남아 있다.

동일 host credit 비교와 `same_total` 비교를 분리했지만, 후자는 64B AR credit과 16KiB speculative page descriptor를 각각 1개로 더한 **혼합 토큰 예산**이다. 동일 unique-page 수나 동일 하드웨어 비용 비교로 해석할 수 없다. 56개 테스트(기존 50개 + 추가 6개) 통과는 현재 모델의 검증이며 상세 설계 요구 전체의 검증 완료를 뜻하지 않는다.

측정한 512 host request demand-only 실행에서 O=8,000은 후반 210.77GB/s, O=10,000은 256GB/s였다. O=10,000·2.5MiB 버퍼에서 중간·후반 256GB/s를 관측했다. 이는 유한 실행의 모델 결과이며 정밀 포화 경계나 실제 SRAM·에너지 비용의 측정은 아니다. 64GB/s 입력 제한과 최대 공급 실험, 준비 시간과 종료 효과는 보고서에서 구분한다.

```sh
python3 -m unittest -q
python3 experiments/run_deep.py
python3 experiments/run_deep_extra.py
python3 experiments/run_buffer_boundary.py
MPLCONFIGDIR=/tmp/nand-mpl .venv/bin/python experiments/summarize_deep.py
```
