#!/usr/bin/env python3
"""FALLBACK board renderer — rebuild a tier-list board from downloaded card images.

Usage:
    python render_board.py <work_dir> [-o board.png] [--width 1920]

You normally do NOT need this. fetch_tierlist.py already downloads the real server
board image (fullImageUrl / thumbUrl / og — see references/tiervibe-api.md), which
is the exact board and the preferred video background. Run this ONLY if the
manifest's `board_image_file` is None (the server had no board image for that post).

This renders an APPROXIMATE board (tier labels + card grid) from the card images;
it will not match TierVibe's exact layout, so prefer the server image whenever
possible. Output: <work_dir>/board.png.
"""

import argparse
import json
import os
import platform
import sys

if sys.platform == "win32":
    # The Windows console defaults to the ANSI code page (GBK on zh-CN), which
    # turns every CJK title, label and path in the log into unreadable bytes.
    # This skill explicitly supports CJK boards, so readable logs are required.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def get_font(size: int):
    """Load a CJK-capable font cross-platform."""
    from PIL import ImageFont
    system = platform.system()
    candidates = []
    if system == "Windows":
        candidates = ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"]
    elif system == "Darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:  # Linux
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def render_board(work_dir: str, output_path: str, board_width: int = 1920):
    from PIL import Image, ImageDraw

    with open(os.path.join(work_dir, "manifest.json"), "r", encoding="utf-8") as f:
        manifest = json.load(f)

    img_dir = os.path.join(work_dir, "images")
    tiers = manifest.get("tiers", [])
    title = manifest.get("title", "Tier List")

    padding = 24
    tier_label_w = int(board_width * 0.12)
    card_area_w = board_width - tier_label_w - padding * 3
    card_h = int(board_width * 0.10)
    card_gap = 10
    tier_gap = 8
    title_h = int(board_width * 0.06)

    total_h = title_h + padding * 2
    for tier in tiers:
        cards = tier.get("cards", [])
        if not cards:
            continue
        row_h = card_h + card_gap
        cards_per_row = max(1, card_area_w // (card_h + card_gap))
        rows = (len(cards) + cards_per_row - 1) // cards_per_row
        tier_h = max(row_h, rows * row_h) + tier_gap
        total_h += tier_h + padding

    brightness = manifest.get("bg_brightness", 0)
    gray = int(brightness * 2.55)
    board = Image.new("RGB", (board_width, total_h), (gray, gray, gray))
    draw = ImageDraw.Draw(board)

    title_font = get_font(max(28, board_width // 30))
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_tw = title_bbox[2] - title_bbox[0]
    title_x = (board_width - title_tw) // 2
    title_y = padding
    draw.text((title_x + 2, title_y + 2), title, fill=(0, 0, 0), font=title_font)
    text_color = (0, 0, 0) if brightness > 50 else (255, 255, 255)
    draw.text((title_x, title_y), title, fill=text_color, font=title_font)

    y_cursor = title_h + padding
    tier_font = get_font(max(18, board_width // 50))

    for tier in tiers:
        cards = tier.get("cards", [])
        if not cards:
            continue

        tier_name = tier["name"]
        tier_color_hex = tier.get("color", "#FF7F7F").lstrip("#")
        if len(tier_color_hex) == 6:
            tr = int(tier_color_hex[0:2], 16)
            tg = int(tier_color_hex[2:4], 16)
            tb = int(tier_color_hex[4:6], 16)
        else:
            tr, tg, tb = 255, 127, 127

        loaded_cards = []
        for card in cards:
            img_file = card.get("image_file")
            if not img_file:
                continue
            card_path = os.path.join(img_dir, img_file)
            if not os.path.exists(card_path):
                continue
            try:
                loaded_cards.append(Image.open(card_path).convert("RGBA"))
            except Exception:
                continue
        if not loaded_cards:
            continue

        x_cursor = tier_label_w + padding * 2
        row_top = y_cursor
        max_row_h = card_h

        for cimg in loaded_cards:
            scale = card_h / cimg.height
            cw = int(cimg.width * scale)
            if cw > card_area_w:
                cw = card_area_w
                scale = cw / cimg.width
            ch = int(cimg.height * scale)
            cimg_resized = cimg.resize((cw, ch), Image.LANCZOS)

            if x_cursor + cw > board_width - padding:
                x_cursor = tier_label_w + padding * 2
                row_top += max_row_h + card_gap
                max_row_h = ch

            if cimg_resized.mode == "RGBA":
                board.paste(cimg_resized, (x_cursor, row_top), cimg_resized)
            else:
                board.paste(cimg_resized, (x_cursor, row_top))
            x_cursor += cw + card_gap
            max_row_h = max(max_row_h, ch)

        tier_bottom = row_top + max_row_h

        draw.rectangle(
            [padding, y_cursor, tier_label_w + padding, tier_bottom],
            fill=(tr, tg, tb),
        )
        name_bbox = draw.textbbox((0, 0), tier_name, font=tier_font)
        name_h = name_bbox[3] - name_bbox[1]
        name_w = name_bbox[2] - name_bbox[0]
        name_x = padding + (tier_label_w - name_w) // 2
        name_y = y_cursor + (tier_bottom - y_cursor - name_h) // 2
        luminance = 0.299 * tr + 0.587 * tg + 0.114 * tb
        label_text_color = (0, 0, 0) if luminance > 128 else (255, 255, 255)
        draw.text((name_x, name_y), tier_name, fill=label_text_color, font=tier_font)

        y_cursor = tier_bottom + tier_gap + padding

    board = board.crop((0, 0, board_width, y_cursor))
    board.save(output_path, quality=95)
    print(f"Board rendered (FALLBACK): {output_path} ({board.width}x{board.height})")
    return board.width, board.height


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render tier list board image (fallback)")
    parser.add_argument("work_dir", help="Working directory with manifest + images")
    parser.add_argument("-o", "--output", default=None, help="Output image path")
    parser.add_argument("--width", type=int, default=1920, help="Board width in pixels")
    args = parser.parse_args()
    output = args.output or os.path.join(args.work_dir, "board.png")
    render_board(args.work_dir, output, args.width)
