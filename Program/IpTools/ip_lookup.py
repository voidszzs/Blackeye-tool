# IP Lookup / Geolocation
# geolocation + asn

from Config.Colors import *
from Config.Util import *


def run():
    banner()
    log("IP Lookup / Geolocation", "info")

    target = input_line("ip or hostname > ").strip()
    if not target:
        log("no input", "warn"); pause(); return

    # resolve hostname to ip first
    ip = target
    if not target.replace(".", "").isdigit():
        resolved = resolve_host(target)
        if not resolved:
            log(f"could not resolve {target}", "err"); pause(); return
        log(f"resolved -> {resolved}", "ok")
        ip = resolved

    try:
        import requests
    except ImportError:
        log("requests not installed. pip install requests", "err"); pause(); return

    fields = "status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query,reverse"
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?fields={fields}", timeout=10)
        data = r.json()
    except Exception as e:
        log(f"lookup failed: {e}", "err"); pause(); return

    if data.get("status") != "success":
        log(f"lookup error: {data.get('message','unknown')}", "err"); pause(); return

    print()
    print(f"{WHITE}── {data.get('query','?')} ──{RESET}")
    rows = [
        ("country",  f"{data.get('country','?')} ({data.get('countryCode','?')})"),
        ("region",   f"{data.get('regionName','?')} [{data.get('region','?')}]"),
        ("city",     data.get("city", "?")),
        ("zip",      data.get("zip", "?")),
        ("lat/lon",  f"{data.get('lat','?')}, {data.get('lon','?')}"),
        ("timezone", data.get("timezone", "?")),
        ("isp",      data.get("isp", "?")),
        ("org",      data.get("org", "?")),
        ("as",       data.get("as", "?")),
        ("reverse",  data.get("reverse", "?")),
    ]
    for k, v in rows:
        print(f"  {CYAN}{k:<9}{RESET} {v}")

    if confirm("\nsave to Output/? [y/n] "):
        fn = timestamp_name(f"iplookup_{ip.replace('.','_')}_", "txt")
        body = "\n".join(f"{k}: {v}" for k, v in rows)
        save_output(fn, body)
    pause()