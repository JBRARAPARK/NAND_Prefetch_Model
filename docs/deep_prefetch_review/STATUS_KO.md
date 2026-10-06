# NAND Prefetch 심화 모델링 검토 현황

검토일: 2026-10-06. 재현 기준: `bf63379b7587b63e01925730f123f37a1ec33bdf`.

현재 완료 범위는 **기존 결과 재현, 합성 예측 민감도 실험, 설계 검토**이다. 실제 인과적 online predictor와 동일 하드웨어 비용에서의 우위는 아직 검증하지 않았다. 제공된 「NAND_Prefetch_심화_설계검토」 문서를 검토 자료로 사용했으며, 문서에 제안된 구현 항목을 완료된 작업으로 취급하지 않는다.

## 완료한 작업과 측정 결과

- 기존 모델을 보존하고 별도 `deep_prefetch_sim.py`, 테스트 6개, 단계별 runner 및 단일 조건 replay를 추가했다.
- 기존 4조건과 새 99조건, 합계 103조건을 실행했다. CSV·설정·실행 전 추정·소스 해시·그래프·한국어 보고서를 보존한다. 완료 행의 runtime 합계 약 413.75초는 개발 중 카운터 변경을 포함하므로 동일 최종 소스로 한 번에 실행한 시간은 아니다.
- 기존 O=502 demand-only/ready 전체 평균은 13.408/252.145GB/s, O=10,000은 197.265/252.145GB/s였다. 이는 128 host request 실행이며 ready 준비 시간은 host 구간 처리량에서 제외된다.
- 새 512 host request demand-only 실행에서 O=8,000은 후반 210.77GB/s, O=10,000은 중간·후반 256GB/s였다. O=10,000의 버퍼 2/2.25/2.5MiB에서 후반은 각각 225.000/252.770/256GB/s였다. 측정한 지점 사이의 정밀 경계와 무한 정상상태는 확인하지 않았다.
- 56개 테스트(기존 50개 + 추가 6개)는 현재 모델의 credit 상한, page 병합, 반환 수·순서, 버퍼 및 drain 등을 검증한다. 과거 관측만으로의 예측, 재사용 page 수명, 실제 AXI/RTL 전체의 검증은 포함하지 않는다.

Outstanding은 **포트당 64B AXI burst의 AR 수락부터 RLAST까지 점유하는 credit**이다. 이 구성에서 64KiB host request 하나는 1,024 burst, 16KiB NAND page 4개다. Host request 개수와 AXI credit 수를 혼용하지 않는다.

## 기존 표현의 정정

| 코드·CSV 이름 | 현재 실제 의미 | 아직 주장할 수 없는 것 |
| --- | --- | --- |
| `demand` | AR 수락에 따라 NAND 읽기가 시작되는 기존 demand 경로 | 이미 알려진 64KiB 요청을 조기에 발행하는 최선의 demand 구현 |
| `ready` | 미래 요청을 알고 host 전에 미리 읽을 시간을 준 이상적 준비 비교 | 준비 비용 없는 실제 시스템 성능 |
| `online` | 미래 요청 ID·시각으로 후보를 만들되 실행은 첫 host 도착 이후로 제한한 합성 모델 | 과거 관측만으로 예측하는 인과적 online predictor |
| `same_total` | host 64B AR credit과 speculative 16KiB page descriptor를 각각 1로 합산한 예산 | 동일 unique-page 예산 또는 동일 SRAM/하드웨어 비용 |
| `end_to_end_gbps` | ready 사전 lead부터 마지막 demand 완료까지의 처리량 | 마지막 speculative drain까지 포함한 whole-job 처리량 |

호환성과 재현을 위해 기존 case/column 이름 및 수치 데이터는 유지한다. 보고서·그래프에는 합성 모델과 혼합 토큰이라는 한계를 표시한다.

현재 `wrong` 표시는 실제 미래 사용 여부를 알고 만들어지며, 잘못된 page를 ready 시점에 바로 폐기하는 제어에도 쓰인다. 따라서 오류 예측의 체류 시간·버퍼 부담을 낙관적으로 만들 수 있다. 단순히 예측기만 바꾸어서는 인과성이 확보되지 않으며, 폐기·피드백·admission도 함께 고쳐야 한다.

현재 demand queue age는 후보 생성부터 issue까지이므로 demand 승격 전 시간도 섞인다. 기아는 발행된 후보의 최대 대기만으로 판정할 수 없고 미발행·drop·누적 대기도 봐야 한다. 실제 demand로 알려진 시각 이후의 순수 추가 지연과 유한 관측에서의 기아를 별도로 정의해야 한다.

## 설계에서 놓치기 쉬운 지점

1. **주소가 언제 누구에게 보이는가.** Controller가 64KiB 요청 주소를 이미 아는 시점이라면 AR credit과 독립적으로 알려진 demand를 먼저 읽을 수 있다. 기존 AR 기반 demand, 알려진 demand 조기 발행, 미래 주소 예측을 구분해야 이득의 원인을 가릴 수 있다. 재사용 실험에는 동일 cache/eviction 정책의 demand 기준선도 필요하다.
2. **64B burst와 포트 전체 FIFO는 모델의 선택이다.** 제품의 실제 burst 길이·AXI ID·ordering 계약을 확인해야 한다. 64KiB를 64B로 나누면 1,024 burst, 4KiB로 나누면 16 burst이므로 credit 개수의 의미가 크게 바뀐다. 현재 결과는 기존 64B/FIFO 구성을 위한 기준점으로 보존한다.
3. **예측 정확도, coverage, lead는 서로 다르다.** 후보 생성 정확도와 실제 발행 precision, page timely coverage와 요청 전체 readiness를 분리한다. 실제 예측기가 동시에 달성할 수 있는 조합인지 확인해야 하며 독립적인 합성 파라미터 조합만으로 가능성을 입증할 수 없다.
4. **버퍼 용량만으로 데이터 경로를 검증할 수 없다.** 예약 용량, resident SRAM, NAND 내부 latch를 구분한다. 256GB/s 유효 데이터를 SRAM에 한 번 쓰고 한 번 읽는다면 합산 512GB/s 트래픽이 필요하다는 것은 이론적 계산이다. Bank/port 충돌과 읽기·쓰기 동시 처리량은 아직 측정하지 않았다.
5. **평균과 tail·종료 비용은 다른 지표다.** NAND/ECC 지연 변동, RREADY stall, 오류의 군집성, post-demand drain까지 포함한 whole-job 자원·에너지를 추가해야 한다. 현재 요청 분위수는 결정론적 서비스와 제한된 workload에서 얻은 값이다.
6. **동일 seed만으로 동일 외부 조건을 보장하지 않는다.** Prefetch 유무가 난수 소비 순서를 바꾸면 demand service draw도 바뀔 수 있다. 서비스 시간·예측 오류의 스트림을 분리하거나 외부 scenario를 사전에 고정해야 한다. 현재 서비스 시간은 고정이며 이 항목은 변동 모델 확장 시 요구사항이다.
7. **입력 방식과 관측 창을 고정해야 한다.** 64GB/s open-loop pacing과 완료에 의존하는 closed-loop workload를 구분하고 backlog 변화도 기록한다. 완료 수로 자른 후반 구간의 64GB/s 초과는 backlog 해소일 수 있다. 실행 길이·시간창을 늘려 지속성을 다시 확인해야 한다.

## 후속 구현 및 검증 순서 — 미완료

1. 주소 공개 시점, request/page/AR credit, cache와 ordering 계약을 고정하고 알려진 demand 조기 발행 기준선을 추가한다. P99·허용 낭비·면적/전력 예산의 목표도 결정한다.
2. Canonical physical page·version·refcount, 중복 병합, 만료·안전한 eviction, demand 승격·취소·drain 수명주기를 구현한다. 미래 사용 여부를 제어에서 제거한다.
3. `observe/predict/feedback`의 인과적 경계를 구현하고 동일 prefix/서로 다른 suffix 실행에서 예측·admission·eviction·반환 결정의 인과성을 테스트한다. Decision latency와 II 및 처리 용량을 따로 반영한다.
4. AR credit, unique-page descriptor, resident/reserved bytes를 별도 계수한다. 동일 host outstanding 비교와 동일 실제 전체 자원 비용 비교를 다시 설계한다.
5. 작은 smoke test → 단계별 workload·정확도·lead·정책 sweep → 긴 실행·다중 seed 순으로 진행한다. 조합 수와 runtime 추정을 갱신한 후 확장한다. Demand 지연과 prefetch 기아, backlog·공정성·whole-job 비용을 함께 측정한다.

이 단계는 계획이며 아직 실행 결과가 없다. 현재 103조건으로 후속 구현의 결과를 대신하지 않는다.

## 데이터 및 소스 보존

[실행 안내](../../results/deep_prefetch/README.txt), [결과 CSV](../../results/deep_prefetch/sweep.csv), [구성](../../results/deep_prefetch/configs.json), [보고서](../../results/deep_prefetch/REPORT_KO.html)를 함께 확인한다.

검토 정정은 모델의 수치 연산을 바꾸지 않고 설명·표시를 수정한다. 측정 당시 `manifest.json`과 CSV/configs는 보존하고, 이번 정정으로 해시가 달라진 소스의 원본은 `results/deep_prefetch/provenance/measurement_sources/`에 둔다. `review_manifest.json`은 이번 검증과 변경 후 소스 해시를 별도로 기록한다. 기존 103조건 전체를 새로 실행한 것으로 표시하지 않는다.

## Blind spot 상세 고찰 자료

[21쪽 PDF](NAND_Prefetch_Blind_Spot_상세검토.pdf)와 [편집 가능한 Word](NAND_Prefetch_Blind_Spot_상세검토.docx)에 13개 blind spot을 상세히 정리했다. 주소 공개 시점과 인과성, 자원 예산의 동등성, page 수명주기, 예측 품질과 대역폭·버퍼 비용, AXI 순서 및 관측 창을 다루며, 지표 정의·단계별 실험안·반례 테스트·후속 구현 순서를 포함한다.

검토 대상 코드는 `4d3bb3f0eba163f0b44dd193b1db5b65958bf739`로 고정했다. 기존 103조건 측정, 이론 계산, 아직 실행하지 않은 제안을 구분하며 이 문서 추가로 새 측정 결과가 생긴 것은 아니다. 우선 3~6장과 19장의 설계 결정 사항을 검토한다.
