# TierList Video Maker

A Claude Code / Codex skill that turns any **published** [TierVibe](https://tiervibe.com) tier list into a narrated video.

## What it does

- **Fetch** the tier list data + card images from the TierVibe public read API
- **Capture a high-resolution board** from the public post page (Playwright runs the same `html-to-image` export the in-page "download whole image" button uses — automated, no TierVibe server call)
- **AI vision** identifies each card (the API returns no text labels)
- **Narration script** — generated, then user-reviewable before production
- **TTS** via edge-tts (multi-language, cross-platform)
- **Video** — scrolling tier-list background + per-card zoom overlay + subtitles (SRT)

## Why the board image comes from a browser capture

The TierVibe server only stores a 600px thumbnail of the board, not a
high-resolution one. For a sharp 1080p background, this skill reproduces the
user-side "download whole image" action in a script: a headless Chromium opens
the **public** read page and runs `html-to-image` on the tier-grid DOM. The export
stays a client-side action — **no TierVibe server call is made for the board
image** — the script is just doing what a human clicking the download button
would do.

> Requires the TierVibe deploy to have shipped the `data-testid="tier-grid"`
> attribute on the read page. If the capture step reports "tier-grid not found",
> the skill falls back to the 600px server thumbnail.

## Quick start

1. Install as a skill (copy to `~/.claude/skills/` or `~/.codex/skills/tierlist-video-maker/`).
2. Say: *"帮我把这个 TierVibe 做成视频: https://tiervibe.com/t/xxxxx"*
3. Review the generated narration script
4. Get your video + `.srt`

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fetch_tierlist.py` | Fetch tier list data + download card images + server thumb |
| `scripts/capture_board.py` | Capture a high-res board image from the public page (Playwright) |
| `scripts/render_board.py` | Fallback: rebuild an approximate board from card images |
| `scripts/tts_narration.py` | Generate TTS audio from the narration script |
| `scripts/generate_video.py` | Compose video with scrolling background + subtitles |

## Dependencies

- Python 3.10+
- `Pillow`, `requests`
- `edge-tts` (auto-installed)
- `moviepy>=2.0` + `numpy` (auto-installed; bundles ffmpeg)
- `playwright` + Chromium (auto-installed on first `capture_board.py` run; ~150MB browser)

## Cross-platform

- Windows: Microsoft YaHei (msyh.ttc)
- macOS: PingFang SC
- Linux: Noto Sans CJK

## License

MIT
