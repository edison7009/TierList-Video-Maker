#!/usr/bin/env python3
"""Capture a high-resolution tier-list board image from the public TierVibe post page.

Usage:
    python capture_board.py "<URL_OR_SLUG>" -o <work_dir>

Produces board_hd.png = the tier grid + a branded title bar on top (title left,
TierVibe logo + "Tier"/"Vibe" wordmark right) — i.e. the SAME image the in-page
"download whole image" button produces (SaveImage.saveImage(includeTitle=true)),
so the video background carries the TierVibe brand. Runs headless Chromium on
the public page (no login, no TierVibe server call for the image). The title is
fetched from the public API; the logo is bundled in the skill (assets/logo.svg).
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

API_BASE = "https://tiervibe.com/api/posts"
USER_AGENT = "TierListVideoMaker/1.0"
IMG_TIMEOUT = 30

# assets/logo.svg lives three directories above this script:
# scripts/ -> skills/tierlist-video-maker/ -> skills/ -> plugins/tierlist-video-maker/ -> assets/
_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "..", "..", "assets", "logo.svg")


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
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            "Failed to install Playwright Chromium (check network/proxy/disk). "
            "High-res capture aborted — the video will fall back to the 600px "
            "thumb from Step 2 (fetch_tierlist.py)."
        )


def _fetch_title(slug: str) -> str:
    """Fetch the post title from the public API (capture needs it for the bar)."""
    api_url = f"{API_BASE}/{slug}"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=IMG_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8")).get("title", "") or ""
    except Exception as e:
        print(f"  [WARN] could not fetch title from API: {e}", file=sys.stderr)
        return ""


def _load_logo_data_uri() -> str:
    """Read the bundled logo.svg as a data: URI (keeps the canvas untainted)."""
    try:
        with open(_LOGO_PATH, "rb") as f:
            return "data:image/svg+xml;base64," + base64.b64encode(f.read()).decode("ascii")
    except Exception as e:
        print(f"  [WARN] logo not found at {_LOGO_PATH}: {e} — wordmark still draws.", file=sys.stderr)
        return ""


# JS injected into the page. Replicates SaveImage.drawHeader: title left, logo
# + "Tier"/"Vibe" wordmark right, on a dark band above the captured tier grid.
_INJECT = r"""
async function captureBoard(pixelRatio, title, logoDataUri) {
  const node = document.querySelector('[data-testid="tier-grid"]');
  if (!node) throw new Error('tier-grid node not found');
  const imgs = Array.from(node.querySelectorAll('img'));
  await Promise.all(imgs.map(img => img.complete
    ? Promise.resolve()
    : new Promise(res => { img.addEventListener('load', res, {once:true}); img.addEventListener('error', res, {once:true}); })));
  await new Promise(r => setTimeout(r, 400));
  const boardDataUrl = await htmlToImage.toPng(node, { pixelRatio: pixelRatio, cacheBust: false });
  const boardImg = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = boardDataUrl; });

  const scale = pixelRatio;
  const headerH = Math.max(96 * scale, boardImg.width * 0.10);
  const canvasW = boardImg.width;
  const canvasH = boardImg.height + headerH;
  const canvas = document.createElement('canvas');
  canvas.width = canvasW; canvas.height = canvasH;
  const ctx = canvas.getContext('2d');
  // Dark header band + the board beneath it.
  ctx.fillStyle = '#111111';
  ctx.fillRect(0, 0, canvasW, headerH);
  ctx.drawImage(boardImg, 0, headerH);

  const pad = 20 * scale;
  const logoSize = headerH * 0.6;
  const spacing = 12 * scale;
  const wmSize = headerH * 0.42;
  ctx.font = `bold ${wmSize}px Arial, sans-serif`;
  const tierW = ctx.measureText('Tier').width;
  ctx.font = `400 ${wmSize}px Arial, sans-serif`;
  const vibeW = ctx.measureText('Vibe').width;
  const siteW = tierW + vibeW;
  const rightX = canvasW - pad;

  // Title (left, white bold). Wrap to TWO lines if it overflows; ellipsize line 2.
  const titleSize = Math.max(28 * scale, headerH * 0.32);
  const titleFont = `bold ${titleSize}px Arial, sans-serif`;
  ctx.font = titleFont;
  ctx.fillStyle = '#ffffff';
  ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  const availW = Math.max(60 * scale, canvasW - pad - pad - logoSize - spacing - siteW);
  const t = title || '';
  if (ctx.measureText(t).width <= availW) {
    // Fits one line — keep it centered.
    ctx.fillText(t, pad, headerH / 2 + 3 * scale);
  } else {
    // Two-line wrap by character (CJK-safe, no word boundary assumption).
    let line1 = '', line2 = '';
    for (const ch of t) {
      if (ctx.measureText(line1 + ch).width <= availW) line1 += ch;
      else if (ctx.measureText(line2 + ch).width <= availW) line2 += ch;
      else break;
    }
    const remaining = t.slice(line1.length + line2.length);
    if (remaining) {
      while (line2.length > 0 && ctx.measureText(line2 + '…').width > availW) line2 = line2.slice(0, -1);
      line2 += '…';
    }
    const lineGap = titleSize * 1.2;
    ctx.fillText(line1, pad, headerH / 2 - lineGap / 2 + 3 * scale);
    if (line2) ctx.fillText(line2, pad, headerH / 2 + lineGap / 2 + 3 * scale);
  }

  // Wordmark (right): "Vibe" grey, "Tier" white bold just before it.
  ctx.textBaseline = 'middle';
  ctx.fillStyle = '#9ca3af';
  ctx.font = `400 ${wmSize}px Arial, sans-serif`;
  ctx.textAlign = 'right';
  ctx.fillText('Vibe', rightX, headerH / 2 + 3 * scale);
  ctx.fillStyle = '#ffffff';
  ctx.font = `bold ${wmSize}px Arial, sans-serif`;
  ctx.textAlign = 'right';
  ctx.fillText('Tier', rightX - vibeW - 0.4, headerH / 2 + 3 * scale);

  // Logo (right of wordmark's left edge).
  if (logoDataUri) {
    try {
      const logo = await new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = logoDataUri; });
      if (logo) {
        const logoY = (headerH - logoSize) / 2;
        const logoX = rightX - siteW - spacing - logoSize;
        ctx.drawImage(logo, logoX, logoY, logoSize, logoSize);
      }
    } catch (e) {}
  }
  return canvas.toDataURL('image/png');
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

    title = _fetch_title(slug)
    logo_data_uri = _load_logo_data_uri()
    print(f"Title: {title or '(none)'}  |  logo: {'yes' if logo_data_uri else 'no'}")

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
            try:
                page.wait_for_function(
                    "typeof window.htmlToImage === 'object' && typeof window.htmlToImage.toPng === 'function'",
                    timeout=30000,
                )
            except Exception:
                raise SystemExit(
                    "html-to-image failed to load from the CDN. High-res capture "
                    "aborted — the video will fall back to the 600px thumb from "
                    "Step 2 (fetch_tierlist.py)."
                )

            try:
                data_url = page.evaluate(
                    f"async (params) => {{ {_INJECT} return await captureBoard(params.pixelRatio, params.title, params.logoDataUri); }}",
                    {"pixelRatio": pixel_ratio, "title": title, "logoDataUri": logo_data_uri},
                )
            except Exception as e:
                raise SystemExit(
                    f"High-res capture failed (often CDN CORS / canvas taint, or the "
                    f"tier-grid changed). Falling back to the 600px thumb from Step 2. "
                    f"Detail: {e}"
                )
            if not data_url or not data_url.startswith("data:image/png"):
                raise SystemExit("Capture returned no image data — falling back to the 600px thumb from Step 2.")

            b64 = data_url.split(",", 1)[1]
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"High-res board captured (with title bar): {out_path}")
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
