# Reverse IP Lookup
# domains on same ip

from Config.Colors import *
from Config.Util import *


def run():
    banner()
    log("Reverse IP Lookup", "info")

    ip = input_line("ip > ").strip()
    if not ip:
        pause(); return

    try:
        import requests
    except ImportError:
        log("pip install requests", "err"); pause(); return

    # free source: rapiddns
    try:
        r = requests.get(f"https://rapiddns.io/sameip/{ip}?full=1",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        html = r.text
    except Exception as e:
        log(f"request failed: {e}", "err"); pause(); return

    import re
    domains = set()
    for m in re.finditer(r'href="//([a-zA-Z0-9\.\-]+\.[a-zA-Z]{2,})"', html):
        d = m.group(1).lower()
        if not any(d.endswith(x) for x in ["rapiddns.io", "twitter.com", "github.com"]):
            domains.add(d)

    if not domains:
        log("no domains found", "warn"); pause(); return

    print()
    for d in sorted(domains):
        print(f"  {GREEN}{d}{RESET}")

    if confirm("\nsave? [y/n] "):
        save_output(timestamp_name(f"revip_{ip.replace('.','_')}_", "txt"), "\n".join(sorted(domains)))
    pause()