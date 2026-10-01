# NAND–AXI 실행 모델 다이어그램

`index.html`을 브라우저에서 열면 실행 흐름, 칩·page 배치, burst 타이밍, 전체 파라미터를 확인할 수 있습니다. 파일에 결과와 화면 동작을 포함했습니다.

## 실행 조건

- 32 × 64KiB 동시 요청, tR 3µs, 16KiB page, 4KiB AXI burst
- 256bit / 500MHz AXI, 병렬 hit 조회, 전역 in-order 반환
- Prefetch 4종 × 배치 2종 × outstanding 7종 × 조회 지연 7종 = 392개 실행 결과
- 초기 선택: ready, 4칩·4채널, outstanding 4, 조회 지연 0.768µs
- 타임라인은 요청 0의 burst 0–7과 요청 1의 burst 16–17을 표시합니다.

## 데이터 재생성

저장소 루트에서 다음을 실행합니다.

```sh
python3 docs/execution_model/generate_data.py
```

`data.json`은 모델을 다시 실행한 결과입니다. HTML은 작성 시점의 결과를 내장한 스냅샷이므로 JSON 재생성만으로 화면이 갱신되지는 않습니다.

Ready 조건의 0.768µs 경계는 초기 대기 이후 연속 R 전송이 가능한 한계입니다. 유한한 전체 요청의 처리량에는 초기 조회 대기가 포함됩니다. NAND tR 3µs는 내부 sensing 시간이며 NAND 데이터 전송·ECC·AXI 반환 시간은 별도입니다.
