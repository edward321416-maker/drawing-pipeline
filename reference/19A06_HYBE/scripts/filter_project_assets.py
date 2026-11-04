#!/usr/bin/env python3
"""FHHH 19A06 페이지 데이터(__NEXT_DATA__)에서 '이 프로젝트' 이미지만 가려 다운로드본과 대조한다.

capture_reference.py 는 페이지 전체 데이터에서 prismic 이미지 URL을 모두 수집하므로 `works`(다른 프로젝트 썸네일)까지 섞인다.
이 스크립트는 pageData.work 아래 이미지(썸네일·본문 블록 content[]·사진 갤러리 imgsList[][])만 남기고 나머지를 OTHER_WORK 로 분리한다.

    python reference/19A06_HYBE/scripts/filter_project_assets.py --root reference/19A06_HYBE
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_reference as AR  # noqa: E402


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, o


def key(url: str) -> str:
    p = urlsplit(url)
    return unquote(p.path.rsplit("/", 1)[-1]).replace("+", " ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("reference/19A06_HYBE"))
    root = ap.parse_args().root
    html = (root / "manifests" / "rendered_page.html").read_text("utf-8")
    nd = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S).group(1))
    page = nd["props"]["pageProps"]["pageData"]
    cap = json.loads((root / "manifests" / "capture_manifest.json").read_text("utf-8"))
    by_key = {key(a["url"]): a for a in cap["assets"] if a.get("status") == "DOWNLOADED"}
    ana = json.loads((root / "manifests" / "analysis_manifest.json").read_text("utf-8")) if (root / "manifests" / "analysis_manifest.json").is_file() else {"items": []}
    cat = {it["source_url"]: it for it in ana["items"] if it.get("status") == "ANALYZED"}

    def row(path, url, role):
        a = by_key.get(key(url))
        rec = {"json_path": path, "role": role, "url": url, "downloaded": a is not None}
        if a:
            rec.update({"file": a["file"], "sha256": a["sha256"], "size_bytes": a["size_bytes"]})
            c = cat.get(a["url"])
            if c:
                rec.update({"pixels": c["pixels"], "auto_category": c["auto_category"]})
        return rec

    project = []
    seen = set()
    for p, v in walk(page["work"]):
        if isinstance(v, str) and "prismic.io" in v and v not in seen:
            seen.add(v)
            role = "thumbnail" if "/thumbnailImg/" in p else ("page_block" if "/content[" in p else ("photo_gallery" if "/imgsList[" in p else "other_in_work"))
            project.append(row(p, v, role))
    other = []
    for p, v in walk(page.get("works", [])):
        if isinstance(v, str) and "prismic.io" in v and v not in seen:
            seen.add(v)
            other.append(row(p, v, "OTHER_WORK"))
    gallery_lists = [len(x) for x in page["work"].get("imgsList", [])]
    summary = {
        "project": {"id": "19A06", "title": "HYBE", "count_unique_images": len(project), "downloaded": sum(r["downloaded"] for r in project),
                    "by_role": {k: sum(1 for r in project if r["role"] == k) for k in ("thumbnail", "page_block", "photo_gallery", "other_in_work")},
                    "imgsList_lengths": gallery_lists,
                    "note": "페이지 우측 갤러리 번호는 1~15. imgsList[0] 길이와 대조해 CAPTURE 완전성을 판단한다."},
        "other_works_images": {"count": len(other), "downloaded": sum(r["downloaded"] for r in other), "note": "다른 FHHH 프로젝트 썸네일: 분석 대상이 아니다(보관만)."},
        "capture_total_downloaded": cap["downloaded_unique"],
        "missing_project_images": [r["url"] for r in project if not r["downloaded"]],
        "assets": project,
    }
    (root / "manifests" / "project_assets.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", "utf-8")
    other_urls = {r["url"] for r in other}
    (root / "manifests" / "other_work_assets.json").write_text(json.dumps({"count": len(other), "assets": other}, ensure_ascii=False, indent=1) + "\n", "utf-8")

    # 프로젝트 전용 연락판 (분석 도구의 함수 재사용)
    items = [{"path": root / r["file"], "name": Path(r["file"]).name, "auto_category": r.get("auto_category", "?")} for r in project if r["downloaded"] and r["file"].lower().endswith((".jpg", ".png", ".webp", ".gif"))]
    out = root / "contact_sheets"
    for i in range(0, len(items), 12):
        AR.make_sheet(items[i:i + 12], out / f"hybe_only_{i // 12 + 1:02d}.png", i // 12 + 1)
    print(json.dumps({k: summary["project"][k] for k in ("count_unique_images", "downloaded", "by_role", "imgsList_lengths")}, ensure_ascii=False),
          "| other works:", len(other), "| missing:", len(summary["missing_project_images"]), "| sheets:", (len(items) + 11) // 12)


if __name__ == "__main__":
    main()
