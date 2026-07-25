#!/usr/bin/env python3
"""Build a human-readable card manifest table (card_manifest.md).

Usage:
    python build_card_manifest.py <work_dir>

Merges the card file + tier (manifest.json, from fetch_tierlist.py) with the
label + narration (narration_script.json, from Step 6) into ONE markdown table
so the user can verify, at a glance, that each image file maps to the right
card name, tier, and narration — no "which card_003.png was that again?" confusion.

Reads:  <work_dir>/manifest.json
        <work_dir>/narration_script.json
Writes: <work_dir>/card_manifest.md
"""

import argparse
import json
import os


def build(work_dir: str) -> str:
    manifest_path = os.path.join(work_dir, "manifest.json")
    narration_path = os.path.join(work_dir, "narration_script.json")
    if not os.path.exists(manifest_path):
        raise SystemExit(f"manifest.json not found in {work_dir} — run fetch_tierlist.py first.")
    if not os.path.exists(narration_path):
        raise SystemExit(
            f"narration_script.json not found in {work_dir} — write the narration "
            f"script (Step 6) first; this table merges label + narration."
        )

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(narration_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    # index -> narration segment (label + narration come from here)
    seg_map = {s.get("index"): s for s in script.get("segments", [])}
    title = manifest.get("title") or script.get("title") or "Tier List"
    source_url = manifest.get("source_url", "")

    rows = []
    for tier in manifest.get("tiers", []):
        tier_name = tier.get("name", "")
        for card in tier.get("cards", []):
            idx = card.get("index")
            img = card.get("image_file") or "_(missing)_"
            label_manifest = card.get("label") or ""
            seg = seg_map.get(idx, {})
            label = seg.get("label") or label_manifest or "_(unidentified)_"
            narration = (seg.get("narration") or "").strip().replace("\n", " ").replace("|", "\\|")
            if len(narration) > 200:
                narration = narration[:197] + "..."

            # Board-first reconciliation columns. After reconcile_cards.py runs,
            # each card carries board_tier/board_position + the board's label
            # vs the per-card label. Show board position so the reviewer can
            # see the visual order, and flag any board-vs-card disagreement so
            # a wrong AI per-card guess is caught at review time (not in the
            # final video).
            board_pos = card.get("board_position")
            board_pos_s = str(board_pos) if board_pos is not None else "-"
            board_label = (card.get("board_label") or "").replace("|", "\\|")
            card_label_raw = (card.get("card_label") or "").replace("|", "\\|")
            disagree = card.get("label_disagreement", False)
            matched = card.get("matched")
            flag = ""
            if disagree:
                # Show BOTH labels so the reviewer can pick: board (context)
                # vs per-card (higher-res individual image). Escape the literal
                # separator pipes so the markdown row stays 6 columns (F3 —
                # an unescaped " | " split the row into 7 cells vs the 6-col
                # header, corrupting exactly the disagreement rows).
                label = f"⚠ board={board_label} \\| card={card_label_raw}"
            elif matched is False:
                flag = " ⚠unmatched"
                label = label.replace("|", "\\|")

            tier_name_clean = tier_name.replace("|", "\\|")
            rows.append((idx, img, tier_name_clean, board_pos_s, label, narration + flag))

    lines = [f"# {title}", ""]
    if source_url:
        lines.append(f"Source: {source_url}")
        lines.append("")
    lines += [f"Total cards: {len(rows)}", "",
              "| index | image file | tier | board_pos | card name | narration (preview) |",
              "|---|---|---|---|---|---|"]
    for idx, img, tier_name, board_pos_s, label, narration in rows:
        lines.append(f"| {idx} | {img} | {tier_name} | {board_pos_s} | {label} | {narration} |")

    out_path = os.path.join(work_dir, "card_manifest.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Card manifest written: {out_path} ({len(rows)} cards)")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build human-readable card manifest table")
    parser.add_argument("work_dir", help="Working directory with manifest.json + narration_script.json")
    args = parser.parse_args()
    build(args.work_dir)
