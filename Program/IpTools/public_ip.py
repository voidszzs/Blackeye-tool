# Public IP Fetcher
# show your external ip

from Config.Colors import *
from Config.Util import *


def run():
    banner()
    log("Public IP Fetcher", "info")

    try:
        import requests
    except ImportError:
        log("pip install requests", "err"); pause(); return

    sources = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
        "https://ipinfo.io/ip",
    ]
    for url in sources:
        try:
            r = requests.get(url, timeout=6,
                             headers={"User-Agent": "Mozilla/5.0"})
            ip = r.text.strip()
            if ip:
                log(f"public ip -> {ip}", "ok")

                # also try to geo it
                try:
                    g = requests.get(f"http://ip-api.com/json/{ip}", timeout=8).json()
                    if g.get("status") == "success":
                        print(f"  {CYAN}country{RESET} {g.get('country')}")
                        print(f"  {CYAN}region {RESET} {g.get('regionName')}")
                        print(f"  {CYAN}city   {RESET} {g.get('city')}")
                        print(f"  {CYAN}isp    {RESET} {g.get('isp')}")
                        print(f"  {CYAN}as     {RESET} {g.get('as')}")
                except Exception:
                    pass
                pause(); return
        except Exception:
            continue

    log("all sources failed", "err")
    pause()