#!/usr/bin/env python3
"""Make an auditable image inventory/contact sheets without inventing visual facts."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageFilter, ImageOps


def digest(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def font(n):
    for x in ('C:/Windows/Fonts/malgun.ttf', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(x).is_file():
            return ImageFont.truetype(x, n)
    return ImageFont.load_default()


def classify_image(im: Image.Image):
    """Potential drawing/diagram/photo: image characteristics ONLY, no semantic guarantee."""
    img = ImageOps.exif_transpose(im).convert('RGB')
    img.thumbnail((500, 500))
    raw = img.tobytes()
    n = max(1, len(raw) // 3)
    white = sum(1 for i in range(0, len(raw), 3) if min(raw[i:i+3]) >= 235) / n
    grayscale = sum(1 for i in range(0, len(raw), 3) if max(raw[i:i+3]) - min(raw[i:i+3]) <= 20) / n
    edges = img.convert('L').filter(ImageFilter.FIND_EDGES)
    edge_fraction = sum(1 for x in edges.tobytes() if x > 45) / n
    if white >= .58 and grayscale >= .85:
        label = 'DRAWING_CANDIDATE'
    elif grayscale >= .68 and white >= .40:
        label = 'DIAGRAM_CANDIDATE'
    else:
        label = 'PHOTO_OR_COLOR_GRAPHIC_CANDIDATE'
    return label, {'near_white_fraction': round(white, 4), 'near_gray_fraction': round(grayscale, 4),
                   'edge_fraction': round(edge_fraction, 4)}


def make_sheet(items, out: Path, number: int):
    cell_w, cell_h, cols, rows = 370, 320, 3, 4
    image = Image.new('RGB', (cols * cell_w + 30, rows * cell_h + 50), '#f7f7f7')
    draw = ImageDraw.Draw(image)
    draw.text((16, 11), f'FHHH 19A06 | Reference contact sheet {number:02d}', fill='#222', font=font(18))
    for pos, row in enumerate(items):
        x, y = 10 + (pos % cols) * cell_w, 45 + (pos // cols) * cell_h
        with Image.open(row['path']) as original:
            thumb = ImageOps.contain(ImageOps.exif_transpose(original).convert('RGB'), (cell_w - 18, 266))
            image.paste(thumb, (x + (cell_w - thumb.width)//2, y + 4 + (270 - thumb.height)//2))
        draw.text((x + 8, y + 278), row['name'][:45], fill='#333', font=font(14))
        draw.text((x + 8, y + 298), row['auto_category'], fill='#555', font=font(12))
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)


def run(root: Path):
    manifest_path = root / 'manifests' / 'capture_manifest.json'
    rows = json.loads(manifest_path.read_text('utf-8')).get('assets', []) if manifest_path.is_file() else []
    metadata = []
    asset_rows = []
    for row in rows:
        if row.get('status') != 'DOWNLOADED':
            continue
        p = root / row['file']
        if not p.is_file():
            metadata.append({'asset_id': row.get('id'), 'status':'MISSING_ON_DISK', 'path':row['file']})
            continue
        record = {'asset_id': row['id'], 'path':row['file'], 'sha256':digest(p), 'source_url':row['url'], 'domain':urlsplit(row['url']).netloc}
        try:
            with Image.open(p) as im:
                record['pixels'] = [im.width, im.height]
                record['mode'] = im.mode
                record['auto_category'], record['metrics'] = classify_image(im)
            asset_rows.append({'path':p, 'name':p.name, 'auto_category':record['auto_category']})
            record['status'] = 'ANALYZED'
        except Exception as ex:
            record.update({'status': 'NO_RASTER_PREVIEW', 'reason':str(ex)[:150]})
        metadata.append(record)
    dest = root / 'contact_sheets'
    for i in range(0, len(asset_rows), 12):
        make_sheet(asset_rows[i:i+12], dest / f'contact_{i//12+1:02d}.png', i//12+1)
    counts = {}
    for o in metadata:
        tag = o.get('auto_category', o['status'])
        counts[tag] = counts.get(tag, 0) + 1
    report = {'capture_manifest_present':manifest_path.is_file(), 'registered_items':len(rows),
              'analyzed_items':sum(x['status']=='ANALYZED' for x in metadata),
              'auto_classification_counts':counts, 'items':metadata,
              'warning':'Drawing and diagram categories are heuristic only. Human review is mandatory before style mapping.'}
    (root / 'manifests').mkdir(exist_ok=True)
    (root / 'manifests' / 'analysis_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    html_items = []
    for record in metadata:
        thumb = f'<img loading="lazy" src="{html.escape("../"+record["path"])}" alt="{record["asset_id"]}">' if record['status']=='ANALYZED' else ''
        url = html.escape(record['source_url'],quote=True)
        html_items.append(f'<article>{thumb}<b>{html.escape(str(record["asset_id"]))} · {html.escape(record.get("auto_category",record["status"]))}</b><a href="{url}" target="_blank" rel="noopener">Original source</a></article>')
    index = ('<!doctype html><meta charset="utf-8"><title>FHHH HYBE internal reference</title>'
             '<style>body{font:14px Arial;margin:32px;background:#f7f7f7}main{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}'
             'article{background:white;padding:12px}img{width:100%;height:260px;object-fit:contain}article>*{display:block;margin:8px 0}</style>'
             '<h1>FHHH Friends — HYBE 19A06</h1><p>Private study, source-linked. Automatic tags need visual review.</p><main>'
             +''.join(html_items)+'</main>')
    (root / 'contact_sheets' / 'index.html').write_text(index,encoding='utf-8')
    print(f'Analyzed {report["analyzed_items"]} assets. Contact sheets: {math.ceil(len(asset_rows)/12)}')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path('reference/19A06_HYBE'))
    run(p.parse_args().root)
