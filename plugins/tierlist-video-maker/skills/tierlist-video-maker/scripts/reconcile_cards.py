#!/usr/bin/env python3
"""Reconcile the AI's board-image recognition with the API card list.

WHY THIS EXISTS
---------------
The TierVibe API returns card images in storage order, which (verified on real
posts) matches the board's visual order. But recognizing each card image IN
ISOLATION is error-prone — a logo with no context is hard to name. The board
image (board_hd.png) shows every card IN CONTEXT: tier labels as row headers
and neighbors on both sides. So the AI recognizes the whole board FIRST
(board_layout.json), then this script reconciles that against the per-card
labels it filled into manifest.json.

The board is the visual source of truth for tier + order; per-card labels
(higher-res individual images) are a confirmation pass. On disagreement the
board wins (user directive: board-first), but the row is flagged so the user
can override in review.

Usage:
    python reconcile_cards.py <work_dir>

Reads:  <work_dir>/board_layout.json   (AI output from reading board_hd.png)
        <work_dir>/manifest.json       (from fetch_tierlist.py, per-card labels
                                         filled in by AI vision)
Writes: <work_dir>/manifest.json       (reconciled: tiers in board visual order,
                                         each card tagged with board_tier /
                                         board_position / matched /
                                         label_disagreement)
        <work_dir>/manifest.pre_reconcile.json  (backup of the pre-reconcile
                                         manifest)
"""

import argparse
import json
import os
import re
import shutil
import sys
from difflib import SequenceMatcher

if sys.platform == "win32":
    # The Windows console defaults to the ANSI code page (GBK on zh-CN), which
    # turns every CJK title, label and path in the log into unreadable bytes.
    # This skill explicitly supports CJK boards, so readable logs are required.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _label_wins_over_board(man_card: dict) -> bool:
    """True when the manifest's label beats the board's on disagreement.

    Board-first is right for IMAGE cards: the board shows every card in context,
    so reading it beats naming an isolated thumbnail. It is backwards for TEXT
    cards. There the label isn't recognized at all — TierVibe encodes it in the
    card's own data (`text:<urlencoded label>#<fg>#<bg>`) and fetch_tierlist.py
    reads it out verbatim. Letting a vision misread of the board overwrite an
    exact string from the data would be a pure downgrade.

    Tier and position still come from the board in both cases — this is only
    about which spelling of the label survives.
    """
    return (man_card.get("label_source") == "text_card_data"
            and bool((man_card.get("label") or "").strip()))


def _norm(label: str) -> str:
    """Normalize a label for comparison: lowercase, strip, drop punctuation/ws."""
    s = (label or "").lower().strip()
    s = re.sub(r"[\s\-_/.,:;!?'\"()]+", "", s)
    return s


def _fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _assert_detail_preserved(manifest: dict, new_manifest: dict, path: str) -> None:
    """Warn if reconcile dropped any author `detail` text.

    The rebuild copies `detail` through explicitly; this catches a future
    regression that silently strips the narration's reference material. A warn
    (not a hard assert) so a partial drop still yields a usable manifest for
    manual recovery.
    """
    orig = sum(1 for t in manifest.get("tiers", [])
               for c in t.get("cards", []) if (c.get("detail") or "").strip())
    new = sum(1 for t in new_manifest.get("tiers", [])
              for c in t.get("cards", []) if (c.get("detail") or "").strip())
    if new < orig:
        print(f"  [WARN] author `detail` dropped in reconcile ({path}): "
              f"{orig} -> {new} cards with detail. `detail` must pass through "
              f"every rebuild path - check reconcile_cards.py.", file=sys.stderr)


def _flatten_board(board: dict):
    """[(tier, position, label)] in visual reading order (top tier -> bottom, L->R)."""
    out = []
    for tier_obj in board.get("tiers", []):
        tier = tier_obj.get("tier", "") or ""
        for card in tier_obj.get("cards", []):
            out.append({
                "tier": tier,
                "position": card.get("position"),
                "label": (card.get("label") or "").strip(),
            })
    return out


def _flatten_manifest(manifest: dict):
    """[{index, image_file, image_url, card_id, label, orig_tier}] in API order."""
    out = []
    for tier in manifest.get("tiers", []):
        tname = tier.get("name", "")
        for card in tier.get("cards", []):
            out.append({
                "index": card.get("index"),
                "image_file": card.get("image_file"),
                "image_url": card.get("image_url"),
                "card_id": card.get("card_id", ""),
                "detail": card.get("detail", ""),
                "label": (card.get("label") or "").strip(),
                # "text_card_data" means the label came from the card's own data,
                # not from reading an image — see _label_wins_over_board().
                "label_source": card.get("label_source", ""),
                "orig_tier": tname,
                "orig_color": tier.get("color", "#333333"),
                "orig_tier_index": tier.get("tier_index"),
            })
    return out


def _match_by_position(board_slots, man_cards):
    """Pair board slots to manifest cards by POSITION (i-th <-> i-th).

    Verified on real posts: the TierVibe API returns cards in the SAME order
    the board renders them (top tier -> bottom tier, left -> right within a
    tier). So when board_slots and man_cards have equal length, the i-th board
    slot is the i-th manifest card — match by position. Labels are then
    compared ONLY to flag disagreement, never as the matching key.

    This is more robust than label-matching when the per-card recognition is
    simply WRONG: a totally-different label string (e.g. board "Python" vs
    per-card "Snake") would never fuzzy-match, leaving the card orphaned and
    the board slot empty. Position is the truth; labels are confirmation only.
    """
    return [(slot, man_cards[i] if i < len(man_cards) else None)
            for i, slot in enumerate(board_slots)]


def _match_by_label(board_slots, man_cards):
    """Greedy label match: each board slot -> best unused manifest card.

    Returns list of (board_slot, man_card|None) aligned to board order, plus
    the list of unmatched manifest cards.
    """
    used = set()
    pairs = []
    for slot in board_slots:
        best = None
        best_score = 0.0
        # Pass 1: exact normalized match.
        for mc in man_cards:
            if mc["index"] in used:
                continue
            if slot["label"] and _norm(slot["label"]) and _norm(slot["label"]) == _norm(mc["label"]):
                best = mc
                best_score = 1.0
                break
        # Pass 2: fuzzy if no exact.
        if best is None and slot["label"]:
            for mc in man_cards:
                if mc["index"] in used:
                    continue
                if not mc["label"]:
                    continue
                r = _fuzzy_ratio(slot["label"], mc["label"])
                if r > best_score and r >= 0.85:
                    best = mc
                    best_score = r
        if best is not None:
            used.add(best["index"])
        pairs.append((slot, best))
    unmatched_cards = [mc for mc in man_cards if mc["index"] not in used]
    return pairs, unmatched_cards


def _attach_metadata_keep_api_order(manifest, pairs):
    """Fallback: don't reorder, just tag cards with board info where matched."""
    board_by_index = {}
    for slot, mc in pairs:
        if mc is not None:
            board_by_index[mc["index"]] = slot

    new_tiers = []
    for tier in manifest.get("tiers", []):
        cards = []
        for card in tier.get("cards", []):
            idx = card.get("index")
            slot = board_by_index.get(idx)
            c = dict(card)
            if slot is not None:
                c["board_tier"] = slot["tier"]
                c["board_position"] = slot["position"]
                c["matched"] = True
                lb, lc = slot["label"], (card.get("label") or "")
                c["label"] = lc if _label_wins_over_board(card) else (lb or lc)
                # Set both label fields so build_card_manifest's disagreement
                # row has both sides to show (C2 — fallback path previously
                # left these blank, making the ⚠ flag dead signal).
                c["board_label"] = lb
                c["card_label"] = lc
                c["label_disagreement"] = bool(lb and lc and _norm(lb) != _norm(lc))
            else:
                c["board_tier"] = None
                c["board_position"] = None
                c["matched"] = False
                c["board_label"] = None
                c["card_label"] = card.get("label") or ""
                c["label_disagreement"] = False
            cards.append(c)
        new_tiers.append({**tier, "cards": cards})

    new_manifest = dict(manifest)
    new_manifest["tiers"] = new_tiers
    new_manifest["reconcile"] = {
        "reordered_by_board": False,
        "note": "match rate < 50%; API order kept, board tags attached where matched",
    }
    return new_manifest


def reconcile(work_dir: str) -> dict:
    board_path = os.path.join(work_dir, "board_layout.json")
    manifest_path = os.path.join(work_dir, "manifest.json")
    if not os.path.exists(board_path):
        raise SystemExit(
            f"board_layout.json not found in {work_dir}.\n"
            f"Run the board-recognition step first: view board_hd.png and write "
            f"<work_dir>/board_layout.json with the visual layout "
            f"(tiers -> cards: {{position, label}} in reading order)."
        )
    if not os.path.exists(manifest_path):
        raise SystemExit(f"manifest.json not found in {work_dir} — run fetch_tierlist.py first.")

    with open(board_path, "r", encoding="utf-8") as f:
        board = json.load(f)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    board_slots = _flatten_board(board)
    man_cards = _flatten_manifest(manifest)

    if not board_slots:
        raise SystemExit("board_layout.json has no cards — nothing to reconcile.")
    if not man_cards:
        raise SystemExit("manifest.json has no cards — nothing to reconcile against.")

    # Detect duplicate tier names in the board (F4) — they'd silently merge
    # into one tier, losing the second tier's color/structure.
    # One name per TIER, not per card. board_slots is the per-card flattening, so
    # reading tier names off it made any tier holding 2+ cards look duplicated —
    # a false WARN on virtually every board. Warnings that cry wolf train people
    # to ignore the real ones.
    board_tier_names = [t.get("tier", "") for t in board.get("tiers", [])]
    if len(set(board_tier_names)) < len(board_tier_names):
        seen, dups = set(), set()
        for n in board_tier_names:
            (dups if n in seen else seen).add(n)
        print(f"  [WARN] duplicate tier name(s) in board_layout.json: "
              f"{sorted(dups)} — they will be merged into one tier. "
              f"Give each board tier a unique name.", file=sys.stderr)

    pairs, unmatched_cards = ([], [])
    if len(board_slots) == len(man_cards):
        # API order == board visual order (verified): match by position, use
        # labels only to flag disagreement.
        pairs = _match_by_position(board_slots, man_cards)
        unmatched_cards = []
    else:
        # Counts diverge (board miscounted or API differs): fall back to
        # label matching, which can leave slots/cards unmatched.
        pairs, unmatched_cards = _match_by_label(board_slots, man_cards)
    matched = sum(1 for _, mc in pairs if mc is not None)
    # Rate is the fraction of ALL cards (board AND manifest) reconciled —
    # dividing by only len(board_slots) would let a tiny board that matches
    # itself report 100% while orphaning most manifest cards. Use the larger
    # denominator so incomplete board recognition triggers the guard.
    rate = matched / max(len(board_slots), len(man_cards), 1)

    print(f"Board slots: {len(board_slots)} | manifest cards: {len(man_cards)} "
          f"| matched: {matched} ({rate:.0%}) | unmatched manifest cards: {len(unmatched_cards)}")

    disagreements = 0
    comparable = 0  # pairs where BOTH labels are non-empty (have signal)
    for slot, mc in pairs:
        if mc is None:
            continue
        if slot["label"] and mc["label"]:
            comparable += 1
            if _norm(slot["label"]) != _norm(mc["label"]):
                disagreements += 1

    # Back up the pre-reconcile manifest BEFORE any overwrite — including the
    # fallback path. The fallback (bad matching) is the path most likely to
    # need recovery, so it must not be the one that skips the backup. (C1)
    bak = os.path.join(work_dir, "manifest.pre_reconcile.json")
    shutil.copyfile(manifest_path, bak)

    # Guard 1: low overall match rate (counts-differ path). Don't reorder a
    # half-matched manifest — orphaned cards would land under _(unmatched)_.
    # Guard 2 (position-path safety, F1): when counts matched by POSITION,
    # also require the board's labels to broadly AGREE with the per-card
    # labels. A board the AI read in the WRONG ORDER (e.g. reversed) has the
    # right COUNT but every comparable position disagrees — position-zip would
    # silently assign every card to the wrong tier with reordered_by_board=true
    # and zero warning, the exact failure this script exists to catch. If most
    # comparable labels disagree, the board order is not trustworthy: fall back
    # to API order + warn.
    label_disagree_rate = (disagreements / comparable) if comparable > 0 else 0.0
    low_match = rate < 0.5
    board_order_untrusted = (
        len(board_slots) == len(man_cards)
        and comparable > 0
        and label_disagree_rate > 0.5
    )
    if low_match or board_order_untrusted:
        if low_match:
            reason = "match rate below 50%"
        else:
            reason = (f"board labels disagree with per-card labels in "
                      f"{label_disagree_rate:.0%} of comparable positions — "
                      f"board order not trustworthy (likely misread)")
        print(f"  [WARN] {reason} — NOT reordering. Keeping API tier order. "
              f"Board tags attached where matched. Manual review required.",
              file=sys.stderr)
        new_manifest = _attach_metadata_keep_api_order(manifest, pairs)
        _assert_detail_preserved(manifest, new_manifest, "fallback")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(new_manifest, f, ensure_ascii=False, indent=2)
        print(f"Manifest updated (API order kept): {manifest_path} (backup: {bak})")
        return new_manifest

    # Rebuild manifest.tiers in BOARD visual order. Preserve original tier
    # color/tier_index by looking up the board tier name in the API tiers.
    api_tier_lookup = {}  # tier_name -> {color, tier_index}
    for t in manifest.get("tiers", []):
        api_tier_lookup.setdefault(t.get("name", ""), {
            "color": t.get("color", "#333333"),
            "tier_index": t.get("tier_index"),
        })

    by_tier = {}
    tier_order = []
    for slot, mc in pairs:
        if mc is None:
            continue
        if slot["tier"] not in by_tier:
            by_tier[slot["tier"]] = []
            tier_order.append(slot["tier"])
        by_tier[slot["tier"]].append((slot, mc))

    new_tiers = []
    for slot_tier in tier_order:
        items = by_tier[slot_tier]
        items.sort(key=lambda x: (x[0]["position"] if x[0]["position"] is not None else 0))
        meta = api_tier_lookup.get(slot_tier, {"color": "#333333", "tier_index": None})
        cards = []
        for slot, mc in items:
            label_board = slot["label"]
            label_card = mc["label"]
            disagree = bool(label_board and label_card and _norm(label_board) != _norm(label_card))
            final_label = (label_card if _label_wins_over_board(mc)
                           else (label_board or label_card))
            cards.append({
                "index": mc["index"],
                "image_file": mc["image_file"],
                "image_url": mc["image_url"],
                "card_id": mc["card_id"],
                "detail": mc.get("detail", ""),
                "label": final_label,
                "label_source": mc.get("label_source", ""),
                "board_tier": slot["tier"],
                "board_position": slot["position"],
                "card_label": label_card,
                "board_label": label_board,
                "matched": True,
                "label_disagreement": disagree,
            })
        new_tiers.append({
            "tier_index": meta["tier_index"],
            "name": slot_tier,
            "color": meta["color"],
            "cards": cards,
        })

    # Unmatched manifest cards — append under a flagged tier so they are not
    # silently lost.
    if unmatched_cards:
        cards = []
        for mc in unmatched_cards:
            cards.append({
                "index": mc["index"],
                "image_file": mc["image_file"],
                "image_url": mc["image_url"],
                "card_id": mc["card_id"],
                "detail": mc.get("detail", ""),
                "label": mc["label"],
                "label_source": mc.get("label_source", ""),
                "board_tier": None,
                "board_position": None,
                # Preserve the card's original API tier so the reviewer can see
                # where the orphan came from when deciding where to re-place it
                # (A3 — previously dropped, leaving no clue about its origin).
                "orig_tier": mc["orig_tier"],
                "orig_color": mc["orig_color"],
                "card_label": mc["label"],
                "board_label": None,
                "matched": False,
                "label_disagreement": False,
            })
        new_tiers.append({
            "tier_index": None,
            "name": "_(unmatched)_",
            "color": "#666666",
            "cards": cards,
        })
        print(f"  [WARN] {len(unmatched_cards)} manifest card(s) had no board match — "
              f"appended under tier '_(unmatched)_'. Review board_layout.json.",
              file=sys.stderr)

    unmatched_board = sum(1 for _, mc in pairs if mc is None)
    new_manifest = dict(manifest)
    new_manifest["tiers"] = new_tiers
    new_manifest["reconcile"] = {
        "board_slots": len(board_slots),
        "manifest_cards": len(man_cards),
        "matched": matched,
        "match_rate": round(rate, 3),
        "label_disagreements": disagreements,
        "unmatched_board_slots": unmatched_board,
        "unmatched_manifest_cards": len(unmatched_cards),
        "reordered_by_board": True,
    }

    if disagreements:
        print(f"  [INFO] {disagreements} card(s) where board label != per-card label "
              f"— board label used, EXCEPT on text cards where the label comes "
              f"from the card's own data and wins. Rows flagged in "
              f"card_manifest.md.", file=sys.stderr)

    _assert_detail_preserved(manifest, new_manifest, "reorder")

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, ensure_ascii=False, indent=2)
    print(f"Reconciled manifest written: {manifest_path} (backup: {bak})")
    return new_manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reconcile board-image recognition (board_layout.json) with manifest.json"
    )
    parser.add_argument("work_dir", help="Working directory with board_layout.json + manifest.json")
    args = parser.parse_args()
    reconcile(args.work_dir)
