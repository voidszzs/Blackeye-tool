# GeoIP Batch
# batch geolocate a file of ips

from Config.Colors import *
from Config.Util import *

import os
import time


def run():
    banner()
    log("GeoIP Batch", "info")

    path = input_line("path to file of ips (one per line) > ").strip()
    if not path:
        pause(); return
    if not os.path.exists(path):
        log("file not found", "err"); pause(); return

    try:
        import requests
    except ImportError:
        log("pip install requests", "err"); pause(); return

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        ips = [x.strip() for x in f if x.strip()]

    if not ips:
        log("empty file", "warn"); pause(); return

    log(f"{len(ips)} ips to look up", "info")
    rows = []

    # ip-api supports batch of 100 per request
    for i in range(0, len(ips), 100):
        chunk = ips[i:i+100]
        try:
            r = requests.post(
                "http://ip-api.com/batch?fields=status,country,regionName,city,isp,as,query",
                json=chunk, timeout=20)
            results = r.json()
            for ip, d in zip(chunk, results):
                if d.get("status") == "success":
                    rows.append((ip, d.get("country"), d.get("regionName"),
                                 d.get("city"), d.get("isp"), d.get("as")))
                    print(f"  {GREEN}{ip:<16}{RESET} "
                          f"{d.get('country','?'):<4} "
                          f"{d.get('regionName','?'):<18} "
                          f"{d.get('city','?'):<18} "
                          f"{DIM}{d.get('isp','?')}{RESET}")
                else:
                    rows.append((ip, "?", "?", "?", "?", "?"))
                    print(f"  {RED}{ip:<16} lookup failed{RESET}")
        except Exception as e:
            log(f"batch failed: {e}", "err")
        time.sleep(1.4)  # rate limit safety

    if confirm("\nsave csv? [y/n] "):
        body = "ip,country,region,city,isp,as\n" + "\n".join(
            f'"{r[0]}","{r[1]}","{r[2]}","{r[3]}","{r[4]}","{r[5]}"' for r in rows)
        save_output(timestamp_name("geoip_batch_", "csv"), body)
    pause()