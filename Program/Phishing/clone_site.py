# Clone Site
# download html/css/js of a page

from Config.Colors import *
from Config.Util import *

import os
import re
from urllib.parse import urljoin, urlparse


def run():
    banner()
    log("Clone Site", "info")

    try:
        import requests
    except ImportError:
        log("pip install requests", "err"); pause(); return

    url = input_line("url > ").strip()
    if not url:
        pause(); return
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    r = None
    try:
        r = requests.get(url, headers={"User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15)
    except Exception as e:
        log(f"fetch failed: {e}", "err"); pause(); return

    html = r.text
    parsed = urlparse(url)
    domain = parsed.netloc.replace(":", "_")

    out_dir = os.path.join(template_dir(), f"clone_{domain}_{int(__import__('time').time())}")
    os.makedirs(out_dir, exist_ok=True)

    # find and download stylesheets + scripts + images
    assets = set()
    for pat in [
        r'<link[^>]+href=["\']([^"\']+)["\']',
        r'<script[^>]+src=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\']',
    ]:
        for m in re.finditer(pat, html, re.I):
            assets.add(m.group(1))

    log(f"found {len(assets)} asset(s)", "info")

    for a in list(assets):
        if a.startswith(("data:", "javascript:", "mailto:", "#")):
            continue
        full = urljoin(url, a)
        try:
            rr = requests.get(full, headers={"User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=10)
            name = a.split("/")[-1].split("?")[0] or f"asset_{abs(hash(a))}"
            path = os.path.join(out_dir, name)
            with open(path, "wb") as f:
                f.write(rr.content)
            log(f"  downloaded {name} ({len(rr.content)} bytes)", "ok")
        except Exception as e:
            log(f"  failed {a}: {e}", "warn")

    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    log(f"clone saved -> {out_dir}", "ok")
    pause()