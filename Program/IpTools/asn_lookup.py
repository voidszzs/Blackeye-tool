# ASN Lookup
# asn / netblock info

from Config.Colors import *
from Config.Util import *


def run():
    banner()
    log("ASN Lookup", "info")

    target = input_line("asn (e.g. AS15169) or ip > ").strip()
    if not target:
        pause(); return

    try:
        import requests
    except ImportError:
        log("pip install requests", "err"); pause(); return

    q = target
    if not q.upper().startswith("AS") and "." in q:
        # ip -> get asn first
        try:
            r = requests.get(f"http://ip-api.com/json/{q}?fields=as,isp,org,query", timeout=10)
            d = r.json()
            if d.get("status") == "success":
                print()
                print(f"  {CYAN}ip     {RESET} {d.get('query')}")
                print(f"  {CYAN}isp    {RESET} {d.get('isp')}")
                print(f"  {CYAN}org    {RESET} {d.get('org')}")
                print(f"  {CYAN}as     {RESET} {d.get('as')}")
                pause(); return
        except Exception as e:
            log(f"failed: {e}", "err"); pause(); return

    # asn -> prefix list via bgpview
    asn = q.upper().lstrip("AS")
    try:
        r = requests.get(f"https://api.bgpview.io/asn/{asn}", timeout=12)
        d = r.json()
        data = d.get("data") or {}
    except Exception as e:
        log(f"failed: {e}", "err"); pause(); return

    if not data:
        log("no data", "warn"); pause(); return

    print()
    print(f"  {CYAN}name     {RESET} {data.get('name')}")
    print(f"  {CYAN}desc     {RESET} {data.get('description_full')}")
    print(f"  {CYAN}country  {RESET} {data.get('country_code')}")
    print(f"  {CYAN}website  {RESET} {data.get('website')}")
    print(f"  {CYAN}email    {RESET} {', '.join(data.get('email_contacts') or [])}")

    prefixes = data.get("prefixes") or []
    if prefixes:
        print(f"\n{WHITE}── prefixes ({len(prefixes)}) ──{RESET}")
        for p in prefixes[:50]:
            print(f"  {p.get('prefix')}  {DIM}{p.get('description','')}{RESET}")
        if len(prefixes) > 50:
            print(f"  {DIM}... and {len(prefixes)-50} more{RESET}")

    pause()