#!/usr/bin/env python3
"""Run automatically by GitHub every 3 hours. It does two things:

1. Builds USA.m3u = usa_base.m3u (your cleaned list) + Samsung TV Plus US channels.
   Samsung channels are filtered by your rules (English only, no religious/shopping,
   no out-of-area local news), skipped if you already have them, put into your groups,
   and everything is renumbered (each group starts on the next round hundred).
   New Samsung channels show up by themselves; removed ones drop off.

2. Builds the TV guides for TiviMate:
     guide.xml.gz        <- channels.txt       + sources.txt        (USA list, + Samsung channels)
     guide_world.xml.gz  <- channels_world.txt + sources_world.txt  (world list)
"""
import gzip, os, re, urllib.request, xml.etree.ElementTree as ET

DEFAULT_SOURCES = ["https://i.mjh.nz/PlutoTV/all.xml.gz", "https://i.mjh.nz/SamsungTVPlus/us.xml.gz",
                   "https://i.mjh.nz/Plex/us.xml.gz", "https://i.mjh.nz/Roku/all.xml.gz"]
SAMSUNG_M3U = "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists/samsungtvplus_us.m3u"
SAMSUNG_EPG = "https://i.mjh.nz/SamsungTVPlus/us.xml.gz"

GROUP_ORDER = ["Local Stations", "Movies", "Classic TV & Movies", "TV Shows", "Comedy", "Entertainment",
               "Kids & Family", "Documentary & Science", "Sports", "Lifestyle & Food", "Music", "Other", "News"]
SAMSUNG_GROUPS = {
    "Movies": "Movies", "Western & Classic TV": "Classic TV & Movies",
    "Action & Drama": "TV Shows", "Crime": "TV Shows", "Sci-Fi & Horror": "TV Shows",
    "Comedy": "Comedy",
    "Reality TV": "Entertainment", "Reality Competition": "Entertainment", "Game Shows": "Entertainment",
    "Lifestyle & Pop Culture": "Entertainment", "Anime & Gaming": "Entertainment",
    "Kids": "Kids & Family", "Nature, History & Science": "Documentary & Science",
    "Sports & Outdoors": "Sports", "Motor Sports": "Sports", "Home & Food": "Lifestyle & Food",
    "Music": "Music", "Ambiance": "Other", "News & Opinion": "News",
}
SKIP_GROUPS = {"Latino"}
SKIP_NAMES = re.compile(
    r"Charlotte|^WBTV|^WCNC|Amazon Live|Deal Zone|Christian|Dove Channel|Latin|Espa[nñ]ol|Univision|"
    r"Telemundo|ViX|Estrella|K-Drama|K-Movie|KMOVIES|K-Novela|K-Stories|K-Reality|K-Food|Series K ", re.I)

MINIMUM = 100
cache = {}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=300).read()
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def load(url):
    if url not in cache:
        try:
            cache[url] = ET.fromstring(fetch(url))
        except Exception as ex:
            print(f"  skipped {url}: {ex}")
            cache[url] = None
    return cache[url]


# ---------------------------------------------------------------- playlist (USA + Samsung)
def read_m3u(text):
    header, entries, cur = "#EXTM3U", [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            header = line
        elif line.startswith("#EXTINF"):
            cur = {"extinf": line, "opts": []}
        elif line.startswith("#"):
            if cur is not None:
                cur["opts"].append(line)
        elif cur is not None:
            cur["url"] = line
            entries.append(cur)
            cur = None
    return header, entries


def attr(s, name):
    m = re.search(r'\b' + name + r'="([^"]*)"', s)
    return m.group(1) if m else ""


def name_of(e):
    return e["extinf"].rsplit(",", 1)[-1].strip()


def norm(s):
    s = s.lower().replace("&", "and")
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    s = re.sub(r"\b(hd|tv|channel|the|by samsung tv plus)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def natural(s):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s.lower())]


def build_playlist():
    """Returns the set of Samsung tvg-ids that were added (for the guide)."""
    if not os.path.exists("usa_base.m3u"):
        return set()
    try:
        samsung_text = fetch(SAMSUNG_M3U).decode("utf-8", "replace")
    except Exception as ex:
        print(f"Samsung list not available ({ex}) - keeping the previous USA.m3u")
        return set()
    header, base = read_m3u(open("usa_base.m3u", encoding="utf-8").read())
    _, samsung = read_m3u(samsung_text)
    if len(samsung) < MINIMUM:
        print(f"Samsung list looks broken ({len(samsung)} channels) - keeping the previous USA.m3u")
        return set()

    have_ids = {attr(e["extinf"], "tvg-id") for e in base}
    have_names = {norm(name_of(e)) for e in base}
    groups = {g: [] for g in GROUP_ORDER}
    for e in base:
        groups.setdefault(attr(e["extinf"], "group-title"), []).append(e)

    added, skipped_rules, skipped_dupes = set(), 0, 0
    for e in samsung:
        x, name = e["extinf"], name_of(e)
        sg, cid = attr(x, "group-title"), attr(x, "tvg-id")
        if sg in SKIP_GROUPS or SKIP_NAMES.search(name):
            skipped_rules += 1; continue
        if cid in have_ids or norm(name) in have_names:
            skipped_dupes += 1; continue
        g = SAMSUNG_GROUPS.get(sg, "Other")
        x = re.sub(r'\s*channel-id="[^"]*"', "", x)
        e["extinf"] = x
        groups.setdefault(g, []).append(e)
        have_ids.add(cid); have_names.add(norm(name)); added.add(cid)

    out, num = [], 100
    for g in GROUP_ORDER + [g for g in groups if g not in GROUP_ORDER]:
        items = groups.get(g) or []
        if not items:
            continue
        if g != "Local Stations":
            items.sort(key=lambda e: natural(name_of(e)))
        for e in items:
            x = e["extinf"]
            x = re.sub(r'tvg-chno="\d*"', f'tvg-chno="{num}"', x) if "tvg-chno=" in x \
                else x.replace("#EXTINF:-1", f'#EXTINF:-1 tvg-chno="{num}"', 1)
            x = re.sub(r'group-title="[^"]*"', f'group-title="{g}"', x)
            out.append(x); out.extend(e["opts"]); out.append(e["url"])
            num += 1
        num = ((num + 99) // 100) * 100
    with open("USA.m3u", "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n" + "\n".join(out) + "\n")
    print(f"USA.m3u: {len(base)} of yours + {len(added)} Samsung "
          f"({skipped_dupes} already on your list, {skipped_rules} skipped by your rules)")
    return added


# ---------------------------------------------------------------- guides
def build(suffix, extra_ids=frozenset(), extra_sources=()):
    chan_file, src_file, out_file = f"channels{suffix}.txt", f"sources{suffix}.txt", f"guide{suffix}.xml.gz"
    if not os.path.exists(chan_file):
        return
    wanted = {l.strip() for l in open(chan_file, encoding="utf-8") if l.strip()} | set(extra_ids)
    sources = ([l.strip() for l in open(src_file, encoding="utf-8") if l.strip()]
               if os.path.exists(src_file) else list(DEFAULT_SOURCES))
    sources += [s for s in extra_sources if s not in sources]
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


if __name__ == "__main__":
    samsung_ids = build_playlist()
    build("", samsung_ids, [SAMSUNG_EPG] if samsung_ids else [])
    build("_world")
