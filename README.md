# TierList Video Maker

A portable Agent Skills plugin that turns any **published** [TierVibe](https://tiervibe.com) tier list into a narrated video.

> 中文版见 [README.zh-CN.md](README.zh-CN.md).

## About

- **Fetch** the tier list data + card images from the TierVibe public read API.
- **Capture a high-resolution board** from the public post page (Playwright runs the same `html-to-image` export the in-page "download whole image" button uses — automated, **no TierVibe server call**).
- **AI vision** identifies each card (the API returns no text labels — names are baked into the card images).
- **Narration script** — generated, then user-reviewable before production.
- **TTS** via edge-tts (multi-language, cross-platform).
- **Video** — scrolling tier-list background + per-card zoom overlay + subtitles (SRT).
- **Works with the agents you already use** — Claude Code, ChatGPT, Codex, and any agentskills.io-compatible tool.

> **Only published posts.** This skill makes a video from a **published** TierVibe post. A draft / a post you're still editing has no board image and is not publicly readable, so it can't be turned into a video — publish it on TierVibe first.

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

1. Install the skill (see below), then say: *"帮我把这个 TierVibe 做成视频: https://tiervibe.com/t/xxxxx"*
2. Review the generated narration script
3. Get your video + `.srt`

## Repo layout (dual marketplace)

This repo ships **two** marketplace catalogs so the same plugin installs on both Claude Code and Codex/ChatGPT-style agent tools:

```
TierList-Video-Maker/
├── .claude-plugin/
│   └── marketplace.json            # Claude Code marketplace catalog
├── .agents/plugins/
│   └── marketplace.json            # Codex / ChatGPT-style marketplace catalog
├── plugins/
│   └── tierlist-video-maker/
│       ├── .claude-plugin/
│       │   └── plugin.json         # Claude Code plugin manifest
│       ├── .codex-plugin/
│       │   └── plugin.json         # Codex plugin manifest (with logo)
│       └── skills/
│           └── tierlist-video-maker/
│               ├── SKILL.md        # the skill (entry point)
│               ├── references/    # tiervibe-api (canonical API doc)
│               └── scripts/       # fetch / capture / render / tts / generate_video
└── README.md
```

## Install — Claude Code

Add this repo as a marketplace, then install the plugin:

```
/plugin marketplace add edison7009/TierList-Video-Maker
/plugin install tierlist-video-maker@tiervibe-com
```

Skill auto-loads on triggers like "make a video from this TierVibe tier list", or invoke as `/tiervibe-com:tierlist-video-maker`.

## Install — ChatGPT

1. Open ChatGPT → **Plugins**.
2. Click the **⬇️** icon (top-right).
3. Choose **Add plugin marketplace**.
4. Paste the repo URL: `https://github.com/edison7009/TierList-Video-Maker.git`
5. Confirm; `tierlist-video-maker` appears in the plugin list — enable it.

Then say *"帮我把这个 TierVibe 做成视频: https://tiervibe.com/t/xxxxx"* in chat to trigger it. The AI fetches the board + cards, captures the high-res board, drafts a narration script for your review, then renders the video.

## Install — Codex (CLI)

The repo ships `.agents/plugins/marketplace.json` (Codex schema). Add and enable:

```
codex plugin marketplace add edison7009/TierList-Video-Maker
```

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
- `Pillow`
- `edge-tts` (auto-installed)
- `moviepy>=2.0` + `numpy` (auto-installed; bundles ffmpeg)
- `playwright` + Chromium (auto-installed on first `capture_board.py` run; ~150MB browser)

## Cross-platform

- Windows: Microsoft YaHei (msyh.ttc)
- macOS: PingFang SC
- Linux: Noto Sans CJK

## Icons

The TierVibe logo ships at `plugins/tierlist-video-maker/assets/logo.svg` (reused from the TierList-Maker plugin — same brand), and the Codex `.codex-plugin/plugin.json` points `interface.logo` at it. For the marketplace list UI, set the GitHub/GitCode repo's social preview image to the same logo.

## License

MIT
