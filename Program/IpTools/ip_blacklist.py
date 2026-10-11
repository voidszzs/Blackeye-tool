# IP Blacklist Check
# check on common blacklists

from Config.Colors import *
from Config.Util import *

import socket


DNSBLS = [
    "zen.spamhaus.org",
    "b.barracudacentral.org",
    "bl.spamcop.net",
    "dnsbl.sorbs.net",
    "spam.dnsbl.sorbs.net",
    "cbl.abuseat.org",
    "dnsbl-1.uceprotect.net",
    "dnsbl-2.uceprotect.net",
    "psbl.surriel.com",
    "ubl.unsubscore.com",
    "dyna.spamrats.com",
    "spam.spamrats.com",
    "noptr.spamrats.com",
    "cbl.anti-spam.org.cn",
    "dnsbl.inps.de",
    "drone.abuse.ch",
    "http.dnsbl.sorbs.net",
    "misc.dnsbl.sorbs.net",
    "socks.dnsbl.sorbs.net",
    "spam.dnsbl.anonmails.de",
]


def reversed_ip(ip):
    return ".".join(reversed(ip.split(".")))


def check(ip, zone):
    try:
        q = f"{reversed_ip(ip)}.{zone}"
        socket.gethostbyname(q)
        return True
    except socket.gaierror:
        return False
    except Exception:
        return False


def run():
    banner()
    log("IP Blacklist Check", "info")

    ip = input_line("ip to check > ").strip()
    if not ip:
        pause(); return

    try:
        socket.inet_aton(ip)
    except OSError:
        log("not a valid ipv4", "err"); pause(); return

    print()
    hits = 0
    for zone in DNSBLS:
        listed = check(ip, zone)
        if listed:
            hits += 1
            print(f"  {RED}[LISTED]{RESET} {zone}")
        else:
            print(f"  {GREEN}[clean ]{RESET} {zone}")

    print()
    if hits:
        log(f"listed on {hits}/{len(DNSBLS)} blacklists", "warn")
    else:
        log("clean everywhere", "ok")
    pause()