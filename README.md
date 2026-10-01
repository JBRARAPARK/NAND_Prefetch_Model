# NAND Prefetch and AXI Outstanding Model

## GUI 바로 실행

[GUI 상세 안내](docs/execution_model/README.md) · [실행 HTML](docs/execution_model/index.html) · [21,504개 결과 데이터](docs/execution_model/data.json)

저장소를 받은 뒤 **`docs/execution_model/index.html`을 Chrome, Safari 또는 Edge로 열면** 대화 옆 패널과 같은 인터랙티브 GUI가 표시됩니다. Python 설치나 시뮬레이터 실행 없이 내장된 결과를 확인할 수 있습니다.

macOS에서는 저장소 루트에서:

```sh
open docs/execution_model/index.html
```

Windows에서는 해당 파일을 더블클릭하거나 ‘연결 프로그램’에서 브라우저를 선택합니다.

GitHub의 HTML 파일 페이지는 코드를 보여줍니다. 위 링크만 클릭해서는 GUI가 실행되지 않습니다. 파일 페이지의 **Download raw file**로 HTML을 저장한 뒤 브라우저에서 여세요. 저장소 전체를 `Code → Download ZIP`으로 받아 압축을 풀어도 됩니다.

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
