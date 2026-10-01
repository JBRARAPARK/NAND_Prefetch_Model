# NAND Prefetch와 AXI Outstanding 심층 분석

[한글 심층 분석 문서](NAND_AXI_Prefetch_심층분석.docx)

기존 784개 조건과 추가 72개 조건을 바탕으로 작성한 10쪽 분석입니다.
조회 지연과 시작 간격, 처리량과 응답 지연, plane 매핑, HOL 대기, 버퍼와 hit 통계의 편향을 다룹니다.

## 재현

프로젝트 루트에서 실행합니다.

```sh
.venv/bin/python docs/deep_analysis/analyze.py
.venv/bin/python docs/deep_analysis/plots.py
```

- `supplement.csv`: 보충 72개 조건의 설정과 수치
- `manifest.json`: 소스 SHA256 및 실험 개수
- `analyze.py`: 원본 모델의 Config 비교와 조회 처리율 변형 실험
- `plots.py`: 보고서 도표 재생성 및 별도 4요청 이벤트 재현

차트 재생성에는 matplotlib과 한글 글꼴이 필요합니다. 기본 그래프 글꼴은 macOS AppleGothic입니다.
기준 모델 커밋: b2914f2356e7147691cc995b43ecfc6f53d8bcfe.
