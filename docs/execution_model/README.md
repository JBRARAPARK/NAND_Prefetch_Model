# NAND–AXI 실행 모델 다이어그램

`index.html`을 브라우저에서 열면 실행 흐름, 칩·page 배치, burst 타이밍, 전체 파라미터를 확인할 수 있습니다. 파일에 결과와 화면 동작을 포함했습니다.

## GUI 열기

- macOS: 저장소 루트에서 `open docs/execution_model/index.html`
- Windows: `index.html`을 더블클릭하거나 브라우저로 열기
- GitHub: HTML 파일 페이지에서 **Download raw file**로 내려받은 뒤 브라우저로 열기. GitHub 코드 화면에서는 GUI가 실행되지 않습니다.

네 탭은 실행 흐름, 칩과 page 배치, burst 시간 관계, 전체 파라미터입니다. 실행 흐름의 블록을 선택하면 세부 동작을 볼 수 있습니다. 상단의 네 선택 항목을 바꾸면 내장된 실행 결과와 타이밍이 바뀝니다.

GUI는 21,504개 조합의 결과를 탐색하는 화면입니다. 선택할 때 Python을 실행하지 않으며, 임의의 파라미터를 입력해 새 결과를 계산하는 기능은 포함하지 않습니다.

## 실행 조건

- 32 × 64KiB 동시 요청, tR 3µs, 16KiB page, 4KiB AXI burst
- 256bit / 1GHz AXI, 병렬 hit 조회, 전역 in-order 반환
- Prefetch 4종 × 배치 2종 × outstanding 64종(1–64, 1단위) × 조회 지연 42종(0–10µs, 0.25µs 간격 + 0.384µs) = 21,504개 실행 결과
- 초기 선택: ready, 4칩·4채널, outstanding 4, 조회 지연 0.384µs
- 타임라인은 요청 0의 burst 0–7과 요청 1의 burst 16–17을 표시합니다.

## 데이터 재생성

저장소 루트에서 다음을 실행합니다.

```sh
python3 docs/execution_model/generate_data.py
python3 docs/execution_model/update_html.py
```

`generate_data.py`는 4개 프로세스로 모델을 실행해 `data.json`을 생성합니다. `update_html.py`는 결과와 조회 지연 선택값을 HTML에 반영합니다. 두 명령을 실행한 뒤 브라우저를 새로고침하세요. 클럭 등 실행 설정이 바뀌었을 때 이전 결과가 섞이지 않도록 매번 전체 조건을 새로 계산합니다.

Ready 조건의 0.384µs 경계는 초기 대기 이후 연속 R 전송이 가능한 한계입니다. 유한한 전체 요청의 처리량에는 초기 조회 대기가 포함됩니다. NAND tR 3µs는 내부 sensing 시간이며 NAND 데이터 전송·ECC·AXI 반환 시간은 별도입니다.

GUI는 AXI 클럭을 명시적으로 **1GHz**로 설정합니다. 256bit 폭에서 이론 상한은 **32GB/s**, 4KiB burst는 **128ns**, 64KiB R 전송 점유는 **2.048µs**입니다. NAND는 기존 4칩·4채널(또는 한 칩 집중·1채널), 채널당 2.4GB/s를 유지합니다. Ready hit 처리량과 NAND에서 지속적으로 공급하는 처리량은 다릅니다. 기존 보고서·CSV와 `Config` 기본값은 500MHz 기준이며 GUI와 구분해서 비교하세요.
