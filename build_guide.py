#!/usr/bin/env python3
"""Builds the TV guides for TiviMate (run automatically by GitHub every 12 hours):
     guide.xml.gz        <- channels.txt       + sources.txt        (USA list)
     guide_world.xml.gz  <- channels_world.txt + sources_world.txt  (world list)
Each guide only keeps the channels listed in its channels file, so it stays small."""
import gzip, os, urllib.request, xml.etree.ElementTree as ET

DEFAULT_SOURCES = ["https://i.mjh.nz/PlutoTV/all.xml.gz", "https://i.mjh.nz/SamsungTVPlus/us.xml.gz",
                   "https://i.mjh.nz/Plex/us.xml.gz", "https://i.mjh.nz/Roku/all.xml.gz"]
cache = {}


def load(url):
    if url not in cache:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=300).read()
            if data[:2] == b"\x1f\x8b":
                data = gzip.decompress(data)
            cache[url] = ET.fromstring(data)
        except Exception as ex:
            print(f"  skipped {url}: {ex}")
            cache[url] = None
    return cache[url]


def build(suffix):
    chan_file, src_file, out_file = f"channels{suffix}.txt", f"sources{suffix}.txt", f"guide{suffix}.xml.gz"
    if not os.path.exists(chan_file):
        return
    wanted = {l.strip() for l in open(chan_file, encoding="utf-8") if l.strip()}
    sources = ([l.strip() for l in open(src_file, encoding="utf-8") if l.strip()]
               if os.path.exists(src_file) else DEFAULT_SOURCES)
    out = ET.Element("tv", {"generator-info-name": "combined-guide"})
    chans, progs, seen = [], [], set()
    for url in sources:
        root = load(url)
        if root is None:
            continue
        mine = set()
        for ch in root.iter("channel"):
            cid = ch.get("id")
            if cid in wanted and cid not in seen:
                seen.add(cid); mine.add(cid); chans.append(ch)
        for p in root.iter("programme"):
            if p.get("channel") in mine:
                progs.append(p)
        print(f"  {url}: {len(mine)} channels")
    if not chans:
        print(f"{out_file}: nothing matched - keeping the previous file")
        return
    out.extend(chans)
    out.extend(progs)
    with gzip.open(out_file, "wb") as f:
        ET.ElementTree(out).write(f, encoding="utf-8", xml_declaration=True)
    print(f"{out_file}: {len(chans)} channels, {len(progs)} programmes")


for sfx in ("", "_world"):
    build(sfx)
