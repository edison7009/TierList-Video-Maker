#!/usr/bin/env python3
"""Generate TTS narration audio from a script JSON using edge-tts.

Usage:
    python tts_narration.py generate <narration_script.json> -o <work_dir> [-v VOICE]
    python tts_narration.py voices -l <lang_prefix>
"""

import argparse
import asyncio
import json
import os
import sys


async def generate_all(script_path: str, out_dir: str, voice: str = "zh-CN-YunxiNeural"):
    try:
        import edge_tts
    except ImportError:
        print("Installing edge-tts...", file=sys.stderr)
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts", "-q"])
        import edge_tts

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    audio_dir = os.path.join(out_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    segments = script.get("segments", [])
    print(f"Generating TTS for {len(segments)} segments (voice: {voice})...")

    results = []
    for seg in segments:
        idx = seg["index"]
        text = seg.get("narration", "")
        if not text.strip():
            results.append({"index": idx, "audio_file": None, "duration": 0})
            continue

        filename = f"narration_{idx:03d}.mp3"
        filepath = os.path.join(audio_dir, filename)
        print(f"  [{idx}] {text[:50]}...")

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filepath)

        results.append({"index": idx, "audio_file": filename, "text": text})

    # Intro / outro TTS — generate so the video has a spoken opening / closing
    # instead of jumping straight to card 1 (user feedback). These are REQUIRED
    # for a usable video: if the script omits intro/outro text, the video gets a
    # silent title frame at both ends. Warn loudly (do not silently skip) so the
    # operator notices and fills them in. Always emit the keys in the manifest
    # (null when absent) so generate_video can tell "no audio because no text"
    # apart from "audio generation failed".
    intro_outro = {}
    for key, fname in (("intro", "narration_intro.mp3"), ("outro", "narration_outro.mp3")):
        text = (script.get(key) or "").strip()
        if not text:
            print(f"  [WARN] {key} text is EMPTY — the video will have a SILENT "
                  f"{key} title frame. Fill `{key}` in narration_script.json.",
                  file=sys.stderr)
            intro_outro[f"{key}_audio"] = None
            intro_outro[f"{key}_text_present"] = False
            continue

        fp = os.path.join(audio_dir, fname)
        print(f"  [{key}] {text[:50]}...")
        await edge_tts.Communicate(text, voice).save(fp)
        # Verify the file is non-zero — a 0-byte mp3 would load as a silent /
        # broken clip downstream and look like "no voiceover" (the exact bug
        # this guard exists to catch).
        if not os.path.exists(fp) or os.path.getsize(fp) == 0:
            raise SystemExit(
                f"edge-tts produced an empty/missing {fname} for {key}. "
                f"This is usually a transient network/voice issue — re-run "
                f"tts_narration.py. Do NOT proceed: generate_video would attach "
                f"a broken clip and the {key} would be silent."
            )
        intro_outro[f"{key}_audio"] = fname
        intro_outro[f"{key}_text_present"] = True

    audio_manifest = {"voice": voice, "segments": results, **intro_outro}
    manifest_path = os.path.join(out_dir, "audio_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(audio_manifest, f, ensure_ascii=False, indent=2)
    print(f"\nAudio manifest saved: {manifest_path}")
    return audio_manifest


def list_voices(language: str = "zh"):
    try:
        import edge_tts
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts", "-q"])
        import edge_tts

    async def _list():
        voices = await edge_tts.list_voices()
        for v in voices:
            if v["Locale"].startswith(language):
                print(f"  {v['ShortName']:30s} {v['Gender']:8s} {v['Locale']}")

    asyncio.run(_list())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate TTS narration audio")
    sub = parser.add_subparsers(dest="cmd")

    gen = sub.add_parser("generate", help="Generate audio from script")
    gen.add_argument("script", help="Path to narration script JSON")
    gen.add_argument("-o", "--output", default="tierlist_work", help="Output directory")
    gen.add_argument("-v", "--voice", default="zh-CN-YunxiNeural", help="TTS voice name")

    lv = sub.add_parser("voices", help="List available voices")
    lv.add_argument("-l", "--language", default="zh", help="Language prefix filter")

    args = parser.parse_args()
    if args.cmd == "generate":
        asyncio.run(generate_all(args.script, args.output, args.voice))
    elif args.cmd == "voices":
        list_voices(args.language)
    else:
        parser.print_help()
