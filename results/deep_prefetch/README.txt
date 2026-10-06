NAND 심화 실험 실행 안내

상태: 기존 결과 재현 + 합성 예측 민감도 실험 + 설계 검토.
중요: online은 미래 요청 ID/시각을 아는 합성 모델입니다. 실제 인과적 예측기가 아니며
wrong page를 ready 시 즉시 폐기하는 oracle 가정이 남아 있습니다.
same_total은 64B AR credit과 16KiB page descriptor를 각각 1로 더한 추상 혼합
토큰 예산입니다. 동일 unique-page 수 또는 동일 하드웨어 비용으로 해석하지 마세요.
상세 검토·미완료 항목: docs/deep_prefetch_review/STATUS_KO.md (저장소 루트 기준).

저장소 기준: bf63379b7587b63e01925730f123f37a1ec33bdf
코드: deep_prefetch_sim.py
검증: test_deep_prefetch.py 및 기존 test_*.py
결과 보고서: REPORT_KO.html (동일 폴더의 PNG와 함께 보관)

실행 위치: 저장소 루트 (NAND_Prefetch_Model)
1. python3 -m unittest -q
2. python3 experiments/run_deep.py
3. python3 experiments/run_deep_extra.py
4. python3 experiments/run_buffer_boundary.py
5. MPLCONFIGDIR=/tmp/nand-mpl .venv/bin/python experiments/summarize_deep.py

시뮬레이션과 테스트는 Python 표준 라이브러리를 사용하며 그래프에는 matplotlib이 필요합니다.
처음 실행하는 시스템에서는
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
이후 .venv/bin/python으로 위 명령을 실행하세요.

NAND_RESUME=1 python3 experiments/run_deep.py
는 완료된 case 이름을 건너뜁니다. 다른 코드·설정의 결과를 이어 붙이지 않도록
이름만 확인하고 소스 해시를 자동 검증하지 않습니다.
코드/설정을 변경했으면 기존 결과를 백업한 뒤 resume 없이 새로 실행하세요.
보충 runner는 extra_ case를 교체하여 중복 행을 만들지 않습니다.
기본 runner는 기존 legacy 결과 폴더를 수정하지 않습니다.

sweep.csv: 모든 측정 조건의 집계 지표
configs.json: case별 전체 dataclass 설정
manifest.json: 측정 당시 소스 SHA256, 기준 커밋, 완료된 조건 runtime 합계
review_manifest.json: 설명 정정 후 소스 해시, 데이터 보존 확인, 이번 테스트 결과
provenance/measurement_sources/: 이번 설명 정정으로 해시가 바뀐 소스의 측정 당시 사본
estimate.json: 최초 4조건 측정 후 본 sweep 전에 생성한 시간 추정
validation.json: 테스트와 계측 자료 구조 검증 기록

throughput_gbps는 host 구간만, end_to_end_gbps는 ready의 사전 lead까지 포함합니다.
둘 다 마지막 demand 완료가 분모의 끝이며 post-demand drain은 제외합니다.
drain_us는 별도 기록하므로 end_to_end_gbps를 whole-job 처리량으로 해석하지 마세요.
Ready의 10,000us lead에는 유휴 slack이 있으므로 active 준비 span도 함께 보세요.
부정확한 예측·입력 제한·동시 일괄 도착을 혼동하지 마세요.
GB/s는 decimal, KiB/MiB는 binary, 시간은 us입니다.

특정 측정 조건 재실행과 요청별 CSV:
python3 experiments/replay_deep_case.py --case host_1.024_502_online_False --out scratch/deep_replay
--trace를 추가하면 AR/lookup/NAND/RLAST 이벤트 CSV도 저장합니다. 긴 실행 trace는 파일이 커집니다.

이번 검토 정정에서는 103조건 CSV/configs와 수치 연산을 바꾸지 않았습니다.
56개 테스트는 기존 50개+추가 6개이며 상세 설계 요구 전체의 검증 완료가 아닙니다.
전체 sweep 명령은 CSV/configs 및 manifest를 갱신하므로 보존할 결과는 먼저 복사하세요.
기록된 runtime은 개발 중 카운터 구현 변경을 포함하며 단일 최종 소스 배치 시간이 아닙니다.
