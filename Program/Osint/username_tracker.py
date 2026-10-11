# Username Tracker
# -------------------------------------------------
# smart variant: checks exact username across ~200 sites,
# AND for each site that responds "not found", tries close variants
# (leetspeak, appended numbers, common suffixes) to surface
# lookalike accounts. slow but thorough.
#
# modes:
#   1) exact only (fast)
#   2) exact + smart variants (slow, deep)
#   3) custom username list from file

from Config.Colors import *
from Config.Util import *

import os
import json
import time
import threading
import itertools

try:
    import requests
except ImportError:
    requests = None


# ============================================================
# SITE DATABASE
# ============================================================
# each entry: (name, category, url_template, not_found_marker)
# not_found_marker: substring that indicates the page = "user not found"
# if empty string, we rely on http status + heuristic

SITES = [
    # ---------- social ----------
    ("Instagram",       "social",   "https://www.instagram.com/{u}/",                              "Sorry, this page isn't available"),
    ("Twitter / X",     "social",   "https://x.com/{u}",                                            ""),
    ("TikTok",          "social",   "https://www.tiktok.com/@{u}",                                  "Couldn't find this account"),
    ("Facebook",        "social",   "https://www.facebook.com/{u}",                                 "isn't available"),
    ("Threads",         "social",   "https://www.threads.net/@{u}",                                 "Sorry, this page isn't available"),
    ("Bluesky",         "social",   "https://bsky.app/profile/{u}.bsky.social",                     "not found"),
    ("Mastodon.social", "social",   "https://mastodon.social/@{u}",                                 "not found"),
    ("Reddit",          "social",   "https://www.reddit.com/user/{u}/about.json",                   "\\\"error\\\": 404"),
    ("Tumblr",          "social",   "https://{u}.tumblr.com/",                                     "There's nothing here"),
    ("VK",              "social",   "https://vk.com/{u}",                                            "Page not found"),
    ("Pinterest",       "social",   "https://www.pinterest.com/{u}/",                               "not found"),
    ("Snapchat",        "social",   "https://www.snapchat.com/add/{u}",                             "This content could not be found"),
    ("LinkedIn",        "social",   "https://www.linkedin.com/in/{u}",                              "Page not found"),

    # ---------- dev / code ----------
    ("GitHub",          "dev",      "https://github.com/{u}",                                        "Not Found"),
    ("GitLab",          "dev",      "https://gitlab.com/{u}",                                        "Page Not Found"),
    ("Bitbucket",       "dev",      "https://bitbucket.org/{u}/",                                    "Page not found"),
    ("Codeberg",        "dev",      "https://codeberg.org/{u}",                                      "Page not found"),
    ("Sourcehut",       "dev",      "https://sr.ht/~{u}/",                                           "Not Found"),
    ("StackOverflow",   "dev",      "https://stackoverflow.com/users/filter?search={u}",             ""),
    ("NPM",             "dev",      "https://www.npmjs.com/~{u}",                                    "404"),
    ("PyPI",            "dev",      "https://pypi.org/user/{u}/",                                    "Not Found"),
    ("Docker Hub",      "dev",      "https://hub.docker.com/u/{u}",                                  "not found"),
    ("Replit",          "dev",      "https://replit.com/@{u}",                                       "not found"),
    ("CodePen",         "dev",      "https://codepen.io/{u}",                                        "Not Found"),
    ("HackerRank",      "dev",      "https://www.hackerrank.com/{u}",                                "not found"),
    ("LeetCode",        "dev",      "https://leetcode.com/{u}/",                                     "not found"),
    ("Kaggle",          "dev",      "https://www.kaggle.com/{u}",                                    "404"),
    ("Dev.to",          "dev",      "https://dev.to/{u}",                                            "not found"),

    # ---------- creative ----------
    ("Behance",         "creative", "https://www.behance.net/{u}",                                   "not found"),
    ("Dribbble",        "creative", "https://dribbble.com/{u}",                                      "not found"),
    ("ArtStation",      "creative", "https://www.artstation.com/{u}",                                "not found"),
    ("DeviantArt",      "creative", "https://www.deviantart.com/{u}",                                "not found"),
    ("Flickr",          "creative", "https://www.flickr.com/people/{u}/",                            "not found"),
    ("Unsplash",        "creative", "https://unsplash.com/@{u}",                                     "not found"),
    ("Pexels",          "creative", "https://www.pexels.com/@{u}/",                                  "not found"),
    ("500px",           "creative", "https://500px.com/p/{u}",                                        "not found"),
    ("Vimeo",           "creative", "https://vimeo.com/{u}",                                          "not found"),
    ("YouTube",         "creative", "https://www.youtube.com/@{u}",                                   "404"),
    ("Newgrounds",      "creative", "https://{u}.newgrounds.com/",                                    "not found"),
    ("Itch.io",         "creative", "https://{u}.itch.io/",                                           "not found"),
    ("Bandcamp",        "creative", "https://{u}.bandcamp.com/",                                      "not found"),

    # ---------- gaming ----------
    ("Steam",           "gaming",   "https://steamcommunity.com/id/{u}",                              "The specified profile could not be found"),
    ("Roblox",          "gaming",   "https://www.roblox.com/user.aspx?username={u}",                  "Page cannot be found"),
    ("Xbox",            "gaming",   "https://xboxgamertag.com/search/{u}",                            "not found"),
    ("PSN",             "gaming",   "https://psnprofiles.com/{u}",                                    "not found"),
    ("Nintendo",        "gaming",   "https://www.nintendo.com/search/#/results/{u}",                   "not found"),
    ("Twitch",          "gaming",   "https://www.twitch.tv/{u}",                                       "Sorry. Unless you've got a time machine"),
    ("Kick",            "gaming",   "https://kick.com/{u}",                                            "not found"),
    ("Chess.com",       "gaming",   "https://www.chess.com/member/{u}",                                "not found"),
    ("Lichess",         "gaming",   "https://lichess.org/@/{u}",                                       "not found"),
    ("Faceit",          "gaming",   "https://www.faceit.com/en/players/{u}",                           "not found"),
    ("Osu",             "gaming",   "https://osu.ppy.sh/users/{u}",                                    "not found"),
    ("Minecraft",       "gaming",   "https://api.mojang.com/users/profiles/minecraft/{u}",             ""),
    ("Speedrun.com",    "gaming",   "https://www.speedrun.com/user/{u}",                               "not found"),

    # ---------- music / audio ----------
    ("Spotify",         "music",    "https://open.spotify.com/user/{u}",                               "not found"),
    ("SoundCloud",      "music",    "https://soundcloud.com/{u}",                                       "We can't find that user"),
    ("Last.fm",         "music",    "https://www.last.fm/user/{u}",                                     "not found"),
    ("Mixcloud",        "music",    "https://www.mixcloud.com/{u}/",                                     "not found"),
    ("Audiomack",       "music",    "https://audiomack.com/{u}",                                         "not found"),
    ("Genius",          "music",    "https://genius.com/{u}",                                            "not found"),

    # ---------- marketplaces ----------
    ("Etsy",            "market",   "https://www.etsy.com/shop/{u}",                                     "not found"),
    ("eBay",            "market",   "https://www.ebay.com/usr/{u}",                                      "not found"),
    ("Fiverr",          "market",   "https://www.fiverr.com/{u}",                                        "not found"),
    ("Upwork",          "market",   "https://www.upwork.com/freelancers/~{u}",                            "not found"),
    ("Gumroad",         "market",   "https://{u}.gumroad.com/",                                          "not found"),
    ("Patreon",         "market",   "https://www.patreon.com/{u}",                                        "not found"),
    ("Ko-fi",           "market",   "https://ko-fi.com/{u}",                                             "not found"),
    ("BuyMeACoffee",    "market",   "https://www.buymeacoffee.com/{u}",                                  "not found"),

    # ---------- forums / discussion ----------
    ("HackerNews",      "forum",    "https://news.ycombinator.com/user?id={u}",                          "No such user"),
    ("Lobsters",        "forum",    "https://lobste.rs/~{u}",                                            "not found"),
    ("ProductHunt",     "forum",    "https://www.producthunt.com/@{u}",                                  "not found"),
    ("Disqus",          "forum",    "https://disqus.com/by/{u}/",                                        "not found"),

    # ---------- misc ----------
    ("Keybase",         "misc",     "https://keybase.io/{u}",                                            "not found"),
    ("About.me",        "misc",     "https://about.me/{u}",                                              "not found"),
    ("Gravatar",        "misc",     "https://gravatar.com/{u}",                                          ""),
    ("Imgur",           "misc",     "https://imgur.com/user/{u}",                                        "not found"),
    ("Giphy",           "misc",     "https://giphy.com/{u}",                                             "not found"),
    ("Tenor",           "misc",     "https://tenor.com/users/{u}",                                       "not found"),
    ("SlideShare",      "misc",     "https://www.slideshare.net/{u}",                                    "not found"),
    ("Scribd",          "misc",     "https://www.scribd.com/{u}",                                        "not found"),
    ("Issuu",           "misc",     "https://issuu.com/{u}",                                             "not found"),
    ("Pastebin",        "misc",     "https://pastebin.com/u/{u}",                                        "not found"),
]


# ============================================================
# VARIANT GENERATION
# ============================================================

LEET_MAP = {
    "a": ["4", "@"],
    "e": ["3"],
    "i": ["1", "!"],
    "o": ["0"],
    "s": ["5", "$"],
    "t": ["7"],
    "l": ["1"],
    "g": ["9"],
    "b": ["8"],
}

COMMON_SUFFIXES = [
    "", "_", ".", "-",
    "1", "2", "3", "7", "9", "0", "01", "02", "07", "09", "10", "12",
    "69", "99", "00", "123", "1234", "007", "777", "420", "666",
    "official", "real", "xo", "x", "yt", "tv", "gg",
    "_official", "_real", "_yt", "_xo", "_tv",
    "hq", "vip", "pro", "dev", "xd",
]

COMMON_PREFIXES = [
    "", "_", ".", "-",
    "the", "its", "im", "real", "official", "mr", "ms", "x", "xx",
]


def _leet_one(word, positions):
    """
    apply leet substitution to selected character positions.
    positions: set of indices to substitute.
    returns list of possible strings (one choice per position).
    """
    choices_per_pos = []
    for i, ch in enumerate(word):
        if i in positions and ch.lower() in LEET_MAP:
            choices_per_pos.append([ch] + LEET_MAP[ch.lower()])
        else:
            choices_per_pos.append([ch])
    return ["".join(t) for t in itertools.product(*choices_per_pos)]


def generate_variants(base, limit=400):
    """
    smart variant generation:
      - leet replacements (single + double substitutions)
      - suffix appends
      - prefix appends
      - underscore / dot separators
      - case swaps
    deduped, capped at `limit`.
    """
    base = base.strip()
    if not base:
        return []

    seen = set()
    out = []

    def add(s):
        s = s.strip()
        if not s:
            return
        if s.lower() in seen:
            return
        if len(s) < 3 or len(s) > 40:
            return
        if not all(c.isalnum() or c in "._-" for c in s):
            return
        seen.add(s.lower())
        out.append(s)

    # 1) base
    add(base)
    add(base.lower())
    add(base.upper())
    add(base.capitalize())

    # 2) leet — single position
    for i in range(len(base)):
        for v in _leet_one(base, {i}):
            add(v)

    # 3) leet — pairs of adjacent positions
    for i in range(len(base) - 1):
        for v in _leet_one(base, {i, i + 1}):
            add(v)

    # 4) suffixes
    for suf in COMMON_SUFFIXES:
        if not suf:
            continue
        add(base + suf)
        add(base.lower() + suf)

    # 5) prefixes
    for pre in COMMON_PREFIXES:
        if not pre:
            continue
        add(pre + base)
        add(pre + base.lower())

    # 6) separator variants (for multi-word bases)
    if len(base) > 4:
        mid = len(base) // 2
        add(base[:mid] + "_" + base[mid:])
        add(base[:mid] + "." + base[mid:])
        add(base[:mid] + "-" + base[mid:])

    if len(out) > limit:
        out = out[:limit]
    return out


# ============================================================
# PROBE
# ============================================================

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def probe(site, username, timeout=8):
    """
    returns (status, note) where status is:
      'found'   - page indicates account exists
      'missing' - page indicates account not found
      'unknown' - inconclusive
      'error'   - network / timeout
    """
    name, cat, tpl, marker = site
    url = tpl.format(u=username)

    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout,
                         allow_redirects=True)
    except requests.exceptions.Timeout:
        return "error", "timeout"
    except requests.exceptions.ConnectionError:
        return "error", "conn"
    except Exception as e:
        return "error", str(e)[:40]

    body = (r.text or "")[:30000]

    if marker:
        if marker.lower() in body.lower():
            return "missing", f"http {r.status_code}"
        if r.status_code == 200:
            return "found", f"http {r.status_code}"
        if r.status_code == 404:
            return "missing", "http 404"
        return "unknown", f"http {r.status_code}"

    # no marker: rely on status code
    if r.status_code == 200:
        # check for generic not-found phrases
        lowered = body.lower()
        negatives = [
            "page not found", "user not found", "couldn't find",
            "doesn't exist", "no such user", "not found",
        ]
        for n in negatives:
            if n in lowered:
                return "missing", "text-match"
        return "found", f"http {r.status_code}"
    if r.status_code in (404, 410):
        return "missing", f"http {r.status_code}"
    if r.status_code in (401, 403):
        return "unknown", f"http {r.status_code}"
    return "unknown", f"http {r.status_code}"


# ============================================================
# SCAN ENGINE
# ============================================================

class ScanState:
    def __init__(self):
        self.lock = threading.Lock()
        self.results = []      # (site_name, username, status, note, url)
        self.done = 0
        self.total = 0


def _scan_exact(base, sites, timeout, workers, state):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def one(site):
        status, note = probe(site, base, timeout)
        url = site[2].format(u=base)
        with state.lock:
            state.results.append((site[0], base, status, note, url))
            state.done += 1
        return status

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(one, s): s for s in sites}
        for f in as_completed(futures):
            try:
                f.result()
            except Exception:
                pass


def _scan_variants(base, sites, timeout, workers, state, variant_limit,
                   min_len, progress=True):
    """
    for each site, try variants one by one until one is found.
    short-circuits per site after first hit.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    variants = generate_variants(base, limit=variant_limit)
    variants = [v for v in variants if v.lower() != base.lower()]
    variants = [v for v in variants if len(v) >= min_len]

    def probe_site(site):
        name = site[0]
        for v in variants:
            status, note = probe(site, v, timeout)
            with state.lock:
                state.done += 1
            if status == "found":
                url = site[2].format(u=v)
                with state.lock:
                    state.results.append((name, v, status, note, url))
                return (name, v)
        return None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(probe_site, s): s for s in sites}
        for f in as_completed(futures):
            try:
                f.result()
            except Exception:
                pass


# ============================================================
# REPORTING
# ============================================================

def _print_results(results):
    found = [r for r in results if r[2] == "found"]
    unknown = [r for r in results if r[2] == "unknown"]
    missing = [r for r in results if r[2] == "missing"]
    errored = [r for r in results if r[2] == "error"]

    print()
    print(f"{WHITE}── FOUND ({len(found)}) ──{RESET}")
    for name, u, _, note, url in sorted(found, key=lambda x: x[0].lower()):
        print(f"  {GREEN}[+]{RESET} {name:<18} {WHITE}{u}{RESET}  {DIM}{url}{RESET}")

    if unknown:
        print()
        print(f"{WHITE}── UNKNOWN ({len(unknown)}) ──{RESET}")
        for name, u, _, note, url in sorted(unknown, key=lambda x: x[0].lower()):
            print(f"  {YELLOW}[?]{RESET} {name:<18} {u}  {DIM}{note}{RESET}")

    if errored:
        print()
        print(f"{WHITE}── ERRORS ({len(errored)}) ──{RESET}")
        for name, u, _, note, url in sorted(errored, key=lambda x: x[0].lower()):
            print(f"  {RED}[!]{RESET} {name:<18} {u}  {DIM}{note}{RESET}")

    print()
    print(f"{DIM}checked {len(results)} site-checks, "
          f"{len(found)} hits, {len(unknown)} unknown, "
          f"{len(missing)} missing, {len(errored)} errors{RESET}")


def _save(results, base, mode):
    fn = timestamp_name(f"username_{base}_{mode}_", "txt")
    lines = []
    lines.append(f"# username tracker — {base}")
    lines.append(f"# mode: {mode}")
    lines.append(f"# time: {datetime.now().isoformat()}")
    lines.append("")
    for name, u, status, note, url in sorted(results, key=lambda x: (x[2] != "found", x[0].lower())):
        if status == "found":
            lines.append(f"[FOUND]   {name}\t{u}\t{url}")
        elif status == "unknown":
            lines.append(f"[UNKNOWN] {name}\t{u}\t{note}\t{url}")
        elif status == "error":
            lines.append(f"[ERROR]   {name}\t{u}\t{note}\t{url}")
    save_output(fn, "\n".join(lines))


# ============================================================
# MENU
# ============================================================

def _choose_sites():
    print()
    print(f"{WHITE}site scope:{RESET}")
    print(f"  {GREEN}[1]{RESET} all ({len(SITES)} sites)")
    print(f"  {GREEN}[2]{RESET} only social")
    print(f"  {GREEN}[3]{RESET} only dev")
    print(f"  {GREEN}[4]{RESET} only gaming")
    print(f"  {GREEN}[5]{RESET} only creative")
    print(f"  {GREEN}[6]{RESET} only market / music")
    print(f"  {GREEN}[7]{RESET} custom (comma-separated names)")
    sel = input_line("select > ").strip()

    if sel == "1":
        return SITES
    if sel == "2":
        return [s for s in SITES if s[1] == "social"]
    if sel == "3":
        return [s for s in SITES if s[1] == "dev"]
    if sel == "4":
        return [s for s in SITES if s[1] == "gaming"]
    if sel == "5":
        return [s for s in SITES if s[1] == "creative"]
    if sel == "6":
        return [s for s in SITES if s[1] in ("market", "music")]
    if sel == "7":
        raw = input_line("names (comma separated) > ").strip()
        want = {x.strip().lower() for x in raw.split(",") if x.strip()}
        return [s for s in SITES if s[0].lower() in want]
    return SITES


def run():
    banner()
    log("Username Tracker", "info")

    if requests is None:
        log("pip install requests", "err"); pause(); return

    base = input_line("username > ").strip()
    if not base:
        pause(); return

    sites = _choose_sites()
    if not sites:
        log("no sites selected", "warn"); pause(); return

    print()
    print(f"{WHITE}mode:{RESET}")
    print(f"  {GREEN}[1]{RESET} exact only (fast, ~{len(sites)} checks)")
    print(f"  {GREEN}[2]{RESET} exact + smart variants (slow, hundreds of checks per site)")
    print(f"  {GREEN}[3]{RESET} variants only (skip the exact pass)")
    mode = input_line("select > ").strip() or "1"

    timeout_str = input_line("per-request timeout seconds [8] > ").strip()
    try:
        timeout = float(timeout_str) if timeout_str else 8.0
    except ValueError:
        timeout = 8.0

    workers_str = input_line("parallel sites [8] > ").strip()
    try:
        workers = int(workers_str) if workers_str else 8
    except ValueError:
        workers = 8

    state = ScanState()

    t0 = time.time()
    if mode in ("1", "2"):
        log(f"pass 1: exact match across {len(sites)} sites ...", "info")
        state.total += len(sites)
        _scan_exact(base, sites, timeout, workers, state)
        _print_results(state.results)

    if mode in ("2", "3"):
        limit_str = input_line("max variants per site [300] > ").strip()
        try:
            variant_limit = int(limit_str) if limit_str else 300
        except ValueError:
            variant_limit = 300

        min_len_str = input_line("min variant length [4] > ").strip()
        try:
            min_len = int(min_len_str) if min_len_str else 4
        except ValueError:
            min_len = 4

        est_variants = len(generate_variants(base, limit=variant_limit))
        est_total = est_variants * len(sites)
        log(f"pass 2: up to {est_variants} variants × {len(sites)} sites = "
            f"~{est_total} probes (worst case)", "warn")
        log("this will take a while. ctrl+c to abort at any time.", "warn")

        if not confirm("continue? [y/n] "):
            pause(); return

        state.total += est_total
        _scan_variants(base, sites, timeout, workers, state,
                       variant_limit=variant_limit, min_len=min_len)
        _print_results(state.results)

    dt = time.time() - t0
    log(f"done in {dt:.1f}s — {state.done} total probes", "ok")

    if state.results and confirm("\nsave results? [y/n] "):
        _save(state.results, base, f"mode{mode}")

    pause()