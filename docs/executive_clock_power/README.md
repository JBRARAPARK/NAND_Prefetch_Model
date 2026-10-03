# 조회 클럭·에너지 임원 보고

2026년 10월 3일 기준 1GHz·조회 0ns와 500MHz·조회 500ns의 동일 병렬성 비교를 한 장으로 정리했다.

- [공유용 1쪽 PDF](NAND_Lookup_Clock_Power_Executive_Brief_KO.pdf)
- [편집용 Word](NAND_Lookup_Clock_Power_Executive_Brief_KO.docx)
- [미리보기](preview.png)
- [전체 결과와 모델 가정](../../results/lookup_clock_power_64b/RESULTS_KO.md)

표는 `results/lookup_clock_power_64b/sweep.csv`에서 읽어 생성한다. 기준은 각 행과 같은 슬롯 수의 1GHz·0ns·1V 설계이며 양쪽 모두 clock gating을 적용한다. 파워·에너지는 예시 EU 계수에 따른 상대 결과이고 장치 실측 W·J가 아니다. PDF의 1쪽 분량, 주요 수치와 한글 표시를 검증했다. Word 페이지 나눔은 설치 글꼴과 편집기에 따라 달라질 수 있다.

재생성: 저장소 루트에서 `python3 docs/executive_clock_power/build_report.py`. 의존성은 `python-docx`, `reportlab`, `PyMuPDF`다. PDF에는 [Nanum Gothic 글꼴](https://github.com/google/fonts/tree/main/ofl/nanumgothic)을 포함한다. `evidence.json`은 CSV·manifest·생성 스크립트의 SHA256과 표 수치를 보관한다.
