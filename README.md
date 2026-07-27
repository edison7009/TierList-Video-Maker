# TierList Video Maker

> A "money-printer" video-generation skill — one command turns any TierVibe tier list into a narrated video, with every step engineered tighter than the generic generators.

> 中文（简）见 [README.zh-CN.md](README.zh-CN.md). 繁中見 [README.zh-Hant.md](README.zh-Hant.md).

## Quick demo

**1. Make the tier list.** With **TierList-Maker** installed in your AI tool, enter:

```
/tierlist-maker Make a tier list of America's most popular sports, with detailed commentary.
```

Result: https://tiervibe.com/t/UxDgrOcQxd （中文版：https://tiervibe.com/t/ZY70IpV0K8）

---

**2. Make the video.** With **TierList-Video-Maker** installed in your AI tool, enter:

```
/tierlist-video-maker Turn https://tiervibe.com/t/UxDgrOcQxd into a video
```

（中文版：`/tierlist-video-maker 把 https://tiervibe.com/t/ZY70IpV0K8 制作成视频`）

Video showcase: https://youtu.be/ANjyhxRrH9U （中文版：https://www.bilibili.com/video/BV1LG3F6sEAB）

## Why TierList videos are worth making

TierList videos carry **depth and a point of view** — who's S-tier, who's trashed, who got snubbed — which is inherently controversial and shareable. On nearly every video platform this format **routinely pops off**, earning plays, followers, and a real path to monetization.

## Why this beats other AI video generators

There are already video generators out there, but the output is usually **mediocre**: the thumbnail gets blown up blurry, cards land in the wrong tier, the intro/outro are silent, subtitles drift from the voice, and a static board plays start-to-finish with no rhythm. This skill does each step properly:

- **Board-first AI vision** — the AI reads the **whole board first** (with tier labels + neighbor cards as context) to identify every card, then cross-checks each high-res card image against it. The board is the source of truth for tier and order — not isolated single-logo guessing, so cards are identified correctly and never misplaced.
- **True high-res board background** — Playwright captures the public page's `[data-testid="tier-grid"]` at ~2560px wide, not a 600px thumbnail stretched blurry.
- **AI-written narration, reviewed before production** — not a rigid template read aloud; revise freely, render only after you approve.
- **Multi-language natural-voice TTS** — zh / en / ja / ko via edge-tts, cross-platform, with **spoken intro and outro** (no silent title frames).
- **Subtitles timed to the real audio** — the SRT is generated from each segment's measured audio duration, not a fixed 3-second guess, so subtitles stay in sync.
- **Card zoom overlay + scrolling tier-list background** — the narrated card centers and zooms while the background scrolls to its row, giving the video rhythm instead of a static board from head to tail.
- **Pairs with `TierList-Maker`** — make a deep, content-rich tier list first, then turn it into a video. Quality starts at the source.

## Two steps, that simple

1. Make a deep, content-rich tier list with **[TierList-Maker](https://github.com/edison7009/TierList-Maker)** and publish it on [tiervibe.com](https://tiervibe.com).
2. Paste the published post's link (`https://tiervibe.com/t/xxxxx`) to this skill — it turns the list into a narrated video, fully automated.

> **Only published posts.** This skill makes a video from a **published** TierVibe post. A draft / a post you're still editing has no board image and is not publicly readable, so it can't be turned into a video — publish it on TierVibe first.

## About

- **Fetch** the tier list data + card images from the TierVibe public read API.
- **Capture a high-resolution board** from the public post page (Playwright runs the same `html-to-image` export the in-page "download whole image" button uses — automated, **no TierVibe server call**).
- **AI vision** identifies each card (board-first: whole board first, per-card cross-check second, board is truth).
- **Narration script** — generated, then user-reviewable before production.
- **TTS** via edge-tts (multi-language, cross-platform, with spoken intro/outro).
- **Video** — scrolling tier-list background + per-card zoom overlay + subtitles (SRT timed to real audio).
- **Works with the agents you already use** — Claude Code, ChatGPT, Codex, and any agentskills.io-compatible tool.

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

1. Install the skill (see below), then say: *"Make a video from this TierVibe tier list: https://tiervibe.com/t/xxxxx"*
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
/plugin install tierlist-video-maker@video-maker
```

Skill auto-loads on triggers like "make a video from this TierVibe tier list", or invoke as `/video-maker:tierlist-video-maker`.

## Install — ChatGPT

1. Open ChatGPT → **Plugins**.
2. Click the **⬇️** icon (top-right).
3. Choose **Add plugin marketplace**.
4. Paste the repo URL: `https://github.com/edison7009/TierList-Video-Maker.git`
5. Confirm; `tierlist-video-maker` appears in the plugin list — enable it.

Then say *"Make a video from this TierVibe tier list: https://tiervibe.com/t/xxxxx"* in chat to trigger it. The AI fetches the board + cards, captures the high-res board, drafts a narration script for your review, then renders the video.

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
| `scripts/reconcile_cards.py` | Board-first: cross-check whole-board recognition vs per-card, reorder by board truth |
| `scripts/tts_narration.py` | Generate TTS audio from the narration script (incl. intro/outro) |
| `scripts/build_card_manifest.py` | Build a human-readable card table (file ↔ name ↔ tier ↔ narration) |
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
