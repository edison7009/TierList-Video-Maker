#!/usr/bin/env python3
"""Compose a narrated tier-list video with a scrolling board background.

Usage:
    python generate_video.py <work_dir> [-o output.mp4] [--resolution 1920x1080]

Expects in <work_dir>:
    manifest.json           - from fetch_tierlist.py
    narration_script.json   - AI-generated script with segments
    audio_manifest.json     - from tts_narration.py
    board_source.<ext>      - the real server board image (from fetch_tierlist.py)
                              OR board.png (fallback render from render_board.py)
    images/                 - card images
    audio/                  - narration audio files
"""

import argparse
import json
import os
import platform
import sys


def ensure_deps():
    missing = []
    try:
        import moviepy  # noqa: F401
    except ImportError:
        missing.append("moviepy>=2.0")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow")
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    if missing:
        import subprocess
        print(f"Installing: {', '.join(missing)}...", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "-q"])


ensure_deps()

from PIL import Image, ImageDraw, ImageFont
import numpy as np


# ---------------------------------------------------------------------------
# Cross-platform font helper
# ---------------------------------------------------------------------------
def get_font(size: int):
    system = platform.system()
    if system == "Windows":
        candidates = ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "arial.ttf"]
    elif system == "Darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    else:
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


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------
def darken(img: Image.Image, factor: float = 0.4) -> Image.Image:
    arr = np.array(img).astype(np.float32) * factor
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def add_rounded_border(img: Image.Image, border: int = 5,
                       color=(255, 255, 255), radius: int = 16) -> Image.Image:
    w, h = img.size
    bordered = Image.new("RGBA", (w + border * 2, h + border * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(bordered)
    draw.rounded_rectangle(
        [0, 0, w + border * 2 - 1, h + border * 2 - 1],
        radius=radius, fill=(*color, 255),
    )
    bordered.paste(img.convert("RGBA"), (border, border))
    return bordered


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------
def crop_board_at(board: Image.Image, scroll_y: int,
                 target_w: int, target_h: int) -> Image.Image:
    board_w, board_h = board.size
    max_scroll = max(0, board_h - target_h)
    scroll_y = max(0, min(int(scroll_y), max_scroll))
    return board.crop((0, scroll_y, target_w, scroll_y + target_h))


def create_card_overlay(frame: Image.Image, card_img: Image.Image,
                        tier_name: str, tier_color: str, card_label: str,
                        target_w: int, target_h: int) -> Image.Image:
    result = frame.copy()

    card_target_h = int(target_h * 0.50)
    scale = card_target_h / card_img.height
    card_target_w = int(card_img.width * scale)
    if card_target_w > target_w * 0.65:
        card_target_w = int(target_w * 0.65)
        scale = card_target_w / card_img.width
        card_target_h = int(card_img.height * scale)
    card_resized = card_img.resize((card_target_w, card_target_h), Image.LANCZOS)
    card_bordered = add_rounded_border(card_resized, border=5, radius=16)

    cx = (target_w - card_bordered.width) // 2
    cy = (target_h - card_bordered.height) // 2 - int(target_h * 0.03)

    overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    pad = 30
    overlay_draw.rounded_rectangle(
        [cx - pad, cy - pad,
         cx + card_bordered.width + pad, cy + card_bordered.height + pad],
        radius=24, fill=(0, 0, 0, 140),
    )
    result = Image.alpha_composite(result.convert("RGBA"), overlay).convert("RGB")

    result.paste(card_bordered.convert("RGB"), (cx, cy),
                 card_bordered.split()[3] if card_bordered.mode == "RGBA" else None)

    draw = ImageDraw.Draw(result)
    font_large = get_font(max(26, target_h // 28))
    font_small = get_font(max(18, target_h // 38))

    badge_text = f" {tier_name} "
    bb = draw.textbbox((0, 0), badge_text, font=font_large)
    bw, bh = bb[2] - bb[0] + 24, bb[3] - bb[1] + 14
    bx, by = int(target_w * 0.04), int(target_h * 0.04)
    tc = tier_color.lstrip("#")
    r, g, b = (int(tc[0:2], 16), int(tc[2:4], 16), int(tc[4:6], 16)) if len(tc) == 6 else (255, 127, 127)
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=10, fill=(r, g, b))
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    draw.text((bx + 12, by + 5), badge_text.strip(),
              fill=(0, 0, 0) if lum > 128 else (255, 255, 255), font=font_large)

    if card_label:
        lb = draw.textbbox((0, 0), card_label, font=font_small)
        lw = lb[2] - lb[0]
        lx = (target_w - lw) // 2
        ly = cy + card_bordered.height + 14
        draw.text((lx + 2, ly + 2), card_label, fill=(0, 0, 0), font=font_small)
        draw.text((lx, ly), card_label, fill=(255, 255, 255), font=font_small)

    return result


def create_title_frame(board: Image.Image, title: str,
                      target_w: int, target_h: int) -> Image.Image:
    board_h = board.size[1]
    mid_scroll = max(0, (board_h - target_h) // 2)
    frame = crop_board_at(board, mid_scroll, target_w, target_h)
    frame = darken(frame, 0.45)

    draw = ImageDraw.Draw(frame)
    font = get_font(max(38, target_h // 16))
    bb = draw.textbbox((0, 0), title, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x, y = (target_w - tw) // 2, (target_h - th) // 2
    draw.text((x + 3, y + 3), title, fill=(0, 0, 0), font=font)
    draw.text((x, y), title, fill=(255, 255, 255), font=font)
    return frame


# ---------------------------------------------------------------------------
# Audio helper
# ---------------------------------------------------------------------------
def get_audio_duration(audio_path: str) -> float:
    try:
        from mutagen.mp3 import MP3
        return MP3(audio_path).info.length
    except Exception:
        pass
    try:
        from moviepy import AudioFileClip
        clip = AudioFileClip(audio_path)
        dur = clip.duration
        clip.close()
        return dur
    except Exception:
        return 5.0


# ---------------------------------------------------------------------------
# Subtitle generation (SRT)
# ---------------------------------------------------------------------------
def _srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(script: dict, audio_map: dict, work_dir: str,
                 intro_duration: float, gap_duration: float) -> str:
    segments = script.get("segments", [])
    srt_path = os.path.join(work_dir, "subtitles.srt")
    lines = []
    sub_idx = 1
    current_time = intro_duration

    intro_text = script.get("intro", "")
    if intro_text:
        lines.append(str(sub_idx))
        lines.append(f"{_srt_time(0)} --> {_srt_time(intro_duration)}")
        lines.append(intro_text)
        lines.append("")
        sub_idx += 1

    for seg in segments:
        idx = seg["index"]
        text = seg.get("narration", "")
        if not text.strip():
            continue
        audio_path = audio_map.get(idx)
        if audio_path and os.path.exists(audio_path):
            dur = get_audio_duration(audio_path) + 0.5
        else:
            dur = 5.0
        start = current_time
        end = current_time + dur
        lines.append(str(sub_idx))
        lines.append(f"{_srt_time(start)} --> {_srt_time(end)}")
        lines.append(text)
        lines.append("")
        sub_idx += 1
        current_time = end + gap_duration

    outro_text = script.get("outro", "")
    if outro_text:
        lines.append(str(sub_idx))
        lines.append(f"{_srt_time(current_time)} --> {_srt_time(current_time + intro_duration)}")
        lines.append(outro_text)
        lines.append("")

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Subtitles saved: {srt_path}")
    return srt_path


# ---------------------------------------------------------------------------
# Board selection
# ---------------------------------------------------------------------------
def resolve_board_path(work_dir: str, manifest: dict) -> str:
    """Prefer the high-res Playwright capture, then the server thumb, then fallback render."""
    hd = os.path.join(work_dir, "board_hd.png")
    if os.path.exists(hd):
        print("Using high-res board: board_hd.png (captured from public page)")
        return hd
    board_file = manifest.get("board_image_file")
    if board_file:
        p = os.path.join(work_dir, board_file)
        if os.path.exists(p):
            print(f"Using server board image: {board_file} [{manifest.get('board_image_source')}] (600px)")
            return p
    rendered = os.path.join(work_dir, "board.png")
    if os.path.exists(rendered):
        print("Using rendered fallback board: board.png")
        return rendered
    raise SystemExit(
        "No board image found. Run capture_board.py for a high-res board, "
        "or fetch_tierlist.py for the server thumb, or render_board.py for a fallback."
    )


# ---------------------------------------------------------------------------
# Main video generation
# ---------------------------------------------------------------------------
def generate_video(work_dir: str, output_path: str, resolution: str = "1920x1080",
                   intro_duration: float = 3.0, gap_duration: float = 0.8):
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

    target_w, target_h = map(int, resolution.split("x"))

    with open(os.path.join(work_dir, "manifest.json"), "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(os.path.join(work_dir, "narration_script.json"), "r", encoding="utf-8") as f:
        script = json.load(f)

    audio_map = {}
    audio_manifest_path = os.path.join(work_dir, "audio_manifest.json")
    if os.path.exists(audio_manifest_path):
        with open(audio_manifest_path, "r", encoding="utf-8") as f:
            am = json.load(f)
        for seg in am.get("segments", []):
            if seg.get("audio_file"):
                audio_map[seg["index"]] = os.path.join(work_dir, "audio", seg["audio_file"])

    board_path = resolve_board_path(work_dir, manifest)
    board = Image.open(board_path).convert("RGB")

    if board.width != target_w:
        scale = target_w / board.width
        new_h = int(board.height * scale)
        board = board.resize((target_w, new_h), Image.LANCZOS)
    board_w, board_h = board.size
    max_scroll = max(0, board_h - target_h)
    print(f"Board: {board_w}x{board_h}, max scroll: {max_scroll}px")

    title = manifest.get("title", "Tier List")
    seg_lookup = {s["index"]: s for s in script.get("segments", [])}
    scripted_indices = {s["index"] for s in script.get("segments", []) if s.get("index", -1) >= 0}

    clips_info = []
    total_content_dur = intro_duration
    img_dir = os.path.join(work_dir, "images")

    for tier in manifest.get("tiers", []):
        for card in tier.get("cards", []):
            idx = card["index"]
            if scripted_indices and idx not in scripted_indices:
                continue
            img_file = card.get("image_file")
            if not img_file:
                continue
            card_path = os.path.join(img_dir, img_file)
            if not os.path.exists(card_path):
                continue
            audio_path = audio_map.get(idx)
            if audio_path and os.path.exists(audio_path):
                dur = get_audio_duration(audio_path) + 0.5
            else:
                dur = 5.0
            clips_info.append((tier, card, dur, audio_path))
            total_content_dur += dur + gap_duration
    total_content_dur += intro_duration  # outro

    clips = []

    intro_img = create_title_frame(board, title, target_w, target_h)
    clips.append(ImageClip(np.array(intro_img), duration=intro_duration))

    elapsed = intro_duration
    for tier, card, dur, audio_path in clips_info:
        idx = card["index"]
        seg = seg_lookup.get(idx, {})
        card_label = seg.get("label", card.get("label", ""))
        tier_name = tier["name"]
        tier_color = tier["color"]

        scroll_progress = elapsed / total_content_dur
        scroll_y = int(scroll_progress * max_scroll)

        bg_frame = crop_board_at(board, scroll_y, target_w, target_h)
        bg_frame = darken(bg_frame, 0.55)

        card_path = os.path.join(img_dir, card["image_file"])
        card_img = Image.open(card_path).convert("RGB")
        frame = create_card_overlay(bg_frame, card_img, tier_name, tier_color,
                                     card_label, target_w, target_h)

        clip = ImageClip(np.array(frame), duration=dur)
        if audio_path and os.path.exists(audio_path):
            clip = clip.with_audio(AudioFileClip(audio_path))
        clips.append(clip)

        gap_scroll = int(((elapsed + dur) / total_content_dur) * max_scroll)
        gap_bg = crop_board_at(board, gap_scroll, target_w, target_h)
        gap_bg = darken(gap_bg, 0.55)
        clips.append(ImageClip(np.array(gap_bg), duration=gap_duration))

        elapsed += dur + gap_duration

    outro_img = create_title_frame(board, title, target_w, target_h)
    clips.append(ImageClip(np.array(outro_img), duration=intro_duration))

    generate_srt(script, audio_map, work_dir, intro_duration, gap_duration)

    print(f"Compositing {len(clips)} clips ({total_content_dur:.1f}s total)...")
    final = concatenate_videoclips(clips, method="compose")

    print(f"Writing video to {output_path}...")
    final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger="bar",
    )
    final.close()
    print(f"Done! Video saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate tier-list video")
    parser.add_argument("work_dir", help="Working directory")
    parser.add_argument("-o", "--output", default=None, help="Output MP4 path")
    parser.add_argument("--resolution", default="1920x1080", help="WxH")
    parser.add_argument("--intro-duration", type=float, default=3.0)
    args = parser.parse_args()
    output = args.output or os.path.join(args.work_dir, "tierlist_video.mp4")
    generate_video(args.work_dir, output, args.resolution, args.intro_duration)
