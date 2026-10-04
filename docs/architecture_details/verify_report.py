"""Verify saved sources, row provenance, PDF/Word content and optional rendering."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import fitz
from docx import Document

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
STEM='NAND_Prefetch_Architecture_Detailed_KO'


def normalized(text):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',text))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--word-rendered-pdf',type=Path)
    args=parser.parse_args()
    evidencepath=OUT/'evidence.json'
    evidence=json.loads(evidencepath.read_text())
    content=json.loads((OUT/'content.json').read_text())
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    for name,expected in evidence['source_sha256'].items():assert digest(ROOT/name)==expected,name
    for name,expected in evidence['output_sha256'].items():assert digest(OUT/name)==expected,name
    rows={}
    for item in evidence['selected_source_rows']:
        if item['source'] not in rows:rows[item['source']]=list(csv.DictReader((ROOT/item['source']).open()))
        selected=[r for r in rows[item['source']] if all(r[k]==str(v) for k,v in item['criteria'].items())]
        assert selected==[item['row']],item['criteria']
    for item,expected in zip(evidence['timing_cases'],[501,801,801]):
        assert abs(item['first_burst_ns']['rlast']-expected)<1e-5
    doc=Document(OUT/f'{STEM}.docx')
    docparagraphs=[p.text for p in doc.paragraphs]
    for page in content['pages']:
        assert any(page['title'] in x for x in docparagraphs)
        for block in page['blocks']:
            if block['type'] in ['paragraph','heading','formula']:assert block['text'] in docparagraphs
    with fitz.open(OUT/f'{STEM}.pdf') as pdf:
        assert len(pdf)==len(content['pages'])==20
        assert len(pdf.get_toc())==20
        for i,page in enumerate(content['pages']):assert page['title'] in pdf[i].get_text()
    validation=evidence['validation']
    validation.update(source_hashes_verified=True,selected_csv_rows_verified=len(evidence['selected_source_rows']),
                      timing_first_burst_verified_ns=[501,801,801],pdf_outline_entries=20)
    if args.word_rendered_pdf:
        with fitz.open(args.word_rendered_pdf) as rendered:
            assert len(rendered)==20
            checked=0
            cellcount=0
            for i,page in enumerate(content['pages']):
                # Font fallback can emit arrows after adjacent Latin spans.
                # Geometric sorting restores their visual order; raw order
                # better preserves multi-line cells in separate columns.
                texts=[normalized(rendered[i].get_text(sort=order)) for order in [False,True]]
                def contains(value):return any(normalized(str(value)) in text for text in texts)
                # Read each shaded table cell independently so line wrapping
                # does not interleave text from neighboring columns.
                allowed=[(24/255,55/255,77/255),(1,1,1),(244/255,247/255,248/255)]
                cellrects={}
                for drawing in rendered[i].get_drawings():
                    fill=drawing.get('fill');rect=drawing['rect']
                    if fill and 60<rect.width<500 and rect.height>8 and any(
                            all(abs(a-b)<.002 for a,b in zip(fill,color)) for color in allowed):
                        key=tuple(round(v,1) for v in rect)
                        cellrects[key]=rect
                rects=iter(sorted(cellrects.values(),key=lambda r:(round(r.y0,1),r.x0)))
                assert contains(page['title']),(i,page['title'])
                for block in page['blocks']:
                    if block['type'] in ['paragraph','heading','formula']:
                        assert contains(block['text']),(i,block['text'][:60])
                        checked+=1
                    elif block['type']=='table':
                        for row in [block['headers']]+block['rows']:
                            for cell in row:
                                rect=next(rects)
                                clip=fitz.Rect(rect.x0-.2,rect.y0-.2,rect.x1+.2,rect.y1+.2)
                                extracted=[normalized(rendered[i].get_text(clip=clip,sort=order)) for order in [False,True]]
                                assert normalized(str(cell)) in extracted,(i,cell,extracted)
                                cellcount+=1
                assert next(rects,None) is None,(i,'Unverified rendered table cell')
            validation.update(word_rendered_pdf_pages=20,word_rendered_paragraphs_verified=checked,
                              word_rendered_table_cells_verified=cellcount,
                              word_rendered_pdf_sha256=digest(args.word_rendered_pdf),
                              word_rendered_source_docx_sha256=digest(OUT/f'{STEM}.docx'),
                              word_renderer='LibreOfficeDev 26.8.0.0.alpha0; layout may vary in other editors')
    evidence['source_sha256']['docs/architecture_details/verify_report.py']=digest(Path(__file__))
    evidencepath.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(validation,ensure_ascii=False))


if __name__=='__main__':main()
