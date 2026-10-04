# NAND 프리페치 모델 전체 구조 설명자료

2026-10-04 기준 상세 설계 설명자료다. 모델 구현 commit은 `ee8636d53db93bcbe6a26025ef9cc0e939a55ac6`이며 최신 판단 지연 100·200·300ns와 64GB/s outstanding 조건을 포함한다.

- [읽기용 PDF · 20쪽](NAND_Prefetch_Architecture_Detailed_KO.pdf)
- [편집용 Word](NAND_Prefetch_Architecture_Detailed_KO.docx)
- [전체 페이지 미리보기](preview_all_pages.png)
- [원본 구성·본문·표](content.json), [선택한 원본 CSV 행·hash·검증 기록](evidence.json)

| 쪽 | 내용 |
|---|---|
| 1–4 | 설계 결론, 전체 블록 구조, 요청·page·burst·포트 관계, hit·late·miss 흐름 |
| 5–7 | 선행 프리페치와 실제 burst 타이밍, 판단 위치, 조회 지연·슬롯·lane·outstanding |
| 8–10 | NAND 상태와 자원 해제, 주소 배치·채널 확장·내부 연결, buffer·순서·진행 보호 |
| 11–13 | 최대 256GB/s 검증, 64GB/s 유지 요청 창, 판단 지연 100·200·300ns 결과 |
| 14–15 | 평균 파워·총 에너지 계산과 상대 비교 결과 |
| 16–18 | 소스 계층, 테스트·측정·재현, 구현 범위와 다음 검증 |
| 19–20 | 현재 코드 기본값 전체 파라미터와 실험 override |

## 주요 수치

모든 outstanding은 64B burst의 포트당 수다. 처리량은 4포트 합계이며 전체 평균과 후반 평균을 구분한다.

- 최대 성능: ready 502개/포트, NAND 공급은 128채널·10,000개/포트에서 후반 256GB/s 확인.
- 64GB/s 유지 권장: ready 128개/포트·합계 512개, cold 2,560개/포트·합계 10,240개.
- 예측 lead 10µs의 선행 판단: 100·200·300ns 모두 ready hit와 128개/포트 유지.
- AR 이후 추가 판단: 100·200·300ns에서 160·192·224개/포트 권장.
- Fast 슬롯은 slow의 4배. Ready slow의 에너지는 같은 전압에서 fast의 76.3%, 0.8V 가정에서 55.8%. 평균 파워비는 각각 75.2%·54.9%이며 에너지비와 구분한다.

## 제작·검증

`content.py`가 공통 본문을 구성하고 `build_report.py`가 PDF·Word·그림·content.json·evidence.json을 생성한다. PDF의 20개 챕터·책갈피·출력 범위, Word의 23개 표와 7개 그림, 원본 행과 source hash를 확인했다. Word를 LibreOfficeDev로 PDF 렌더링해 20쪽과 본문·표를 추가 확인했다. 다른 편집기에서는 글꼴·페이지 배치가 달라질 수 있다.

```sh
python3 docs/architecture_details/build_report.py
python3 docs/architecture_details/verify_report.py
```

Word 실제 렌더링을 함께 검사하려면 다음과 같이 실행한다. 출력 폴더는 저장소 밖에 둔다.

```sh
mkdir -p /tmp/nand-architecture-word
soffice --headless --convert-to pdf --outdir /tmp/nand-architecture-word docs/architecture_details/NAND_Prefetch_Architecture_Detailed_KO.docx
python3 docs/architecture_details/verify_report.py --word-rendered-pdf /tmp/nand-architecture-word/NAND_Prefetch_Architecture_Detailed_KO.pdf
```

제작 의존성은 `reportlab`, `python-docx`, `pymupdf`, `matplotlib`, `pillow`다. PDF는 NanumGothic 글꼴을 내장하며, 없는 경우 Google Fonts의 NanumGothic TTF를 `/tmp/nand-executive-fonts`에 내려받는다. 글꼴 출처와 라이선스는 [Google Fonts NanumGothic](https://github.com/google/fonts/tree/main/ofl/nanumgothic)의 SIL Open Font License를 따른다. Word 본문은 맑은 고딕을 지정하고 그림에는 한글을 포함해 저장한다.

`assets/`에는 구조·흐름·상태·타이밍 도식의 PDF/PNG와 성능·outstanding·에너지 그래프의 SVG/PNG를 보관한다. 도식 PDF와 그래프 SVG는 별도 발표 자료에 사용할 수 있다.

이번 변경은 설명자료 제작이며 시뮬레이터 동작·기존 실행 결과·GUI·기존 임원용 PDF를 바꾸지 않는다. 구현하지 않은 predictor 정확도, 판단 resource cap, AR rate limiter, NAND 제품·PHY·fabric의 실제 전력은 본문에서 후속 검증 항목으로 구분했다.
