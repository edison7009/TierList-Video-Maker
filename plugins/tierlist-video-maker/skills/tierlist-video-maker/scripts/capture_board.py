#!/usr/bin/env python3
"""Capture a high-resolution tier-list board image from the public TierVibe post page.

Usage:
    python capture_board.py "<URL_OR_SLUG>" -o <work_dir>

This is how the video gets a true high-resolution background WITHOUT hitting the
TierVibe server for a board image (the server only stores a 600px thumbnail). It
runs a headless Chromium, opens the public read page https://tiervibe.com/t/<slug>
(no login needed — published posts are public), and uses the SAME html-to-image
approach the in-browser "download whole image" button uses, but automated:

    find the node with data-testid="tier-grid"  ->  html-to-image.toPng(pixelRatio=2)

So the whole-image export stays a USER-SIDE action (no server call), just done by
a script instead of a button click. Output: <work_dir>/board_hd.png.

Requirements: Playwright with Chromium. Auto-installs on first run.
"""

import argparse
import os
import re
import sys


def extract_slug(url_or_id: str) -> str:
    m = re.search(r"tiervibe\.com/t/([A-Za-z0-9]+)", url_or_id)
    if m:
        return m.group(1)
    candidate = url_or_id.strip()
    if re.fullmatch(r"[A-Za-z0-9]{4,30}", candidate):
        return candidate
    raise ValueError(f"Cannot extract slug from: {url_or_id}")


def _ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        import subprocess
        print("Installing playwright...", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
    import subprocess
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False,
    )


_INJECT = r"""
async function captureBoard(pixelRatio) {
  const node = document.querySelector('[data-testid="tier-grid"]');
  if (!node) throw new Error('tier-grid node not found (page may be loading or slug wrong)');
  const imgs = Array.from(node.querySelectorAll('img'));
  await Promise.all(imgs.map(img => img.complete
    ? Promise.resolve()
    : new Promise(res => { img.addEventListener('load', res, {once:true}); img.addEventListener('error', res, {once:true}); })));
  await new Promise(r => setTimeout(r, 400));
  const dataUrl = await htmlToImage.toPng(node, { pixelRatio: pixelRatio, cacheBust: false });
  return dataUrl;
}
"""

_HTML_TO_IMAGE_CDN = "https://cdn.jsdelivr.net/npm/html-to-image@1.11.13/dist/html-to-image.min.js"


def capture_board(url_or_id: str, out_dir: str, pixel_ratio: int = 2,
                  page_width: int = 1280, wait_timeout_ms: int = 25000) -> str:
    _ensure_playwright()
    slug = extract_slug(url_or_id)
    url = f"https://tiervibe.com/t/{slug}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "board_hd.png")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": page_width, "height": 900},
                device_scale_factor=1,
            )
            page = context.new_page()
            print(f"Opening public page: {url}")
            page.goto(url, wait_until="networkidle", timeout=wait_timeout_ms)

            try:
                page.wait_for_selector('[data-testid="tier-grid"]', timeout=wait_timeout_ms)
            except Exception:
                raise SystemExit(
                    "tier-grid not found. The page may still be deploying the "
                    "data-testid attribute (needs a TierVibe deploy), or the slug is wrong."
                )

            page.add_script_tag(url=_HTML_TO_IMAGE_CDN)
            page.wait_for_function("typeof window.htmlToImage !== 'undefined'", timeout=15000)

            data_url = page.evaluate(
                f"async () => {{ {_INJECT} return await captureBoard({pixel_ratio}); }}",
            )
            if not data_url or not data_url.startswith("data:image/png"):
                raise SystemExit("Capture returned no image data.")

            import base64
            b64 = data_url.split(",", 1)[1]
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"High-res board captured: {out_path}")
            return out_path
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture high-res board image from public TierVibe page")
    parser.add_argument("url", help="TierVibe URL or public slug")
    parser.add_argument("-o", "--output", default="tierlist_work", help="Output directory")
    parser.add_argument("--pixel-ratio", type=int, default=2, help="html-to-image pixelRatio (higher = sharper)")
    args = parser.parse_args()
    capture_board(args.url, args.output, pixel_ratio=args.pixel_ratio)
