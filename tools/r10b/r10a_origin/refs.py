import fitz
from pathlib import Path
root=Path(__file__).resolve().parent
out=root/'reference_local'
out.mkdir(exist_ok=True)
for kind,name,pages in [('architecture','재열지원_건축 도면집 제출자료.pdf',[6,19,21]),('structure','재열지원_구조 도면집 제출자료.pdf',[15,17]),('overview','설계 개요.pdf',[6,15])]:
    source=Path('D:/Temp')/name
    with fitz.open(source) as doc:
        print(source,len(doc))
        for n in pages:
            page=doc[n-1]
            print(kind,n,page.rect, page.get_text()[:230].replace(chr(10),' '))
            page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False).save(out/f'{kind}_{n:02}.png')
            k=page.rect
            crop=fitz.Rect(k.width*.16,k.height*.19,k.width*.77,k.height*.77)
            page.get_pixmap(dpi=170,clip=crop,alpha=False).save(out/f'{kind}_{n:02}_detail.png')

