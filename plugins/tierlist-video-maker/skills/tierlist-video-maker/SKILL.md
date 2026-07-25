---
name: tierlist-video-maker
description: >
  Turn a published TierVibe tier list into a narrated video. Fetches tier list data and card images
  from a TierVibe URL, captures a HIGH-RESOLUTION board image from the public page (Playwright, no
  server call — the whole-image export is a user-side action, automated), uses AI vision to identify
  each card, generates a narration script (user-reviewable), produces TTS audio with subtitles, and
  composes a video with a scrolling tier-list background where each card is shown enlarged while
  narrated. Use when the user wants to make/create a video from a TierVibe tier list, turn a tier list
  into a video, or narrate/explain a tier list ranking. Triggers: "tier list video", "tiervibe video",
  "tier list 做成视频", "排行榜视频", "tier list 讲解视频".
---

# TierList Video Maker

Turn any published TierVibe tier list into a narrated video with a scrolling
high-resolution background.

## ⚠️ Only published posts — drafts / still-editing posts cannot be used

This skill works on **published** TierVibe posts only. The video needs a board
image and card images, which exist only once a post is published — a draft / a
post you're still editing in the editor is **not publicly readable** and has no
board image, so the scripts cannot fetch it.

If the user gives you a post that isn't published yet: **stop and tell them** —
"先把它在 TierVibe 上发布,再用这个技能做成视频" / "publish it on TierVibe
first, then make the video." Do not try to make a video from an editor URL or a
draft. `fetch_tierlist.py` checks the `status` field and will fail fast with this
same message if the post isn't published.

## ⚠️ Multimodal (image recognition) is required — be honest if you can't

This skill needs **AI vision**: the TierVibe API returns no card text labels —
card names are baked into the card images, so you (the model running this
skill) must look at each card image and identify what it depicts before you
can write any narration.

**If you do NOT support image recognition** (you can't view/identify images),
**stop at Step 4 and tell the user plainly** — do NOT fabricate card names or
hallucinate narration. Say, in the user's language:

> "I can't make this video — I can't recognize the card images. Use a
> multimodal model that supports image recognition (e.g. GPT-4o, Claude with
> vision, Gemini), or tell me what each card is and I'll take it from there."

Image recognition is the model's own capability, not something this skill can
work around — same principle as image search in the TierList-Maker skill. Be
honest; do not pretend.

## How the board image is obtained (read this first)

The TierVibe server only stores a 600px thumbnail of the board, not a
high-resolution one. For a sharp 1080p background, this skill reproduces the
user-side "download whole image" action in a script: a headless Chromium opens
the **public** read page and runs the same `html-to-image` library the in-page
button uses. **No TierVibe server call is made for the board image** — the export
is a client-side action, just automated. See `references/tiervibe-api.md`.

## Workflow (follow in order)

### Step 1 — Capture the high-resolution board (visual source of truth)

```bash
python <skill_dir>/scripts/capture_board.py "<URL_OR_SLUG>" -o <work_dir> --pixel-ratio 2
```

Runs headless Chromium on the public `https://tiervibe.com/t/<slug>` page,
captures `[data-testid="tier-grid"]` to `board_hd.png` (~2560px wide). **This
is captured FIRST because it is the visual source of truth** for tier
assignment and card order — recognizing cards against this single image (with
tier labels and neighbors as context) is far more accurate than recognizing
each card image in isolation (user-reported bug: isolated recognition
misidentifies cards).

> If this fails ("tier-grid not found"), the TierVibe deploy has not shipped the
> `data-testid` attribute yet. Fall back to the 600px thumb from Step 2 — the
> video still works, the background is just softer — and note it to the user.
> Board-first recognition (Step 4) then falls back to per-card-only.

### Step 2 — Fetch tier list data + card images

```bash
python <skill_dir>/scripts/fetch_tierlist.py "<URL_OR_SLUG>" -o <work_dir>
```

Downloads all card images + the 600px server thumb (fallback background), writes
`manifest.json`. Verify: `total_cards > 0` and `images/` is populated.

### Step 3 — (Optional) Render a fallback board

Only if Step 1 failed AND you want a non-blurry background without Playwright:

```bash
python <skill_dir>/scripts/render_board.py <work_dir> --width 1920
```

Builds an APPROXIMATE board (tier labels + card grid) from card images. It will
not match TierVibe's exact layout, so prefer Step 1.

### Step 4 — Board-first recognition (produce board_layout.json)

View `board_hd.png` (the whole board at once). In ONE pass, identify every
card **in context** — tier labels are the row headers, neighbors give context
that an isolated card image lacks. Output the visual layout to
`<work_dir>/board_layout.json`:

```json
{
  "board_title": "编程语言天梯榜 · 2026",
  "tiers": [
    { "tier": "T1", "cards": [{"position": 1, "label": "PHP"}, {"position": 2, "label": "C++"}] },
    { "tier": "T2", "cards": [{"position": 1, "label": "C"}, {"position": 2, "label": "Rust"}] }
  ]
}
```

Rules:
- **Visual reading order**: top tier → bottom tier, within each tier left → right.
- `tier` = the tier label as shown on the board (e.g. "T1", or a custom name
  like "S"/"夯"). `position` = 1-based left-to-right index within that tier.
- `label` = what the card depicts. If you genuinely cannot read a card on the
  board (small/blurry), leave its `label` empty — Step 5's per-card pass
  (higher-res individual image) will fill it.
- This whole-board pass is the primary recognition. It is more accurate than
  per-card because the board carries tier + neighbor context.

If `board_hd.png` is missing (Step 1 failed): skip this step, leave
`board_layout.json` unwritten. Step 5's per-card recognition becomes the only
source; reconcile_cards.py will keep the API order.

### Step 5 — Per-card confirmation + reconcile

1. Read `manifest.json` for card image files in `images/`.
2. View each `card_XXX.webp` (higher-res than the board thumbnail) and confirm
   the label. Write it back into each card's `label` field in `manifest.json`.
   This **confirms** the board recognition; if it disagrees, that's fine — the
   board wins (Step 4 is the truth), but the disagreement is flagged for review.
3. Reconcile the two:

```bash
python <skill_dir>/scripts/reconcile_cards.py <work_dir>
```

Reads `board_layout.json` (board truth: tier + order) + `manifest.json`
(per-card labels), matches each board slot to its card image by label, and
rewrites `manifest.json` so `tiers` are in **board visual order** with each
card tagged `board_tier` / `board_position` / `matched` / `label_disagreement`.
Card `index` (the `card_XXX` file number) is preserved, so narration indices and
the video overlay still map to the right image files. A `manifest.pre_reconcile.json`
backup is written. If matching drops below 50% (board and API structures diverge
too far), it keeps the API order and warns — review manually instead of
trusting a half-matched reorder.

If a card cannot be recognized on either the board or its individual image, ask
the user for that one card rather than guessing — a wrong label misleads the
entire narration.

### Step 6 — Generate narration script

Create `<work_dir>/narration_script.json`:

```json
{
  "title": "中国动画电影龙虎榜",
  "language": "zh",
  "intro": "大家好，今天来看看中国动画电影的排名...",
  "segments": [
    { "index": 0, "tier": "夯", "label": "哪吒之魔童降世",
      "narration": "第一名，哪吒之魔童降世。这部电影..." }
  ],
  "outro": "以上就是今天的排名，你觉得合理吗？"
}
```

Rules:
- Match the language of the tier list title (Chinese title → Chinese narration).
- Each segment: 1-3 sentences, concise and engaging.
- Group by tier: introduce each tier before its cards.
- `index` must match the card index in `manifest.json` (unchanged by reconcile).
- **`intro` and `outro` are REQUIRED and must be non-empty.** If either is
  empty, the video's opening/closing title frame will be SILENT (no voiceover)
  — the TTS step skips empty text silently and the compose step has no audio
  to attach. Always write a 1-2 sentence intro and outro.

### Step 6½ — Generate the card manifest table (file ↔ name ↔ tier ↔ narration)

After the narration is written, generate a human-readable mapping so you and
the user can verify every image file maps to the right card name, tier, board
position, and narration — no "which `card_003.png` was that?" confusion:

```bash
python <skill_dir>/scripts/build_card_manifest.py <work_dir>
```

Reads `manifest.json` (file + tier + board_position + board vs card label) +
`narration_script.json` (label + narration), writes `card_manifest.md` — one
row per card:

| index | image file | tier | board_pos | card name | narration (preview) |
|---|---|---|---|---|---|
| 0 | card_000.webp | 夯 | 1 | 哪吒之魔童降世 | 第一名,哪吒之魔童降世。这部电影... |

Rows where the board recognition and per-card recognition disagreed are shown
as `⚠ board=<x> | card=<y>` so you can resolve them. Show this table to the
user in Step 7 review — it's the single source of truth for "which file is
which card". If a row is wrong, fix it in `manifest.json` (label) or
`narration_script.json` (narration) and re-run this script.

### Step 7 — User review

Present the narration script in readable form; ask the user to confirm or
modify. Revise until approved. Write the final version to `narration_script.json`.

### Step 8 — Generate TTS audio

```bash
python <skill_dir>/scripts/tts_narration.py generate <work_dir>/narration_script.json -o <work_dir> [-v VOICE]
```

Voice by language:
- Chinese: `zh-CN-YunxiNeural` (male, default) / `zh-CN-XiaoxiaoNeural` (female)
- English: `en-US-GuyNeural` / `en-US-JennyNeural`
- Japanese: `ja-JP-NanamiNeural` / `ja-JP-KeitaNeural`
- List all: `python <skill_dir>/scripts/tts_narration.py voices -l <lang_prefix>`

Generates `narration_<NNN>.mp3` per segment PLUS `narration_intro.mp3` /
`narration_outro.mp3` from the (required, non-empty) intro/outro text. If
intro/outro are empty it warns loudly — fix `narration_script.json` and re-run.

### Step 9 — Compose video

```bash
python <skill_dir>/scripts/generate_video.py <work_dir> -o <output.mp4> [--resolution 1920x1080]
```

Options:
- `--resolution 1920x1080` (landscape) or `1080x1920` (vertical/shorts)
- `--intro-duration 3.0` seconds for intro/outro (only used when no intro/outro
  audio is attached; with audio, the frame follows the audio's real length)

Features:
- Background priority: `board_hd.png` (Step 1) → server thumb (Step 2) →
  `board.png` (Step 3).
- Card order follows the reconciled `manifest.json` (board visual order).
- Scrolling background: if the board is taller than the frame, scrolls top→bottom.
- Card overlay: each card zoomed to center with a tier badge + label.
- Subtitles: auto-generates `subtitles.srt` alongside the video, timed to the
  ACTUAL audio durations (intro/outro/segments) — not a fixed 3.0s guess.
- Prints an audio summary at start (`intro: attached | outro: attached | cards:
  N/N with audio`); if intro/outro audio is missing it warns — that's the
  "silent title frame" failure mode, catch it here.
- Cross-platform: Windows / macOS / Linux.

### Step 10 — Deliver

Provide the output video + subtitles file to the user.

## Dependencies

- Python 3.10+
- `Pillow` (usually pre-installed)
- `edge-tts` (auto-installed; Microsoft online TTS, cross-platform)
- `moviepy>=2.0` + `numpy` (auto-installed; moviepy bundles ffmpeg)
- `playwright` + Chromium (for the high-res board capture; auto-installed on
  first run of `capture_board.py`; first install downloads ~150MB browser)

Cross-platform font detection in the render/compose scripts:
- Windows: Microsoft YaHei (msyh.ttc)
- macOS: PingFang SC
- Linux: Noto Sans CJK

## Multi-language

1. Set `"language"` in `narration_script.json`.
2. Choose a matching TTS voice.
3. Subtitles are generated in the narration language.
4. Card labels and tier names are preserved as-is.

## Troubleshooting

- **No card images**: the URL must be a published (not draft) post.
- **`capture_board.py` says "tier-grid not found"**: the TierVibe deploy hasn't
  shipped the `data-testid="tier-grid"` attribute yet. Use the 600px thumb
  fallback (Step 2) and report it. Board-first recognition (Step 4) then has
  no board to read — fall back to per-card-only (Step 5).
- **TTS fails**: needs network; edge-tts uses Microsoft's online service.
- **Video encoding fails**: moviepy bundles ffmpeg; if issues, install ffmpeg.
- **Font missing**: scripts fall back to a default font; install Noto Sans CJK on Linux.
- **Card unclear**: ask the user to help identify specific cards.
- **Model can't recognize images**: if you (the running model) have no image
  recognition, do NOT fabricate card names — stop and tell the user to switch
  to a multimodal model, or have them name each card. See the "Multimodal is
  required" section above.
