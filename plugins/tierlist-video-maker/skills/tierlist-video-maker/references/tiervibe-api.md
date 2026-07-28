# TierVibe API Reference (canonical for this skill)

The TierVibe tier list is fetched from the public read API. **Read this before
writing any fetch logic** — most failures in the previous version came from
misunderstanding where the board image comes from.

## 1. Fetch the tier list

```
GET https://tiervibe.com/api/posts/{slugOrNumericId}
```

- `{slugOrNumericId}` accepts **either** the public slug **or** the numeric post id.
  The server resolves: all-digits → numeric id, otherwise → public slug
  (`findByPublicId`). The skill always works with the **slug** (the URL segment
  in `https://tiervibe.com/t/<slug>`).
- No auth required for published posts. Drafts are not publicly readable.

### Response fields

| Field | Type | Description |
|---|---|---|
| `postId` | int | Internal numeric post id |
| `publicId` | string | Public slug (e.g. `mGw0NA5Gy0`) — use this |
| `title` | string | Tier list title |
| `tierCount` | int | Number of active tiers (1-15) |
| `bgBrightness` | int | Board background brightness 0-100 (0=near-black, 100=white) |
| `fullImageUrl` | string\|null | Intended full board (1600px) — **null on every published post in practice**; do not rely on it. Use `capture_board.py` for high-res (§2.1) |
| `thumbUrl` | string | Board image, 600px wide (always present for published posts) — server fallback |
| `blurhash` | string | BlurHash placeholder |
| `status` | string | `published` or `draft` |
| `T{n}name` | string | Tier n label (n = 1..15) |
| `T{n}color` | string | Tier n title-bar hex color |
| `T{n}images` | array | Cards in tier n: `[{id, imageUrl, detail}]` (see §3) |
| `T{n}size` | string | Tier n font size |
| `C{n}images` | array | Candidate-pool cards (n = 1..3) |
| `cardDetails` | array | All card details: `[{id, content}]` - duplicates each card's `detail`; cross-check source |

## 2. The board image — THIS is your video background

The video's scrolling background is **the full tier-list board image**. The server
already renders and stores it at publish time — **you fetch a URL, you do not
re-render it, and you do NOT click any browser button.**

### Source priority (use the first that exists)

| Priority | Source | Size | How |
|---|---|---|---|
| 1 (high-res) | **Playwright capture** (`capture_board.py`) | ~2560px wide | script opens the public page and runs `html-to-image` on the tier-grid DOM — see §2.1 |
| 2 (server) | `thumbUrl` | 600px wide × full board height | download directly |
| 3 (JPEG fallback) | `GET https://tiervibe.com/og/{slug}.jpg` | ~600px wide | server converts the webp cover to jpg on the fly |

#### 2.1 The high-res path — Playwright capture (preferred for video)

The server does NOT store a high-resolution board image. The `fullImageUrl` field
exists in the schema but is **null on every published post** (verified on real
posts — the publish flow only writes the 600px `thumbUrl`, despite a 1600px
backfill script existing). So for a sharp 1080p video background you CANNOT fetch
a URL — you reproduce the user-side "download whole image" action in a script:

`capture_board.py` runs a headless Chromium, opens the **public** read page
`https://tiervibe.com/t/{slug}` (no login — published posts are public), locates
the node `[data-testid="tier-grid"]`, and calls `html-to-image.toPng(node,
{pixelRatio:2})` — the **same library the in-page download button uses**, just
automated. The export stays a client-side action (no TierVibe server call); the
script is doing what a human clicking the button would do. Output: `board_hd.png`.

> Requires: the TierVibe deploy has shipped the `data-testid="tier-grid"`
> attribute on the read page. If `capture_board.py` says "tier-grid not found",
> that attribute is not live yet — fall back to `thumbUrl`/og and report it.

#### 2.2 The server (low-res) path — `thumbUrl` / og

`thumbUrl` is the 600px-wide webp cover (`fullImage/<date>/<hash>_thumb.webp`),
always present for published posts. It is a real, complete board image (tier
labels, layout, brightness baked in) — just narrow. Good as a fallback when the
Playwright capture is unavailable. `fullImageUrl` (the intended 1600px field) is
null in practice; do not rely on it.

### ❌ The "download whole image" button is NOT an API

The TierVibe post page (`ViewTierList`) has a "download whole image" button. It
runs `SaveImage.saveImage(leftAreaRef, ...)` — a **browser-only DOM→canvas→PNG
export** (`html-to-image`, client-side, in the user's logged-in browser). It is:

- **not a network endpoint** — there is no URL to call,
- **not reachable from a script** — it needs a live browser DOM,
- **unnecessary** — the server already stores the same board image at
  `fullImageUrl`/`thumbUrl`.

A previous version of this skill tried to replicate or trigger that button and
stalled. **Do not.** Just `GET` the image URL from the priority chain above.

## 3. Card images

```json
{
  "id": "8962089c-...",
  "imageUrl": "https://cdn.tiervibe.com/cardimage/2026/07/23/occ2ab5pfbk.webp",
  "detail": "## T1\nAuthor's markdown explanation for this card (optional, may be empty)"
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Card uuid |
| `imageUrl` | string | Card image URL (or `text:<urlencoded label>#<fg>#<bg>` for text cards) |
| `detail` | string\|null | Author's markdown explanation for this card, **optional** - used as narration reference. Empty/null on cards the author didn't annotate. Mirrored in top-level `cardDetails[].content`. |

- Card images live on `cdn.tiervibe.com`. Downloading them server-side with a
  normal HTTP client works (CORS is a browser-only restriction; a Python
  `requests`/`urllib` fetch is unaffected).
- **The API does NOT return card text labels.** Card names are baked into the card images. The primary way to identify a card is AI vision on the downloaded image file. `detail` is the author's written explanation (reference for narration), NOT the stored card name - don't confuse the two. BUT when vision is unavailable, you can usually DERIVE a short card name from the `detail` (e.g. its first markdown heading, or the subject of the first sentence) and use it as a fallback label (`label_source: "derived_from_detail"`); it's a derived guess, not the canonical name.

## 4. URL formats

| Page | URL |
|---|---|
| Tier list page | `https://tiervibe.com/t/{slug}` |
| Board image (JPEG) | `https://tiervibe.com/og/{slug}.jpg` |
| API | `https://tiervibe.com/api/posts/{slug}` |

The slug is a base62 string (typically ~10 chars). Extract it from a `tiervibe.com/t/<slug>`
URL, or accept it bare.
