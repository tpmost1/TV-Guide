#!/usr/bin/env python3
"""One-time test: can GitHub turn YouTube live webcams into stream links that play elsewhere?"""
import json, subprocess

CHANNELS = [
    "https://www.youtube.com/@EarthCam/streams",
    "https://www.youtube.com/@SkylineWebcams/streams",
    "https://www.youtube.com/@VirtualRailfan/streams",
    "https://www.youtube.com/@NASA/streams",
    "https://www.youtube.com/@ExploreLiveNatureCams/streams",
]


def run(args):
    p = subprocess.run(["yt-dlp", "--no-warnings"] + args, capture_output=True, text=True, timeout=180)
    return p.stdout, p.stderr


for ch in CHANNELS:
    out, err = run(["--flat-playlist", "-J", "--playlist-end", "60", ch])
    try:
        entries = json.loads(out).get("entries") or []
    except Exception:
        print(f"[FAIL] {ch}: {err.strip()[:300]}")
        continue
    live = [e for e in entries if e.get("live_status") == "is_live"]
    print(f"[OK] {ch}: {len(entries)} videos listed, {len(live)} live now")
    for e in live[:2]:
        url, err = run(["-g", "-f", "best[protocol^=m3u8]/best", f"https://www.youtube.com/watch?v={e['id']}"])
        print(f"   {e.get('title', '')[:60]}")
        print(f"   LINK: {url.strip()[:2000] or 'ERROR ' + err.strip()[:300]}")
