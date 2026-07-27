#!/usr/bin/env python3
"""Fetch a TierVibe tier list: download the board image + card images, output manifest JSON.

Usage:
    python fetch_tierlist.py "<URL_OR_SLUG>" -o <work_dir>

The board image (the video background) is taken from the server in priority order:
fullImageUrl (1600px) -> thumbUrl (600px) -> /og/<slug>.jpg. See references/tiervibe-api.md.
A script must NOT try to click the in-browser "download whole image" button — the
server already stores the board image; we just fetch the URL.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

API_BASE = "https://tiervibe.com/api/posts"
OG_URL = "https://tiervibe.com/og/{slug}.jpg"
USER_AGENT = "TierListVideoMaker/1.0"
IMG_TIMEOUT = 30

# Text cards are rendered as square swatches at this size.
TEXT_CARD_SIZE = 640
TEXT_CARD_PAD = 56

if sys.platform == "win32":
    # The Windows console defaults to the ANSI code page (GBK on zh-CN), which
    # turns every CJK title and label in the log into unreadable bytes. This
    # skill explicitly supports CJK boards, so a readable log isn't optional.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _hex_rgb(value: str, fallback=(51, 51, 51)):
    """'#e11d48' / 'e11d48' / 'fff' -> (r, g, b). Falls back on anything odd."""
    v = (value or "").lstrip("#").strip()
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) not in (6, 8):
        return fallback
    try:
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def _get_font(size: int):
    """Same CJK-capable font search the render/compose scripts use."""
    from PIL import ImageFont
    if sys.platform == "win32":
        candidates = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
                      r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\arial.ttf"]
    elif sys.platform == "darwin":
        candidates = ["/System/Library/Fonts/PingFang.ttc",
                      "/System/Library/Fonts/Helvetica.ttc"]
    else:
        candidates = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                      "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                      "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_label(draw, text: str, font, max_width: int):
    """Wrap on spaces where possible, per-character for CJK (which has none)."""
    if draw.textlength(text, font=font) <= max_width:
        return [text]
    lines, current = [], ""
    tokens = text.split(" ") if " " in text else list(text)
    joiner = " " if " " in text else ""
    for tok in tokens:
        trial = f"{current}{joiner}{tok}" if current else tok
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = tok
    if current:
        lines.append(current)
    return lines


def _parse_text_card(url: str):
    """'text:<urlencoded label>#<fg>#<bg>' -> (label, fg_rgb, bg_rgb).

    TierVibe encodes a text card's label and its two colors into the card's
    stored imageUrl. Everything the video needs is right here in the data —
    no vision pass required to know what this card says.
    """
    import urllib.parse
    parts = url[len("text:"):].split("#")
    label = urllib.parse.unquote(parts[0]).strip()
    fg = parts[1] if len(parts) > 1 and parts[1] else "ffffff"
    bg = parts[2] if len(parts) > 2 and parts[2] else "333333"
    return label, _hex_rgb(fg, (255, 255, 255)), _hex_rgb(bg)


def _render_text_card(label: str, fg, bg, path: str,
                      size: int = TEXT_CARD_SIZE, pad: int = TEXT_CARD_PAD) -> bool:
    """Draw a text card as the same colored square the board shows.

    Shrinks the font until the wrapped label fits the square, so a long label
    stays inside the card instead of overflowing it.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        import subprocess
        print("Installing Pillow (needed to render text cards)...", file=sys.stderr)
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
        except subprocess.CalledProcessError as e:
            print(f"  [ERROR] cannot render text cards without Pillow ({e}). On "
                  "Debian/Ubuntu or Homebrew Python this is usually PEP 668 — try "
                  "`pip install --user Pillow` or a venv.", file=sys.stderr)
            return False
        from PIL import Image, ImageDraw

    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    avail = size - pad * 2
    lines, font, line_h = [label], _get_font(96), 96
    for font_size in range(96, 27, -4):
        font = _get_font(font_size)
        lines = _wrap_label(draw, label, font, avail)
        line_h = int(font_size * 1.30)
        if len(lines) * line_h <= avail:
            break
    y = (size - len(lines) * line_h) // 2
    for line in lines:
        x = (size - draw.textlength(line, font=font)) / 2
        draw.text((x, y), line, font=font, fill=fg)
        y += line_h
    img.save(path, "PNG")
    return True


def extract_slug(url_or_id: str) -> str:
    """Extract the public slug from a tiervibe.com/t/<slug> URL, or accept it bare."""
    m = re.search(r"tiervibe\.com/t/([A-Za-z0-9]+)", url_or_id)
    if m:
        return m.group(1)
    candidate = url_or_id.strip()
    if re.fullmatch(r"[A-Za-z0-9]{4,30}", candidate):
        return candidate
    raise ValueError(f"Cannot extract slug from: {url_or_id}")


def _ext_from_url(url: str, default: str = ".webp") -> str:
    lower = url.lower().split("?", 1)[0]
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return ".jpg"
    if lower.endswith(".png"):
        return ".png"
    if lower.endswith(".webp"):
        return ".webp"
    return default


def download(url: str, dest: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=IMG_TIMEOUT) as resp, open(dest, "wb") as f:
            f.write(resp.read())
        return True
    except Exception as e:
        print(f"  [WARN] download failed: {url} -> {e}", file=sys.stderr)
        return False


def _pick_board_image(data: dict, slug: str):
    """Return (url, source_label) by priority: fullImageUrl -> thumbUrl -> /og.

    NOTE: fullImageUrl is null on every published post in practice (verified on
    real posts — see references/tiervibe-api.md §2.2). It's kept as the first
    priority for forward compatibility if TierVibe ever ships the 1600px
    variant, but the common path today is thumbUrl. Don't remove this branch
    expecting it to fire — it's intentionally defensive.
    """
    full = data.get("fullImageUrl")
    if full:
        return full, "fullImageUrl"
    thumb = data.get("thumbUrl")
    if thumb:
        return thumb, "thumbUrl"
    return OG_URL.format(slug=slug), "og"


def _is_empty_default_tier(name: str, images) -> bool:
    """Skip tiers that are the placeholder 'Tn' default with no cards."""
    if not name:
        return True
    is_default_label = name.startswith("T") and name[1:].isdigit()
    return is_default_label and not images


def fetch_tierlist(url_or_id: str, out_dir: str) -> dict:
    slug = extract_slug(url_or_id)
    os.makedirs(out_dir, exist_ok=True)
    img_dir = os.path.join(out_dir, "images")
    os.makedirs(img_dir, exist_ok=True)

    # 1. Fetch API data
    api_url = f"{API_BASE}/{slug}"
    print(f"Fetching tier list data: {api_url}")
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=IMG_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Drafts / still-editing posts are not publicly readable -> the API
        # returns 404. Surface the friendly "publish it first" message instead
        # of a raw HTTPError traceback.
        if e.code == 404:
            raise SystemExit(
                f"This tier list is not publicly readable (API returned 404 for {slug}).\n"
                f"Only published TierVibe posts can be turned into a video — drafts / "
                f"still-editing posts are not public and have no board image.\n"
                f"Publish it first at https://tiervibe.com/t/{slug} , then re-run."
            ) from e
        raise SystemExit(f"API request failed (HTTP {e.code}) for {slug}: {e}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"Could not reach the TierVibe API for {slug}: {e}") from e

    # Fail fast on non-published posts. Drafts / "still editing" posts are not
    # publicly readable (the API returns 404 / empty), and the video needs a
    # fully published board. Tell the user clearly instead of failing later
    # with a vague 404 or empty board.
    status = data.get("status")
    if status != "published":
        raise SystemExit(
            f"This tier list is NOT published (status={status or 'unknown'}).\n"
            f"Only published TierVibe posts can be turned into a video — drafts / "
            f"still-editing posts are not publicly readable and have no board image.\n"
            f"Publish it first at https://tiervibe.com/t/{slug} , then re-run."
        )

    title = data.get("title", "Untitled")
    tier_count = data.get("tierCount", 0)
    bg_brightness = data.get("bgBrightness", 0)
    print(f"Title: {title}  |  Tiers: {tier_count}  |  Brightness: {bg_brightness}")

    # 2. Download the board image (the video background) from the server.
    board_url, board_source = _pick_board_image(data, slug)
    board_ext = _ext_from_url(board_url, default=".webp")
    board_file = f"board_source{board_ext}"
    board_path = os.path.join(out_dir, board_file)
    print(f"Downloading board image [{board_source}]: {board_url}")
    board_ok = download(board_url, board_path)
    if not board_ok:
        print("  [ERROR] Could not download the board image from any source.", file=sys.stderr)
        print("          Run render_board.py as a fallback to rebuild the board from card images.",
              file=sys.stderr)

    # 3. Parse tiers and download card images
    tiers = []
    card_index = 0
    downloaded = rendered = failed = with_detail = 0
    for i in range(1, 16):
        tier_name = data.get(f"T{i}name", "") or ""
        tier_color = data.get(f"T{i}color", "#333333")
        tier_images = data.get(f"T{i}images") or []
        if _is_empty_default_tier(tier_name, tier_images):
            continue

        if isinstance(tier_images, dict):
            tier_images = [tier_images]

        cards = []
        for img_obj in tier_images:
            img_url = img_obj.get("imageUrl", "") if isinstance(img_obj, dict) else ""
            if not img_url:
                continue
            if img_url.startswith("text:"):
                # Text card: the label and both colors live in the pseudo-URL, so
                # we render the swatch locally instead of downloading anything —
                # and we already KNOW what the card says, no vision pass needed.
                label, fg, bg = _parse_text_card(img_url)
                filename = f"card_{card_index:03d}.png"
                filepath = os.path.join(img_dir, filename)
                print(f"  [{tier_name}] card {card_index}: text card — {label}")
                ok = _render_text_card(label, fg, bg, filepath)
                if ok:
                    rendered += 1
                else:
                    failed += 1
                card_label, label_source = (label, "text_card_data") if ok else ("", "")
            else:
                ext = _ext_from_url(img_url, default=".webp")
                filename = f"card_{card_index:03d}{ext}"
                filepath = os.path.join(img_dir, filename)
                print(f"  [{tier_name}] card {card_index}: {img_url}")
                ok = download(img_url, filepath)
                if ok:
                    downloaded += 1
                else:
                    failed += 1
                # Image cards carry no text in the API — a vision pass fills this.
                card_label, label_source = "", "ai_vision"
            # Preserve the author's per-card explanation (`detail`). The API
            # returns it on the card object; narration (Step 6) uses it as
            # reference material so the video reflects the author's reasoning
            # instead of generic model knowledge. May be empty - not every card
            # has one. See references/tiervibe-api.md §3.
            detail_text = (img_obj.get("detail") or "") if isinstance(img_obj, dict) else ""
            if detail_text.strip():
                with_detail += 1
            cards.append({
                "index": card_index,
                "image_file": filename if ok else None,
                "image_url": img_url,
                "card_id": img_obj.get("id", "") if isinstance(img_obj, dict) else "",
                "label": card_label,
                "label_source": label_source,
                "detail": detail_text,
            })
            card_index += 1

        if cards:
            tiers.append({
                "tier_index": i,
                "name": tier_name,
                "color": tier_color,
                "cards": cards,
            })

    # Top-level cardDetails ([{id, content}]) - the author's per-card
    # explanations, duplicated from each card's `detail`. Kept whole as a
    # cross-check source; the per-card `detail` field is what narration reads.
    raw_card_details = data.get("cardDetails") or []
    card_details = [
        {"id": cd.get("id", ""), "content": cd.get("content") or ""}
        for cd in raw_card_details if isinstance(cd, dict)
    ]

    manifest = {
        "public_id": slug,
        "title": title,
        "tier_count": len(tiers),
        "total_cards": card_index,
        "bg_brightness": bg_brightness,
        "board_image_file": board_file if board_ok else None,
        "board_image_url": board_url,
        "board_image_source": board_source,
        "tiers": tiers,
        "card_details": card_details,
        "source_url": f"https://tiervibe.com/t/{slug}",
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nManifest saved: {manifest_path}")
    # Report what actually happened, not just the card count. The old line said
    # "Total cards downloaded: 27" even when all 27 failed and images/ was empty,
    # which let a board with no usable card images look like a clean run.
    print(f"Cards: {card_index} total — {downloaded} downloaded, "
          f"{rendered} text cards rendered, {failed} FAILED, {with_detail} with detail")
    if failed:
        print(f"  [WARN] {failed} card(s) have no image on disk; the video will "
              "skip them.", file=sys.stderr)
    if card_index and not (downloaded + rendered):
        print("  [ERROR] not a single card image was obtained — images/ is empty. "
              "generate_video.py would produce an intro+outro and nothing else.",
              file=sys.stderr)
    print(f"Board image source: {board_source} ({'ok' if board_ok else 'FAILED'})")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch TierVibe tier list data and images")
    parser.add_argument("url", help="TierVibe URL or public slug")
    parser.add_argument("-o", "--output", default="tierlist_work", help="Output directory")
    args = parser.parse_args()
    fetch_tierlist(args.url, args.output)
