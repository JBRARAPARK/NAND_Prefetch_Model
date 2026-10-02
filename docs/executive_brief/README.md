# NAND 프리페치 임원용 핵심 보고서

2026년 10월 2일 기준 유한 조회 슬롯 실험의 핵심 결과와 설계 의사결정 제안이다.

- [공유용 1쪽 PDF](NAND_Prefetch_Executive_Brief_KO.pdf)
- [편집 가능한 Word](NAND_Prefetch_Executive_Brief_KO.docx)
- [PDF 미리보기](preview.png)

근거는 `results/lookup_slots_64b/sweep.csv`와 소스 commit `55e06c353480aa11da70156dad4324700f773bb0`의 결과 보고서다. 표 수치는 CSV에서 읽어 생성한다. PDF의 1쪽 분량, 주요 수치, 한글 글꼴과 표 레이아웃을 확인했다. Word의 최종 페이지 나눔은 설치된 글꼴과 편집기에 따라 달라질 수 있다.

재생성은 저장소 루트에서 `python3 docs/executive_brief/build_report.py`를 실행한다. 문서 생성 의존성은 `python-docx`, `reportlab`, `PyMuPDF`다. PDF는 Google Fonts의 Nanum Gothic 글꼴을 임시 폴더에 내려받아 포함한다. [글꼴과 OFL 라이선스](https://github.com/google/fonts/tree/main/ofl/nanumgothic).
