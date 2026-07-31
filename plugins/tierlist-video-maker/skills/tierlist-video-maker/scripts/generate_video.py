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


if sys.platform == "win32":
    # The Windows console defaults to the ANSI code page (GBK on zh-CN), turning
    # every CJK title, label and output path in the log into unreadable bytes.
    # This skill explicitly supports CJK boards, so readable logs aren't optional.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


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
def fit_board(board, target_w: int, target_h: int, scroll_threshold: float = 0.25):
    """Fit the board image to the frame. Returns (image, scrollable).

    Scaling to frame width and scrolling vertically is only right when the board
    is genuinely taller than the frame. Doing it unconditionally is what cut the
    bottom tier off a 2450x1449 board: scaled to 1920 wide it comes to 1135 high,
    just 55px over a 1080 frame — so the opening frame (scroll 0) silently lost
    its last row, the closing frame lost the title bar, and the "scrolling
    background" travelled 55px that nobody can see.

    Worse in portrait: a wide board scaled to 1080 wide is ~638 high, and cropping
    a 1920-high window out of it gives 1282px of pure black, because PIL's crop()
    pads out-of-bounds regions instead of raising.

    So: scroll only when scaling to width leaves the board meaningfully taller
    than the frame (>25% by default). Otherwise contain it — whole board visible,
    padded with the board's own background color so the seam doesn't show.
    """
    bw, bh = board.size
    scaled_h = int(bh * target_w / bw)
    if (scaled_h - target_h) / target_h > scroll_threshold:
        return board.resize((target_w, scaled_h), Image.LANCZOS), True

    scale = min(target_w / bw, target_h / bh)
    fitted = board.resize((max(1, int(bw * scale)), max(1, int(bh * scale))), Image.LANCZOS)
    pad_color = board.getpixel((2, 2))  # title-bar corner: blends with the board
    canvas = Image.new("RGB", (target_w, target_h), pad_color)
    canvas.paste(fitted, ((target_w - fitted.width) // 2, (target_h - fitted.height) // 2))
    return canvas, False


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


def has_transparency(img: Image.Image) -> bool:
    if img.mode == "P":
        return "transparency" in img.info
    if img.mode in ("RGBA", "LA"):
        alpha = img.getchannel("A")
        return alpha.getextrema()[0] < 255
    return False


def resize_rgba_clean(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize RGBA without letting hidden transparent RGB create dark halos."""
    rgba = img.convert("RGBA")
    arr = np.asarray(rgba).astype(np.float32)
    alpha = arr[..., 3:4] / 255.0
    arr[..., :3] *= alpha
    resized = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA").resize(size, Image.LANCZOS)

    out = np.asarray(resized).astype(np.float32)
    out_alpha = out[..., 3:4] / 255.0
    np.divide(out[..., :3], out_alpha, out=out[..., :3], where=out_alpha > 0)
    out[..., :3] = np.where(out_alpha > 0, out[..., :3], 0)
    return Image.fromarray(out.clip(0, 255).astype(np.uint8), "RGBA")


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
    # Transparent cutout cards need a calm surface behind them. A semi-transparent
    # glass panel showed the busy tier-list background through it and its outline
    # looked like an accidental border. Use a clean solid-black stage instead:
    # no outline, no blur edge, no transparency behind the cutout.
    card_resized = resize_rgba_clean(card_img, (card_target_w, card_target_h))
    cx = (target_w - card_resized.width) // 2
    cy = (target_h - card_resized.height) // 2 - int(target_h * 0.03)
    pad = 24
    if has_transparency(card_resized):
        panel_pad = max(pad, int(target_w * 0.018))
        panel_rect = [
            cx - panel_pad,
            cy - panel_pad,
            cx + card_resized.width + panel_pad,
            cy + card_resized.height + panel_pad,
        ]
        backing = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        ImageDraw.Draw(backing).rectangle(panel_rect, fill=(0, 0, 0, 255))
        result = Image.alpha_composite(result.convert("RGBA"), backing)
    else:
        backing = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        ImageDraw.Draw(backing).rectangle(
            [cx - pad, cy - pad, cx + card_resized.width + pad, cy + card_resized.height + pad],
            fill=(0, 0, 0, 140),
        )
        result = Image.alpha_composite(result.convert("RGBA"), backing)
    result.alpha_composite(card_resized, (cx, cy))
    result = result.convert("RGB")

    # No tier badge (top-left): the scrolling background already shows the full
    # board with every tier label, so a badge here is redundant (user feedback).
    # No card label text: the card image is clear on its own, and a wrong
    # AI-guessed label under it would be misleading (user feedback).

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
        # Neither probe worked (mutagen missing / 0-byte file / decode error).
        # Falling back to a 5.0s guess will desync subtitles from the real audio
        # if the audio later loads in moviepy with a different length — warn so
        # the operator knows a guess was used.
        print(f"  [WARN] could not probe audio duration for {audio_path}; "
              f"assuming 5.0s (subtitles may desync).", file=sys.stderr)
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


def _has_cjk(text: str) -> bool:
    return any("㐀" <= ch <= "鿿" or "぀" <= ch <= "ヿ"
               or "가" <= ch <= "힯" for ch in text)


def _split_text_for_cues(text: str):
    """Break one narration block into reader-sized subtitle cues.

    A whole intro used to go out as a single cue: 18.5 seconds, four sentences,
    60+ characters. Players stack that across the screen and nobody can follow
    it. Netflix-style limits: ~24 chars per cue for CJK (no spaces, denser
    glyphs), ~42 for Latin.
    """
    import re
    text = " ".join(text.split())
    limit = 24 if _has_cjk(text) else 42
    if len(text) <= limit:
        return [text]

    # Split after sentence-final punctuation, keeping the punctuation attached.
    parts = [p.strip() for p in re.split(r"(?<=[。！？；!?;.])", text) if p.strip()]
    joiner = "" if _has_cjk(text) else " "

    merged, current = [], ""
    for part in parts:
        if not current:
            current = part
        elif len(current) + len(part) <= limit:
            current = f"{current}{joiner}{part}"
        else:
            merged.append(current)
            current = part
    if current:
        merged.append(current)

    # A single sentence can still be over the limit — fall back to commas, then
    # to a hard wrap, so no cue is ever wildly oversized.
    cues = []
    for cue in merged:
        if len(cue) <= limit * 1.5:
            cues.append(cue)
            continue
        chunks = [c.strip() for c in re.split(r"(?<=[，,、])", cue) if c.strip()]
        buf = ""
        for chunk in chunks:
            if not buf:
                buf = chunk
            elif len(buf) + len(chunk) <= limit:
                buf = f"{buf}{joiner}{chunk}"
            else:
                cues.append(buf)
                buf = chunk
        if buf:
            cues.append(buf)
    out = []
    for cue in cues:
        while len(cue) > limit * 1.8:
            out.append(cue[:limit])
            cue = cue[limit:]
        out.append(cue)
    return [c for c in out if c]


def _emit_cues(lines: list, sub_idx: int, text: str, start: float, end: float) -> int:
    """Append text as one or more cues spanning [start, end); return next index.

    Time is shared out in proportion to cue length, so a long sentence holds the
    screen longer than a short one and the block still ends exactly at `end`.
    """
    cues = _split_text_for_cues(text)
    total = sum(len(c) for c in cues) or 1
    span = max(0.0, end - start)
    t = start
    for i, cue in enumerate(cues):
        # Last cue lands exactly on `end` — no rounding drift into the next block.
        cue_end = end if i == len(cues) - 1 else t + span * len(cue) / total
        lines.append(str(sub_idx))
        lines.append(f"{_srt_time(t)} --> {_srt_time(cue_end)}")
        lines.append(cue)
        lines.append("")
        sub_idx += 1
        t = cue_end
    return sub_idx


def generate_srt(script: dict, audio_map: dict, work_dir: str,
                 intro_duration: float, gap_duration: float,
                 intro_dur_actual: float = None,
                 outro_dur_actual: float = None,
                 seg_durations: dict = None) -> str:
    """Generate subtitles.

    Timing MUST follow the actual audio-clip durations used by generate_video,
    not a fixed --intro-duration. The old code used ``intro_duration`` (default
    3.0s) as the intro subtitle end AND as the start offset for every segment,
    while the real intro clip was ``intro_audio.duration + 0.3`` — so when intro
    audio ran 6s, the subtitle vanished at 3s and every later subtitle fired
    ~3s early. Caller passes the measured durations; we only fall back to
    probing when the caller didn't (legacy callers / no audio).
    """
    segments = script.get("segments", [])
    srt_path = os.path.join(work_dir, "subtitles.srt")
    lines = []
    sub_idx = 1

    intro_real = intro_dur_actual if intro_dur_actual is not None else intro_duration
    outro_real = outro_dur_actual if outro_dur_actual is not None else intro_duration
    current_time = intro_real

    intro_text = script.get("intro", "")
    if intro_text:
        sub_idx = _emit_cues(lines, sub_idx, intro_text, 0, intro_real)

    for seg in segments:
        idx = seg["index"]
        text = seg.get("narration", "")
        if not text.strip():
            continue
        # When the caller passed real per-segment durations (generate_video
        # does), an idx missing from seg_durations means that card was SKIPPED
        # in the video loop (missing image_file / file not on disk). The video
        # has NO clip for it, so emitting a subtitle + advancing the timeline
        # by 5.0s+ would desync every later subtitle (F2). Skip it + warn.
        if seg_durations is not None and idx not in seg_durations:
            print(f"  [WARN] segment index {idx} has narration but no video "
                  f"clip (card image missing?) — subtitle skipped to avoid "
                  f"SRT drift.", file=sys.stderr)
            continue
        if seg_durations and idx in seg_durations:
            dur = seg_durations[idx]
        else:
            audio_path = audio_map.get(idx)
            if audio_path and os.path.exists(audio_path):
                dur = get_audio_duration(audio_path) + 0.5
            else:
                dur = 5.0
        start = current_time
        end = current_time + dur
        sub_idx = _emit_cues(lines, sub_idx, text, start, end)
        current_time = end + gap_duration

    outro_text = script.get("outro", "")
    if outro_text:
        sub_idx = _emit_cues(lines, sub_idx, outro_text,
                             current_time, current_time + outro_real)

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
# Resolution parsing
# ---------------------------------------------------------------------------
def _parse_resolution(resolution: str):
    """Parse a WxH string into (width, height) ints, with a clear error."""
    try:
        parts = resolution.lower().split("x")
        if len(parts) != 2:
            raise ValueError
        w, h = int(parts[0].strip()), int(parts[1].strip())
        if w <= 0 or h <= 0:
            raise ValueError
        return w, h
    except ValueError:
        raise SystemExit(
            f"Invalid --resolution {resolution!r}; use WxH, e.g. 1920x1080 "
            f"(landscape) or 1080x1920 (vertical)."
        )


# ---------------------------------------------------------------------------
# Main video generation
# ---------------------------------------------------------------------------
def generate_video(work_dir: str, output_path: str, resolution: str = "1920x1080",
                   intro_duration: float = 3.0, gap_duration: float = 0.8,
                   fps: int = 24, scroll_threshold: float = 0.25):
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

    target_w, target_h = _parse_resolution(resolution)

    with open(os.path.join(work_dir, "manifest.json"), "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(os.path.join(work_dir, "narration_script.json"), "r", encoding="utf-8") as f:
        script = json.load(f)

    audio_map = {}
    intro_audio = None
    outro_audio = None
    audio_manifest_path = os.path.join(work_dir, "audio_manifest.json")
    if os.path.exists(audio_manifest_path):
        with open(audio_manifest_path, "r", encoding="utf-8") as f:
            am = json.load(f)
        for seg in am.get("segments", []):
            if seg.get("audio_file"):
                audio_map[seg["index"]] = os.path.join(work_dir, "audio", seg["audio_file"])
        if am.get("intro_audio"):
            intro_audio = os.path.join(work_dir, "audio", am["intro_audio"])
        if am.get("outro_audio"):
            outro_audio = os.path.join(work_dir, "audio", am["outro_audio"])

    # Audio diagnostic summary — surface silent intro/outro at compose time so
    # "no voiceover" is visible in the log, not buried. (The intro/outro TTS
    # bug manifested as a silent title frame with no obvious cause.)
    intro_present = bool(intro_audio and os.path.exists(intro_audio))
    outro_present = bool(outro_audio and os.path.exists(outro_audio))
    if not intro_present:
        print("  [WARN] intro audio MISSING — intro will be a SILENT title frame. "
              "Did tts_narration.py run with a non-empty `intro` in narration_script.json?",
              file=sys.stderr)
    if not outro_present:
        print("  [WARN] outro audio MISSING — outro will be a SILENT frame. "
              "Did tts_narration.py run with a non-empty `outro` in narration_script.json?",
              file=sys.stderr)
    print(f"Audio: intro={'attached' if intro_present else 'MISSING'} "
          f"| outro={'attached' if outro_present else 'MISSING'}")

    board_path = resolve_board_path(work_dir, manifest)
    board = Image.open(board_path).convert("RGB")

    board, scrollable = fit_board(board, target_w, target_h, scroll_threshold)
    board_w, board_h = board.size
    max_scroll = max(0, board_h - target_h)
    print(f"Board: {board_w}x{board_h}, "
          + (f"scroll {max_scroll}px" if scrollable else "contain (no scroll)"))

    title = manifest.get("title", "Tier List")
    seg_lookup = {s["index"]: s for s in script.get("segments", [])}
    scripted_indices = {s["index"] for s in script.get("segments", []) if s.get("index", -1) >= 0}

    clips_info = []
    skipped = []
    img_dir = os.path.join(work_dir, "images")

    for tier in manifest.get("tiers", []):
        for card in tier.get("cards", []):
            idx = card["index"]
            if scripted_indices and idx not in scripted_indices:
                continue
            img_file = card.get("image_file")
            card_path = os.path.join(img_dir, img_file) if img_file else ""
            if not img_file or not os.path.exists(card_path):
                # Never skip silently. A board whose cards all lack images used to
                # sail through here and produce an intro + outro and nothing in
                # between, exit code 0 — a two-frame "video" that looks finished.
                skipped.append((idx, str(card.get("image_url", ""))[:48]))
                continue
            audio_path = audio_map.get(idx)
            # NOTE: do NOT probe audio duration here. The clip's real duration
            # is loaded via AudioFileClip in the second loop (real_dur, used for
            # both the clip and seg_durations). Probing here too would open
            # every MP3 twice (C3) and feed a guessed 5.0s-fallback duration
            # into the "Compositing N clips (Xs total)" log (C4). The clips_info
            # tuple carries (tier, card, audio_path) — no dur.
            clips_info.append((tier, card, audio_path))

    if skipped:
        print(f"  [WARN] {len(skipped)} card(s) have no image on disk and were "
              f"skipped: {skipped[:5]}{' ...' if len(skipped) > 5 else ''}",
              file=sys.stderr)
    print(f"Cards: {len(clips_info)} with images"
          + (f", {len(skipped)} skipped" if skipped else ""))
    if not clips_info:
        raise SystemExit(
            "No card has a usable image — the video would be nothing but an intro "
            "and an outro.\n"
            "If this board uses TEXT cards (image_url starts with 'text:'), re-run "
            "fetch_tierlist.py: it renders those locally. If they are image cards, "
            "the downloads failed — check the network and images/."
        )

    clips = []

    # Intro: show the board TOP as-is — the branded title bar (title, up to 2
    # lines, + logo) is already baked into board_hd.png by capture_board. No
    # overlaid centered title, no darkening: the viewer opens on the full board
    # carrying its own title. (user feedback)
    intro_img = crop_board_at(board, 0, target_w, target_h)
    intro_dur = intro_duration
    intro_audio_clip = None
    if intro_audio and os.path.exists(intro_audio):
        try:
            intro_audio_clip = AudioFileClip(intro_audio)
            intro_dur = max(0.1, intro_audio_clip.duration) + 0.3
        except Exception as e:
            print(f"  [WARN] intro audio load failed: {e}", file=sys.stderr)
    _intro_clip = ImageClip(np.array(intro_img), duration=intro_dur)
    if intro_audio_clip is not None:
        _intro_clip = _intro_clip.with_audio(intro_audio_clip)
    clips.append(_intro_clip)

    elapsed = intro_duration
    n_cards = len(clips_info)
    # Collect each segment's real (audio-true) duration so generate_srt can use
    # the SAME durations the clips actually play at — subtitle timing must
    # follow audio, not a re-probe that can fall back to a 5.0s guess.
    seg_durations = {}
    for k, (tier, card, audio_path) in enumerate(clips_info):
        idx = card["index"]
        seg = seg_lookup.get(idx, {})
        card_label = seg.get("label", card.get("label", ""))
        tier_name = tier["name"]
        tier_color = tier["color"]

        # Scroll by CARD INDEX (k of n), not by elapsed time — so the background
        # reaches the k-th card's area as that card is narrated, instead of
        # stalling when one card's audio runs long (the old time-proportional
        # scroll desynced from the narration).
        if n_cards > 1:
            scroll_progress = k / (n_cards - 1)
            gap_progress = (k + 0.5) / (n_cards - 1)
        else:
            scroll_progress = gap_progress = 0.0
        scroll_y = int(scroll_progress * max_scroll)

        # Full-vivid board, NO blur/darken: the colorful board IS the attraction
        # while a card is narrated - blurring it left a dead mid-frame with no pull
        # (user feedback). The card's own dark backing in create_card_overlay keeps
        # it readable against the bright background.
        bg_frame = crop_board_at(board, scroll_y, target_w, target_h)

        card_path = os.path.join(img_dir, card["image_file"])
        card_img = Image.open(card_path).convert("RGBA")
        frame = create_card_overlay(bg_frame, card_img, tier_name, tier_color,
                                     card_label, target_w, target_h)

        # Audio-true duration: load the ACTUAL audio clip and use its real
        # length (+0.5s tail) so the frame matches the spoken audio exactly.
        # This kills the 5.0s-fallback desync (get_audio_duration could guess
        # wrong while the real audio played a different length). Keep the clip
        # object to attach it.
        audio_clip = None
        real_dur = 5.0
        if audio_path and os.path.exists(audio_path):
            try:
                audio_clip = AudioFileClip(audio_path)
                real_dur = max(0.1, audio_clip.duration) + 0.5
            except Exception as e:
                print(f"  [WARN] audio load failed for card {idx}: {e}; frame=5.0s", file=sys.stderr)
        seg_durations[idx] = real_dur
        clip = ImageClip(np.array(frame), duration=real_dur)
        if audio_clip is not None:
            clip = clip.with_audio(audio_clip)
        clips.append(clip)

        gap_scroll = int(gap_progress * max_scroll)
        # Same full-vivid board as the card frame (no blur/darken) so the gap
        # doesn't flicker bright<->dim between cards.
        gap_bg = crop_board_at(board, gap_scroll, target_w, target_h)
        clips.append(ImageClip(np.array(gap_bg), duration=gap_duration))

        elapsed += real_dur + gap_duration

    # Outro: NO title frame (don't repeat the title). Full-vivid board scrolled
    # to the end (no blur/darken, matching intro + card frames) + outro audio.
    outro_frame = crop_board_at(board, max_scroll, target_w, target_h)
    outro_dur = intro_duration
    outro_audio_clip = None
    if outro_audio and os.path.exists(outro_audio):
        try:
            outro_audio_clip = AudioFileClip(outro_audio)
            outro_dur = max(0.1, outro_audio_clip.duration) + 0.3
        except Exception as e:
            print(f"  [WARN] outro audio load failed: {e}", file=sys.stderr)
    _outro_clip = ImageClip(np.array(outro_frame), duration=outro_dur)
    if outro_audio_clip is not None:
        _outro_clip = _outro_clip.with_audio(outro_audio_clip)
    clips.append(_outro_clip)

    # Total content duration from the REAL durations actually used (intro_dur,
    # outro_dur, each card's real_dur + gap), not the old get_audio_duration
    # guesses that could fall back to 5.0s and mislead the log (C4).
    total_content_dur = (intro_dur + outro_dur
                        + sum(seg_durations.values())
                        + gap_duration * len(clips_info))

    generate_srt(script, audio_map, work_dir, intro_duration, gap_duration,
                 intro_dur_actual=intro_dur,
                 outro_dur_actual=outro_dur,
                 seg_durations=seg_durations)

    print(f"Compositing {len(clips)} clips ({total_content_dur:.1f}s total)...")
    final = concatenate_videoclips(clips, method="compose")

    print(f"Writing video to {output_path} at {fps}fps...")
    final.write_videofile(
        output_path,
        fps=fps,
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
    parser.add_argument(
        "--fps", type=int, default=24,
        help="Frame rate (default 24). Every clip is a still image, so 23 of "
             "every 24 frames are byte-identical re-renders — dropping to 12 "
             "roughly halves render time with no visible difference.")
    parser.add_argument(
        "--scroll-threshold", type=float, default=0.25,
        help="How much taller than the frame the board must be (as a fraction) "
             "before scrolling it instead of fitting it whole. Default 0.25.")
    args = parser.parse_args()
    output = args.output or os.path.join(args.work_dir, "tierlist_video.mp4")
    generate_video(args.work_dir, output, args.resolution, args.intro_duration,
                   fps=args.fps, scroll_threshold=args.scroll_threshold)
