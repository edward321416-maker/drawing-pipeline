from pathlib import Path
import json
import re
import fitz
import package as pack
p=pack.PKT
q=pack.read(pack.VALID/'R10A_OUTPUT_QA.json')
with fitz.open(pack.PDF) as d:
    page=d[3]
    k=pack.K
    nominal=17000/75
    lengths=[(q['rect'].width/k,q['rect'].y0/k) for q in page.get_drawings()
             if abs(q['rect'].width/k-nominal)<.025 and q['rect'].height<.025]
    assert any(79<y<115 for w,y in lengths),lengths
    main=pack.read(pack.VALID/'R10A_GEOMETRY.json')
    f=fitz.Font(fontfile='C:/Windows/Fonts/malgun.ttf')
    for row in main['labels']:
        assert all(f.has_glyph(ord(c)) for c in row[-1]),row
    q['independent_1to75_vector_dimension_check']={'sheet':'S-401','distance_world_mm':17000,'scale':75,
            'measured_paper_mm':round(next(w for w,y in lengths if 79<y<115),5)}
    q['embedded_label_glyphs_available']=True
    q['reference_compared_locally']=[str(path.resolve()) for path in sorted(pack.QA.glob('*.jpg'))]
    # Reference files and comparative images remain on this machine.
    q['reference_compared_locally']=[Path(path).name for path in q['reference_compared_locally']]
    assert len(q['reference_compared_locally'])==14
pack.save(pack.VALID/'R10A_OUTPUT_QA.json',q)
pack.doc_notes(q['pages'],q['reference_compare'])
pack.assets_manifest()
print((p/'manifest.json').resolve())

