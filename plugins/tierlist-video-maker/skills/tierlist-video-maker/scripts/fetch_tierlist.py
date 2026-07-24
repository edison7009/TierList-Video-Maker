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
            ext = _ext_from_url(img_url, default=".webp")
            filename = f"card_{card_index:03d}{ext}"
            filepath = os.path.join(img_dir, filename)
            print(f"  [{tier_name}] card {card_index}: {img_url}")
            ok = download(img_url, filepath)
            cards.append({
                "index": card_index,
                "image_file": filename if ok else None,
                "image_url": img_url,
                "card_id": img_obj.get("id", "") if isinstance(img_obj, dict) else "",
                "label": "",  # filled by AI vision (API returns no text labels)
            })
            card_index += 1

        if cards:
            tiers.append({
                "tier_index": i,
                "name": tier_name,
                "color": tier_color,
                "cards": cards,
            })

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
        "source_url": f"https://tiervibe.com/t/{slug}",
    }

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nManifest saved: {manifest_path}")
    print(f"Total cards downloaded: {card_index}")
    print(f"Board image source: {board_source} ({'ok' if board_ok else 'FAILED'})")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch TierVibe tier list data and images")
    parser.add_argument("url", help="TierVibe URL or public slug")
    parser.add_argument("-o", "--output", default="tierlist_work", help="Output directory")
    args = parser.parse_args()
    fetch_tierlist(args.url, args.output)
