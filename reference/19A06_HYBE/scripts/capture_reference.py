#!/usr/bin/env python3
"""Capture public on-page imagery for private architectural reference study.

Only the explicitly requested project page is navigated. No login, paywall or
access control is bypassed. Raw images are preserved with source URL + hash.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import mimetypes
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

try:
    from playwright.async_api import async_playwright, TimeoutError as BrowserTimeout
except ImportError as exc:
    raise SystemExit("Playwright missing. Use an existing trusted Python environment: python -m pip install playwright") from exc

TARGET_URL = "https://fhhhfriends.com/19a06"
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg", ".tif", ".tiff"}
EXT_MIME = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
    "image/gif": ".gif", "image/avif": ".avif", "image/svg+xml": ".svg",
    "image/tiff": ".tif",
}
IMAGE_URL_PATTERN = re.compile(r"(?:https?:)?//[^\s\"'<>\\]+?\.(?:jpg|jpeg|png|webp|gif|avif|svg|tif|tiff)(?:\?[^\s\"'<>\\]*)?", re.I)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_url(value: str, base: str) -> str | None:
    if not isinstance(value, str):
        return None
    value = html.unescape(value).strip().strip("\"'")
    if not value or value.startswith(("data:", "blob:", "javascript:", "mailto:")):
        return None
    url = urljoin(base, value)
    if urlsplit(url).scheme not in ("http", "https", "file"):
        return None
    return url.split("#", 1)[0]


def extract_html_image_urls(content: str, base: str) -> set[str]:
    content = html.unescape(content).replace("\\/", "/").replace("\\u002F", "/")
    found = set()
    for match in IMAGE_URL_PATTERN.findall(content):
        value = normalize_url(match, base)
        if value:
            found.add(value)
    return found


def prefer_browser_executable(hint: str | None) -> str | None:
    if hint:
        p = Path(hint)
        if not p.is_file():
            raise FileNotFoundError(f"Browser executable not found: {hint}")
        return str(p)
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/usr/bin/chromium", "/usr/bin/google-chrome",
    ]
    return next((p for p in paths if Path(p).is_file()), None)


def image_ext(url: str, content_type: str) -> str:
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime in EXT_MIME:
        return EXT_MIME[mime]
    suffix = Path(unquote(urlsplit(url).path)).suffix.lower()
    return suffix if suffix in MEDIA_EXT else ".img"


async def dom_images(page) -> set[str]:
    collected = await page.evaluate("""() => {
      const output = [];
      const add = v => {if (v && typeof v === 'string') output.push(v)};
      for (const el of document.querySelectorAll('img, picture source, video[poster]')) {
        for (const name of ['src', 'currentSrc', 'data-src', 'data-lazy-src', 'data-original', 'poster'])
          add(el[name] || el.getAttribute(name));
        for (const name of ['srcset', 'data-srcset']) {
          const srcset = el.getAttribute(name);
          if (srcset) for (const item of srcset.split(',')) add(item.trim().split(/\\s+/)[0]);
        }
      }
      for (const el of document.querySelectorAll('*')) {
        const bg = getComputedStyle(el).backgroundImage;
        if (bg && bg !== 'none') for (const m of bg.matchAll(/url\\(["']?([^"')]+)["']?\\)/g)) add(m[1]);
      }
      for (const el of document.querySelectorAll('a[href]')) {
        const href = el.getAttribute('href');
        if (/\\.(jpe?g|png|gif|webp|svg|avif|tiff?)(\\?|$)/i.test(href || '')) add(href);
      }
      return output;
    }""")
    base = page.url
    return {u for raw in collected if (u := normalize_url(raw, base))}


async def create_screenshots(page, dest: Path, observed: set[str], delay: float, max_scrolls: int):
    dest.mkdir(parents=True, exist_ok=True)
    h = await page.evaluate("document.documentElement.scrollHeight")
    viewport = page.viewport_size or {"height": 900}
    step = max(200, int(viewport["height"] * .80))
    y = 0
    screenshots = []
    previous = set()
    for iteration in range(max_scrolls):
        await page.evaluate("y => window.scrollTo(0, y)", y)
        await page.wait_for_timeout(delay * 1000)
        observed.update(await dom_images(page))
        png = await page.screenshot(full_page=False, animations="disabled")
        sig = hash_bytes(png)
        if sig not in previous:
            path = dest / f"viewport_{len(screenshots)+1:04d}.png"
            path.write_bytes(png)
            screenshots.append({"path": str(path.name), "scroll_y": y, "sha256": sig})
            previous.add(sig)
        new_h = await page.evaluate("document.documentElement.scrollHeight")
        if y + viewport["height"] >= new_h - 6 and h == new_h:
            break
        h = new_h
        y += step
    await page.evaluate("window.scrollTo(0, 0)")
    return screenshots


async def click_gallery(page, dest: Path, observed: set[str], delay: float, max_clicks: int):
    """Best effort: click explicit on-page 'next image' controls, never a project nav link."""
    selector = ("button[aria-label*='next' i], button[title*='next' i], "
                "button[aria-label*='다음' i], .swiper-button-next, "
                "[role='button'][aria-label*='next' i]")
    seen = set()
    items = []
    for _ in range(max_clicks):
        buttons = page.locator(selector)
        button = None
        for i in range(min(await buttons.count(), 15)):
            candidate = buttons.nth(i)
            if await candidate.is_visible() and await candidate.is_enabled():
                button = candidate
                break
        if button is None:
            break
        signature = tuple(sorted(await dom_images(page)))
        if signature in seen:
            break
        seen.add(signature)
        before = urlsplit(page.url).path
        try:
            await button.click(timeout=4500)
        except Exception:
            break
        await page.wait_for_timeout(delay * 1000)
        if urlsplit(page.url).path != before:
            break
        observed.update(await dom_images(page))
        pic = await page.screenshot(full_page=False, animations="disabled")
        fname = f"gallery_{len(items)+1:04d}.png"
        (dest / fname).write_bytes(pic)
        items.append({"path": fname, "sha256": hash_bytes(pic)})
    return items


async def download_assets(context, urls: list[str], output: Path, max_size_mb: int, max_total_mb: int):
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    content_hashes = set()
    total = 0
    max_size = max_size_mb * 1024 * 1024
    max_total = max_total_mb * 1024 * 1024
    for idx, url in enumerate(urls, start=1):
        row = {"id": idx, "url": url, "status": "PENDING"}
        try:
            if urlsplit(url).scheme == "file":
                raw = Path(unquote(urlsplit(url).path)).read_bytes()
                content_type = mimetypes.guess_type(url)[0] or "application/octet-stream"
                status = 200
            else:
                response = await context.request.get(url, timeout=35000, max_redirects=8)
                status = response.status
                content_type = response.headers.get("content-type", "")
                if not response.ok:
                    raise ValueError(f"HTTP {status}")
                if not (content_type.lower().startswith("image/") or Path(urlsplit(url).path).suffix.lower() in MEDIA_EXT):
                    raise ValueError(f"not image media: {content_type}")
                raw = await response.body()
            if len(raw) > max_size:
                raise ValueError(f"individual file exceeds {max_size_mb} MB")
            if total + len(raw) > max_total:
                raise ValueError(f"TOTAL_LIMIT_REACHED ({max_total_mb} MB); no more downloads")
            digest = hash_bytes(raw)
            row.update({"http_status": status, "mime": content_type, "size_bytes": len(raw), "sha256": digest})
            if digest in content_hashes:
                row["status"] = "DUPLICATE_SHA256"
            else:
                extension = image_ext(url, content_type)
                name = f"asset_{idx:04d}_{digest[:10]}{extension}"
                (output / name).write_bytes(raw)
                row.update({"status": "DOWNLOADED", "file": f"originals/{name}"})
                content_hashes.add(digest)
                total += len(raw)
        except Exception as ex:
            row.update({"status": "FAILED", "error": str(ex)[:350]})
        rows.append(row)
    return rows


async def capture(args):
    root = args.output.resolve()
    (root / "originals").mkdir(parents=True, exist_ok=True)
    (root / "captures").mkdir(exist_ok=True)
    (root / "manifests").mkdir(exist_ok=True)
    observed: set[str] = set()
    net: set[str] = set()
    screenshots = []
    gallery = []
    errors = []
    async with async_playwright() as pw:
        launch = {"headless": True}
        executable = prefer_browser_executable(args.browser)
        if executable:
            launch["executable_path"] = executable
        browser = await pw.chromium.launch(**launch)
        context = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = await context.new_page()
        def response_listener(response):
            mime = response.headers.get("content-type", "")
            if mime.lower().startswith("image/"):
                net.add(response.url.split("#", 1)[0])
        page.on("response", response_listener)
        try:
            await page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(1900)
            if urlsplit(page.url).path.rstrip("/") != urlsplit(args.url).path.rstrip("/"):
                errors.append(f"redirected to unexpected path: {page.url}")
            screenshots = await create_screenshots(page, root / "captures", observed, args.delay, args.max_scrolls)
            gallery = await click_gallery(page, root / "captures", observed, args.delay, args.max_clicks)
            observed.update(await dom_images(page))
            raw_html = await page.content()
            (root / "manifests" / "rendered_page.html").write_text(raw_html, encoding="utf-8")
            observed.update(extract_html_image_urls(raw_html, args.url))
        except Exception as ex:
            errors.append(f"page collection failed: {type(ex).__name__}: {ex}")
        found = sorted({u for u in observed | net if u and urlsplit(u).scheme in ("http", "https", "file")})
        print(f"Found {len(found)} image URLs, captured {len(screenshots)} viewports and {len(gallery)} gallery slides", flush=True)
        rows = await download_assets(context, found, root / "originals", args.max_file_mb, args.max_total_mb)
        await browser.close()
    report = {
        "source_url": args.url, "captured_at_utc": now_iso(),
        "capture_policy": "public on-page assets only; personal research; no auth bypass",
        "page_screenshots": screenshots, "gallery_screenshots": gallery,
        "network_image_urls": len(net), "dom_or_html_image_urls": len(observed),
        "discovered_image_urls": len(found),
        "downloaded_unique": sum(x["status"] == "DOWNLOADED" for x in rows),
        "duplicate_by_sha256": sum(x["status"] == "DUPLICATE_SHA256" for x in rows),
        "download_failed": sum(x["status"] == "FAILED" for x in rows),
        "assets": rows,
        "issues": errors,
        "all_media_captured": bool(rows) and not errors and all(x["status"] != "FAILED" for x in rows),
        "completeness_caveat": "Lazy slide content not referenced by page until interacted with may remain missing; compare visible gallery count to manifest and capture manually if needed.",
    }
    path = root / "manifests" / "capture_manifest.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RESULT: {report['downloaded_unique']} unique images; {report['download_failed']} failures. Manifest: {path}")
    return 0 if not errors and report["download_failed"] == 0 else 2


def main():
    parser = argparse.ArgumentParser(description="Capture user-specified FHHH HYBE project imagery for private research")
    parser.add_argument("--url", default=TARGET_URL)
    parser.add_argument("--output", type=Path, default=Path("reference/19A06_HYBE"))
    parser.add_argument("--browser", help="Already installed Chrome/Edge/Chromium path")
    parser.add_argument("--delay", type=float, default=0.35, help="Seconds after scroll/click")
    parser.add_argument("--max-scrolls", type=int, default=400)
    parser.add_argument("--max-clicks", type=int, default=150)
    parser.add_argument("--max-file-mb", type=int, default=80)
    parser.add_argument("--max-total-mb", type=int, default=4096)
    args = parser.parse_args()
    sys.exit(asyncio.run(capture(args)))


if __name__ == "__main__":
    main()
