from pathlib import Path
import fitz
root=Path(__file__).resolve().parent
with fitz.open(root/'review_packet/pdf/WP0_R10A_Representative_A2.pdf') as book:
    for page in book:
        path=root/f'qa_draft_{page.number+1}.png'
        page.get_pixmap(matrix=fitz.Matrix(.86,.86),alpha=False).save(path)
        print(path.resolve())

