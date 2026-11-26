"""Render, measure, and package R10-A. Reference-page comparisons stay local."""
from collections import Counter
from hashlib import file_digest
from io import BytesIO
from pathlib import Path
import json
import math
import sys
import re

import fitz
from PIL import Image,ImageOps,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
PKT=ROOT/"review_packet"
QA=ROOT/"비교검수"
VALID=PKT/"validation"
PDF=PKT/"pdf/WP0_R10A_Representative_A2.pdf"
K=72/25.4
DPI=300
SPECS=[
(1,"A-201","2층 전체 건축 평면도","1:200",(63,68,191,176)),
(2,"A-301","전체 건축 종단면도","1:250",(179,221,307,329)),
(3,"A-501","코어 D 상세 평·단면도","1:50",(362,132,490,240)),
(4,"S-401","E2 브리지 구조 상세 연구도","1:100 / 1:75 / 1:25",(365,246,493,354))]
REFS=[
(1,"architecture_06","재열지원_건축 도면집 제출자료.pdf",6,(209,95),"A축·치수선·벽 및 구획"),
(1,"overview_06","설계 개요.pdf",6,(207,170),"실 번호·동선 설비·투영"),
(2,"architecture_19","재열지원_건축 도면집 제출자료.pdf",19,(89,223),"절단·기준 레벨 및 층고"),
(3,"architecture_21","재열지원_건축 도면집 제출자료.pdf",21,(363,185),"디딤판·계단참 단면"),
(3,"overview_15","설계 개요.pdf",15,(373,185),"계단실·부속실 치수"),
(4,"structure_15","재열지원_구조 도면집 제출자료.pdf",15,(232,75),"부재 태그·접합 상세 키"),
(4,"structure_17","재열지원_구조 도면집 제출자료.pdf",17,(117,170),"단면 부호·레벨과 기준선")]
FONT="C:/Windows/Fonts/malgun.ttf"

def sha(p):
    with p.open("rb") as f:return file_digest(f,"sha256").hexdigest()

def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))

def save(p,d):
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf8",newline="\n")

def image_of(p,dpi=DPI,clip=None):
    pix=p.get_pixmap(dpi=dpi,alpha=False,annots=False,clip=clip)
    return Image.frombytes("RGB",(pix.width,pix.height),pix.samples)

def small_jpeg(im,path,target=(1880,1330),n=950_000):
    ip=ImageOps.contain(im,target,Image.Resampling.LANCZOS)
    for q in (92,88,83,77,70,62):
        b=BytesIO()
        ip.save(b,format="JPEG",quality=q,optimize=True,subsampling=0)
        data=b.getvalue()
        if len(data)<n:
            path.write_bytes(data)
            return {"width":ip.width,"height":ip.height,"bytes":len(data),"quality":q}
    raise ValueError(f"JPEG over budget {path}")

def clip_phys(page,x,y,w,h):
    if (x+w)*K>page.rect.width+.02 or (y+h)*K>page.rect.height+.02:
        raise ValueError(("comparison outside original",page.number,x,y,w,h,page.rect))
    return fitz.Rect(x*K,y*K,(x+w)*K,(y+h)*K)

def paired(a,b,left,right,size=None):
    if size:
        a=ImageOps.contain(a,size);b=ImageOps.contain(b,size)
        cellw,cellh=size
    else:
        assert abs(a.width-b.width)<2 and abs(a.height-b.height)<2,(a.size,b.size)
        cellw,cellh=max(a.width,b.width),max(a.height,b.height)
    canvas=Image.new("RGB",(2*cellw+43,cellh+60),"#e5e9e8")
    dr=ImageDraw.Draw(canvas)
    f=ImageFont.truetype(FONT,18)
    for i,(img,title) in enumerate([(a,left),(b,right)]):
        x=12+i*(cellw+19)
        dr.text((x,8),title,font=f,fill="#202526")
        canvas.paste(img,(x+(cellw-img.width)//2,43+(cellh-img.height)//2))
    return canvas

def bar_lengths(doc,data):
    results=[]
    for row in data["graphical_scales"]:
        d=row["panel"][:5]
        p=doc[next(n-1 for n,k,*_ in SPECS if k==d)]
        x,y,h=row["bar"]
        lens=[]
        for d in p.get_drawings():
            a,b,c,e=[v/K for v in d["rect"]]
            if abs(b-y)<.020 and abs(e-y-h)<.018 and (abs(a-x)<.018 or abs(a-x-row["paper_mm"]/2)<.018):
                lens.append((a,c))
        assert len(lens)==2,(row,lens)
        measured=max(c for a,c in lens)-min(a for a,c in lens)
        assert abs(measured-row["metres"]*1000/row["scale"])<.025
        results.append({**row,"vector_measured_mm":round(measured,5)})
    return results

def render_packs(book):
    rows=[]
    for num,id_,title,scale,b in SPECS:
        page=book[num-1]
        assert len(page.get_image_info())==0 and id_ in page.get_text()
        text=page.get_text()
        assert re.search("[가-힣]",text) and "\ufffd" not in text
        assert abs(page.rect.width/K-594)<.003 and abs(page.rect.height/K-420)<.003
        a=PKT/f"pdf/{id_}.pdf"
        with fitz.open() as only:
            only.insert_pdf(book,from_page=num-1,to_page=num-1,annots=False,links=False)
            only.save(a,garbage=4,deflate=True)
        with fitz.open(a) as only:
            assert only[0].get_text()==text
            assert only[0].get_pixmap(dpi=150).samples==page.get_pixmap(dpi=150).samples
        svg=page.get_svg_image(text_as_path=True)
        assert "<image" not in svg
        (PKT/f"svg/{id_}.svg").write_text(svg,encoding="utf8",newline="\n")
        im=image_of(page)
        target=PKT/f"high_resolution/{id_}.png"
        im.save(target,dpi=(DPI,DPI))
        sm=small_jpeg(im,PKT/f"previews/{id_}.jpg")
        x0,y0,x1,y1=b
        detail=image_of(page,DPI,clip_phys(page,x0,y0,x1-x0,y1-y0))
        detail.save(PKT/f"details/{id_}_detail.png",dpi=(DPI,DPI))
        zoom=small_jpeg(detail,PKT/f"details/{id_}_detail.jpg",(1530,1310))
        dd=PKT/"tiles"/id_
        dd.mkdir(exist_ok=True)
        tiles=[]
        for r in range(3):
            for c in range(4):
                w,h=im.size
                bounds=(max(0,w*c//4-40),max(0,h*r//3-40),min(w,w*(c+1)//4+40),min(h,h*(r+1)//3+40))
                tile=im.crop(bounds)
                number=f"r{r+1:02d}-c{c+1:02d}"
                tile.save(dd/(number+".png"),dpi=(DPI,DPI))
                small=small_jpeg(tile,dd/(number+".jpg"),(1800,1700))
                tiles.append({"png":f"tiles/{id_}/{number}.png","jpeg":f"tiles/{id_}/{number}.jpg","bounds_px":bounds,"jpeg_data":small})
        stats=Counter(round(q["width"]/K,3) for q in page.get_drawings() if q.get("width") and q["width"]>0)
        rows.append({"number":num,"sheet":id_,"title":title,"scale":scale,"pdf":f"pdf/{id_}.pdf",
                     "svg":f"svg/{id_}.svg","preview":f"previews/{id_}.jpg","preview_data":sm,
                     "high_resolution":f"high_resolution/{id_}.png","high_resolution_px":im.size,
                     "detail":f"details/{id_}_detail.png","detail_preview":f"details/{id_}_detail.jpg","detail_preview_data":zoom,
                     "detail_window_mm":b,"tiles":tiles,"pen_distribution_mm":dict(stats)})
        print(target.resolve(),flush=True)
    return rows

def compare_references(book):
    results=[]
    for n,ident,name,pn,origin,focus in REFS:
        source=Path("D:/Temp")/name
        out=QA/ident
        with fitz.open(source) as ref:
            r=ref[pn-1]
            target=book[n-1]
            ss=paired(image_of(r,80),image_of(target,80),f"참고 {pn}쪽 · {focus}",f"R10-A {SPECS[n-1][1]}",size=(1000,710))
            ss.save(out.with_name(ident+"_same_screen.jpg"),quality=94)
            x0,y0,x1,y1=SPECS[n-1][-1]
            w,h=x1-x0,y1-y0
            aa=image_of(r,220,clip_phys(r,*origin,w,h))
            bb=image_of(target,220,clip_phys(target,x0,y0,w,h))
            vv=paired(aa,bb,f"참고 {pn}쪽 · {w:g} × {h:g} mm",f"R10-A {SPECS[n-1][1]} · 동일 물리 영역")
            vv.save(out.with_name(ident+"_100pct.jpg"),quality=96)
            widths=Counter(round(d["width"]/K,3) for d in r.get_drawings() if d.get("width") and d["width"]>0)
            results.append(dict(sheet=SPECS[n-1][1],reference_filename=name,reference_page=pn,
              reference_sha256=sha(source),reference_paper_mm=[round(r.rect.width/K,3),round(r.rect.height/K,3)],
              viewport_caption=focus,common_physical_crop_mm=[w,h],common_dpi=220,
              reference_pen_common_mm=widths.most_common(9),full_comparison=ident+"_same_screen.jpg",
              detail_comparison=ident+"_100pct.jpg"))
    return results

def doc_notes(rows,comparisons):
    text="""# WP0 R10-A · 대표 도면 검수

건축 제출 표현을 검토하는 A2 가로형 대표 도면 네 장입니다. PDF는 벡터 원본이며 A2에서 실제 크기 100%로 출력합니다. 300 DPI 원본과 1MB 미만 JPEG를 함께 제공합니다. 설계안은 독립 검수 대기 상태입니다.

- [대표 도면 전체 PDF](pdf/WP0_R10A_Representative_A2.pdf)
- [페이지별 컷·축척·이미지 색인](validation/R10A_OUTPUT_QA.json)
- [형상·실 목록·절단 근거](validation/R10A_GEOMETRY.json)
- [참고본 대비 개선 내역](validation/REFERENCE_COMPARISON.md)
- [SHA-256 매니페스트](manifest.json)

| 도면 | 축척 | PDF | SVG | 채팅 미리보기 | 300 DPI | 확대 | 타일 |
|---|---|---|---|---|---|---|---|
"""
    for r in rows:
        s=r["sheet"]
        text+=f"| {s} {r['title']} | {r['scale']} | [PDF]({r['pdf']}) | [SVG]({r['svg']}) | [JPEG]({r['preview']}) | [PNG]({r['high_resolution']}) | [JPEG]({r['detail_preview']}) | [PNG·JPEG](tiles/{s}) |\n"
    text+="""
2F의 실 분할과 가구는 PR #30의 연구 프로그램을 유지합니다. CH는 미확인입니다. 코어 D, 브리지, 랜딩, 개구는 이전 연구 형상을 기준으로 표시합니다. OS-1 지점 및 정착, 방화·피난·운영, 1F 계단 통합은 미확인입니다.

- [R9 N-2F 기술 검증 경로 오버레이](https://github.com/edward321416-maker/drawing-pipeline/blob/a7805f335abe0653baaf93a61e7777f6d619cd42/review/wp0_r9/vector_drawings/P02-N-2F.pdf)
- [R9 A-D 계단 대안 비교 부록](https://github.com/edward321416-maker/drawing-pipeline/blob/a7805f335abe0653baaf93a61e7777f6d619cd42/review/wp0_r9/vector_drawings/P12-A-D.pdf)
- PR #30 기준 커밋 `1164fc0f58d943598d8e48146a02fcb3214c852e`
- R9 독립 검수 기준 커밋 `a7805f335abe0653baaf93a61e7777f6d619cd42`
"""
    (PKT/"README.md").write_text(text,encoding="utf8",newline="\n")
    compare="""# R10-A 참고본 대조 결과

로컬 기준 PDF를 직접 렌더링했습니다. 같은 크기의 화면에서 도곽과 제도 위계를 대조했고, 동일한 물리 영역 128×108 mm를 220 DPI로 렌더하여 글자·치수선·부재 경계를 비교했습니다. 참고본 내 레벨·부재 크기는 R10-A의 설계 입력으로 옮기지 않았습니다. 화면과 PDF 벡터를 검수했습니다. 실제 프린터 테스트는 미실시입니다.

| 대표 시트 | 대응 참고 | 반영한 표현 | 현재 근거 한계 |
|---|---|---|---|
| A-201 | 건축 6 / 설계 개요 6 | 축 버블·전체와 부분 치수·실번호와 실 목록·벽/기둥/가구 위계·북향·절단 및 상세 크로스레퍼런스 | PR #30 배치 데이터를 회수한 설계 후보. 천장고·마감 및 미원본 부재는 미확인. |
| A-301 | 건축 19 | B2–15F의 층별 기준선과 층고, 모델 절단 포셰, 후면 투영 점선, 프로그램 표기, 2F·7F D 브리지 콜아웃 | 모형의 기존 코어 표현 박스에서 실계단을 추정하지 않음. 정원은 프로그램 계획. |
| A-501 | 건축 21 / 설계 개요 15 | 6m·5m 계단 후보 1:50 평면, 4갈래 챌면·디딤판 치수와 계단참, 같은 좌표의 실제 1F 마스터 단면 비교 | 계단 통합 보류. 후보 방화문은 하드웨어·등급 미확인. |
| S-401 | 구조 15·17 | 기준축·부재 태그·평면·종횡단·양단 키, 기존 슬래브와 후보 접합 체적 구분 | 모델 수평 간격이 구조 경간으로 확정되지 않음. 단면·정착·앵커·배근·강도 미확인. |

원본 PDF와 비교 이미지는 로컬 검수에 사용했습니다. 원격 검수팩에는 자체 도면과 대조 내역 및 참고 페이지의 SHA-256을 포함합니다.
"""
    (VALID/"REFERENCE_COMPARISON.md").write_text(compare,encoding="utf8",newline="\n")

def assets_manifest():
    vals=[]
    for f in sorted(PKT.rglob("*")):
        if f.is_file() and f.name!="manifest.json":
            vals.append({"path":f.relative_to(PKT).as_posix(),"bytes":f.stat().st_size,"sha256":sha(f)})
    save(PKT/"manifest.json",{"base":"review/wp0_r10_a","algorithm":"SHA-256","artifact_count":len(vals),
                              "pdf":{"path":PDF.relative_to(PKT).as_posix(),"sha256":sha(PDF)},"files":vals})

def main():
    QA.mkdir(exist_ok=True)
    for n in ("previews","high_resolution","svg","details","tiles"):
        (PKT/n).mkdir(exist_ok=True)
    e=read(VALID/"R10A_GEOMETRY.json")
    assert sha(PDF)==e["pdf_sha256"] and len(e["sheets"]["A-501"]["intersecting_steps"])>=10
    assert all(abs(d["paper_mm"]-1000*d["metres"]/d["scale"])<1e-7 for d in e["calculated_dimensions"])
    with fitz.open(PDF) as doc:
        assert len(doc)==4
        checks=bar_lengths(doc,e)
        rows=render_packs(doc)
        references=compare_references(doc)
    doc_notes(rows,references)
    save(VALID/"R10A_OUTPUT_QA.json",{"page_count":len(rows),"raster_dpi":DPI,
        "graphical_scales":checks,"dimension_samples":len(e["calculated_dimensions"]),
        "reference_compare":references,"previews_mb_limit":1_000_000,"pages":rows})
    assets_manifest()
    print((PKT/"manifest.json").resolve(),flush=True)

if __name__=="__main__":
    main()

