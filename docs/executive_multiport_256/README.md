# 4포트·512bit 모델 확장 임원 보고

- [공유용 1쪽 PDF](NAND_4Port_256GBps_Executive_Brief_KO.pdf)
- [편집용 Word](NAND_4Port_256GBps_Executive_Brief_KO.docx)
- [미리보기](preview.png)
- [모델 반영 사항과 전체 실험](../../results/multiport_256/RESULTS_KO.md)

표는 `results/multiport_256/sweep.csv`에서 생성한다. Host 256GB/s 상한과 NAND 공급 조건을 구분하고, 초기 대기를 포함한 전체 평균·후반부 처리량을 함께 표시했다. 조회 클럭 정렬을 반영해 ready-hit outstanding 권장값을 포트당 502개로 보정했다.

PDF는 1쪽·한글·주요 수치를 검증한다. Word 페이지 나눔은 글꼴과 편집기에 따라 달라질 수 있다. 재생성은 저장소 루트에서 `python3 docs/executive_multiport_256/build_report.py`를 실행한다. 기존 클럭·파워 보고서의 한글 문서 레이아웃을 재사용한다. `evidence.json`은 데이터와 생성 코드의 SHA256을 기록한다.
