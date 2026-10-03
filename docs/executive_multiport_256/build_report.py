"""Source-backed one-page brief for the 4-port 512-bit model upgrade."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from docx import Document

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
CSV=ROOT/'results/multiport_256/sweep.csv'
MANIFEST=ROOT/'results/multiport_256/manifest.json'
TEMPLATE=ROOT/'docs/executive_clock_power/build_report.py'


def main():
    spec=importlib.util.spec_from_file_location('executive_layout',TEMPLATE)
    brief=importlib.util.module_from_spec(spec);spec.loader.exec_module(brief)
    brief.OUT=OUT
    brief.STEM='NAND_4Port_256GBps_Executive_Brief_KO'
    brief.TITLE='4포트·512bit 기반 256GB/s 확장 검토'
    brief.SUBTITLE='임원 보고  |  2026년 10월 3일  |  모델 업그레이드 반영 결과'
    brief.LEAD='Host 256GB/s를 확인했으며, NAND 공급에는 채널·요청창 확장이 필요합니다.'
    brief.SUMMARY='512bit·1GHz 독립 포트 4개를 구현했습니다. 기존 64B 읽기를 유지하면서 포트별 요청·조회·반환을 병렬화하고, NAND는 128개 독립 채널과 전체 page 분산 배치로 확장했습니다.'
    brief.HEADERS=['실행 조건','작업량\nMiB','전체 평균\nGB/s','후반부\nGB/s']
    brief.TABLE_NOTE='Ready는 데이터 사전 준비, NAND는 프리페치 없는 읽기입니다. Ready의 요청창은 포트당 502개, 표의 NAND 조건은 포트당 1만 개입니다. NAND 행은 모두 500MHz·조회 500ns입니다.'
    brief.TERMS='전체 평균은 첫 요청 수락부터 마지막 반환까지이며 초기 대기를 포함합니다. 후반부는 전체 burst 절반이 완료된 이후의 공통 시간창입니다. 이는 유한 실행 결과입니다.'
    brief.INSIGHT='NAND 128채널이어도 요청창을 포트당 502개로 제한하면 전체 평균은 13.41GB/s입니다. 채널 확대와 충분한 미완료 요청 수 확보가 함께 필요합니다.'
    brief.DECISIONS=[
        ('조회·Host 자원', '500MHz 경로는 포트당 조회 슬롯 500개·파이프라인 2개를 사용합니다. 클럭 정렬 대기를 반영해 ready 요청창은 앞선 501개에서 502개로 보정했습니다. 4포트 합계는 슬롯 2,000개·요청창 2,008개입니다.'),
        ('NAND 공급 조건', '채널당 2.4GB/s × 128채널 = 원시 307.2GB/s입니다. page 분산 배치와 포트당 요청창 1만 개에서 후반부 256GB/s를 확인했습니다. 기존 주소 배치의 전체 평균은 64.31GB/s에 그칩니다.'),
        ('전력 비교 조건', '1GHz·0ns 경로는 슬롯을 4배(포트당 2,000개)로 두고 파이프라인 수는 같습니다. 예시 계수의 ready 에너지는 500MHz 동일 전압에서 기준의 76.3%, 0.8V 가정에서 55.8%입니다.')]
    brief.GATING='반환 순서는 포트 내부에서 보장하고 포트 간 전역 순서는 강제하지 않습니다. 한 요청은 네 포트에 나뉜 모든 burst가 끝난 뒤 완료됩니다. NAND page 읽기와 버퍼는 공유합니다.'
    brief.SCOPE='모델 조건: NAND 128chip·128channel·chip당 6plane, page 16KiB, tR 2.08µs, controller buffer 8MiB. 내부 연결과 버퍼가 합계 256GB/s의 읽기를 처리할 수 있다고 가정합니다.'
    brief.LIMIT='판단 범위: 실제 제품·PHY·내부 연결의 실측이 아닙니다. 파워는 예시 EU 계수이며 NAND 채널 증설의 실제 전력은 미산정입니다. 0.8V 동작은 가정이고 ready의 사전 준비 시간·에너지는 제외합니다.'
    brief.VALIDATION='검증: 테스트 43개 통과 · 성능 실행 24개 · 에너지 계산 60개 · 직전 단일 포트 32개 조건 회귀 일치.'
    brief.SOURCE='근거: results/multiport_256/sweep.csv 및 manifest.json'
    brief.PDF_CHECKS=['512bit','핵심 비교 결과','252.14','197.26','238.26','256.00','502개','55.8%']
    brief.TABLE_HIGHLIGHT_ROW=5
    rows=list(csv.DictReader(CSV.open()))
    selections=[('ready_O502','fast','Ready · 1GHz'),('ready_O502','slow','Ready · 500MHz'),
                ('nand_4ch','slow','NAND · 4채널'),('nand_128ch','slow','NAND · 128채널'),
                ('nand_long','slow','NAND · 128채널')]
    table=[]
    for case,design,label in selections:
        row=next(r for r in rows if r['case']==case and r['design']==design and r['power_variant']=='same_voltage_gated')
        table.append([label,f'{int(row["requests"])*65536/1024**2:g}',
                      f'{float(row["throughput_gbps"]):.2f}',f'{float(row["tail_throughput_gbps"]):.2f}'])
    brief.build_pdf(table);brief.build_docx(table)
    docpath=OUT/f'{brief.STEM}.docx';doc=Document(docpath)
    doc.core_properties.subject='4포트 512bit Host, NAND 확장과 조회 자원 검토';doc.save(docpath)
    evidence=dict(source_csv=str(CSV.relative_to(ROOT)),source_csv_sha256=hashlib.sha256(CSV.read_bytes()).hexdigest(),
                  source_manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                  build_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  layout_script_sha256=hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
                  verified_pdf_pages=1,table_rows=table)
    (OUT/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(OUT)


if __name__=='__main__':main()
