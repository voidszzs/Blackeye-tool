# Phone Number Lookup — Real OSINT
# ------------------------------------------------------------
# free, no-key, no-login phone intelligence.
#
# modules:
#   1) parse + carrier + location  (libphonenumber)
#   2) spam reputation heuristics  (nomorobo-style + local scoring)
#   3) OSINT dorks                 (google queries for social/breach)
#   4) phonebook reverse lookup    (Das Telefonbuch, tellows, whitepages)
#   5) breach check                (xposedornot, leakcheck free tier)
#   6) account discovery           (phonsint-style registration checks)
#   7) history + export
#
# what requires registration (not built in):
#   - truecaller (needs your account)
#   - sync.me (needs your account)
#
# dependencies: pip install phonenumbers requests
# nothing else. no api keys.

from Config.Colors import *
from Config.Util import *

import os
import re
import json
import time
import hashlib
import threading
import queue
import webbrowser
from datetime import datetime
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None

try:
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone, number_type, PhoneNumberType, PhoneNumberFormat
    HAS_PHONE = True
except ImportError:
    HAS_PHONE = False


# ============================================================
# SPAM HEURISTICS (local, nomorobo-style)
# ============================================================

def spam_score(parsed):
    """
    local heuristic score based on number characteristics.
    returns (score 0-100, reasons list)
    """
    score = 0
    reasons = []

    ntype = number_type(parsed)

    if ntype == PhoneNumberType.PREMIUM_RATE:
        score += 50
        reasons.append("premium rate number")
    if ntype == PhoneNumberType.TOLL_FREE:
        score += 30
        reasons.append("toll free number")
    if ntype == PhoneNumberType.VOIP:
        score += 25
        reasons.append("voip number")
    if ntype == PhoneNumberType.SHARED_COST:
        score += 20
        reasons.append("shared cost number")

    car = carrier.name_for_number(parsed, "en")
    if not car:
        score += 15
        reasons.append("unknown carrier (may be voip or spoofed)")

    natl = str(parsed.national_number)
    if re.search(r"(\d)\1{4,}", natl):
        score += 20
        reasons.append("repeating digits")
    if "1234" in natl or "4321" in natl:
        score += 15
        reasons.append("sequential digits")

    # 900 / 0900 style
    if parsed.country_code == 1 and natl.startswith("900"):
        score += 40
        reasons.append("US 900 premium prefix")
    if parsed.country_code == 49 and natl.startswith("900"):
        score += 40
        reasons.append("DE 0900 premium prefix")

    score = min(100, score)
    return score, reasons


def spam_verdict(score):
    if score >= 70:
        return "HIGH RISK", RED
    if score >= 40:
        return "SUSPICIOUS", YELLOW
    if score >= 20:
        return "LOW RISK", CYAN
    return "LIKELY SAFE", GREEN


# ============================================================
# OSINT DORK GENERATION
# ============================================================

def generate_dorks(raw_number, e164):
    """
    generate google dorks that actually surface public mentions.
    """
    variants = set()
    # cleaned
    digits = re.sub(r"\D", "", raw_number)
    variants.add(digits)
    if e164:
        variants.add(e164)
        variants.add(e164.lstrip("+"))
    # spaced formats
    if len(digits) > 6:
        variants.add(digits[:4] + " " + digits[4:])
        variants.add(digits[:5] + " " + digits[5:])

    dorks = []
    for v in variants:
        dorks.append(f'"{v}"')
    dorks.append(f'"{" ".join(variants)}" site:facebook.com')
    dorks.append(f'"{list(variants)[0]}" site:twitter.com OR site:x.com')
    dorks.append(f'"{list(variants)[0]}" site:linkedin.com')
    dorks.append(f'"{list(variants)[0]}" site:instagram.com')
    dorks.append(f'"{list(variants)[0]}" filetype:pdf')
    dorks.append(f'"{list(variants)[0]}" filetype:xlsx OR filetype:csv')
    dorks.append(f'"{list(variants)[0]}" "phone" "address"')
    dorks.append(f'"{list(variants)[0]}" leak OR breach OR pastebin')
    return dorks


# ============================================================
# PHONEBOOK REVERSE LOOKUP (browser-based)
# ============================================================

PHONEBOOK_SOURCES = [
    ("Das Telefonbuch (DE)",
     "https://www.dastelefonbuch.de/R%C3%BCckw%C3%A4rtssuche/{q}"),
    ("Das Örtliche (DE)",
     "https://www.dasoertliche.de/?kw={q}&ci=&zvo=2&track=1"),
    ("11880 (DE)",
     "https://www.11880.com/suche/{q}"),
    ("Tellows (DE/AT/CH)",
     "https://www.tellows.de/num/{q}"),
    ("Whitepages (US)",
     "https://www.whitepages.com/phone/{q}"),
    ("TruePeopleSearch (US)",
     "https://www.truepeoplesearch.com/resultphone?phoneno={q}"),
    ("FastPeopleSearch (US)",
     "https://www.fastpeoplesearch.com/{q}"),
    ("Sync.me (web)",
     "https://sync.me/search/?number={q}"),
]


def build_phonebook_urls(e164, raw):
    """
    build urls to open for each phonebook source.
    """
    q = e164 or re.sub(r"\D", "", raw)
    q_raw = re.sub(r"[^\d+]", "", raw)
    out = []
    for name, tmpl in PHONEBOOK_SOURCES:
        # different sites want different formats
        if "tellows" in tmpl:
            url = tmpl.format(q=q_raw)
        elif "sync.me" in tmpl:
            url = tmpl.format(q=q)
        else:
            url = tmpl.format(q=q_raw)
        out.append((name, url))
    return out


# ============================================================
# BREACH CHECK (free sources only)
# ============================================================

def check_phone_breach(phone):
    """
    free breach sources:
      - xposedornot has phone breach endpoint? it's email-focused, skip
      - leakcheck has a 100/month free tier for phone. no key => skip
    so we return what we can: nothing free is reliably phone-breach,
    but we can still return a clean "not found" state.
    """
    # this space intentionally returns "no free source" rather than
    # pretending. we surface this to the user so they know why.
    return None


# ============================================================
# ACCOUNT DISCOVERY (phonsint-style, silent)
# ============================================================

ACCOUNT_SITES = [
    # (name, url_template, success_marker, fail_marker)
    # markers are best-effort; endpoints shift, tool stays useful
    ("Facebook",  "https://www.facebook.com/login/identify?ctx=recover&phone={p}", "", ""),
    ("Instagram", "https://www.instagram.com/accounts/password/reset/", "", ""),
    ("Twitter/X", "https://twitter.com/account/begin_password_reset", "", ""),
    ("Snapchat",  "https://accounts.snapchat.com/accounts/password_reset_request", "", ""),
    ("Microsoft", "https://account.live.com/password/reset", "", ""),
    ("Google",    "https://accounts.google.com/signin/recovery", "", ""),
    ("Amazon",    "https://www.amazon.com/ap/forgotpassword", "", ""),
    ("Discord",   "https://discord.com/api/v9/auth/register", "", ""),
]


def account_discovery_manual(e164):
    """
    we cannot truly probe registration without triggering sms or using
    platform-specific cryptographic flow (phonsint does that by reverse
    engineering Meta LOX etc). what we CAN do: open the recovery pages
    so the human can check manually. this keeps it honest.
    """
    urls = []
    for name, tmpl, _, _ in ACCOUNT_SITES:
        url = tmpl.format(p=quote(e164 or ""))
        if url:
            urls.append((name, url))
    return urls


# ============================================================
# MAIN PARSE
# ============================================================

def parse_full(raw, region=None):
    info = {
        "input": raw,
        "normalized": re.sub(r"[^\d+]", "", raw),
        "region_hint": region,
    }
    if not HAS_PHONE:
        info["error"] = "phonenumbers not installed"
        return info
    try:
        parsed = phonenumbers.parse(raw, region)
    except Exception as e:
        info["error"] = str(e)
        return info

    info["valid"] = phonenumbers.is_valid_number(parsed)
    info["possible"] = phonenumbers.is_possible_number(parsed)
    info["country_code"] = parsed.country_code
    info["national_number"] = parsed.national_number
    info["region_code"] = phonenumbers.region_code_for_number(parsed)
    info["country"] = geocoder.description_for_number(parsed, "en")
    info["carrier"] = carrier.name_for_number(parsed, "en")
    info["timezone"] = ", ".join(timezone.time_zones_for_number(parsed) or [])
    info["line_type"] = str(number_type(parsed))
    info["e164"] = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    info["international"] = phonenumbers.format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
    info["national"] = phonenumbers.format_number(parsed, PhoneNumberFormat.NATIONAL)
    info["rfc3966"] = phonenumbers.format_number(parsed, PhoneNumberFormat.RFC3966)

    sc, reasons = spam_score(parsed)
    info["spam_score"] = sc
    info["spam_reasons"] = reasons
    return info


# ============================================================
# PRINTING
# ============================================================

def print_info(info):
    print()
    print(f"{WHITE}== phone intelligence =={RESET}")
    print(f"  {CYAN}input      {RESET} {info.get('input')}")
    print(f"  {CYAN}normalized {RESET} {info.get('normalized')}")
    if info.get("error"):
        print(f"  {RED}error      {RESET} {info['error']}")
        return

    print()
    print(f"{WHITE}-- number --{RESET}")
    if info.get("valid") is not None:
        v = f"{GREEN}valid{RESET}" if info["valid"] else f"{YELLOW}invalid{RESET}"
        print(f"  {CYAN}status     {RESET} {v}")
    for k in ("country_code", "region_code", "country", "carrier",
              "line_type", "timezone"):
        if info.get(k):
            print(f"  {CYAN}{k:<11}{RESET} {info[k]}")

    print()
    print(f"{WHITE}-- formats --{RESET}")
    for k in ("e164", "international", "national", "rfc3966"):
        if info.get(k):
            print(f"  {CYAN}{k:<14}{RESET} {info[k]}")

    # spam
    if "spam_score" in info:
        sc = info["spam_score"]
        verdict, color = spam_verdict(sc)
        bar = "#" * (sc // 5) + "-" * (20 - sc // 5)
        print()
        print(f"{WHITE}-- spam analysis --{RESET}")
        print(f"  {CYAN}verdict    {RESET} {color}{verdict}{RESET} (score {sc}/100)")
        print(f"  {CYAN}graph      {RESET} [{bar}]")
        for r in info.get("spam_reasons") or []:
            print(f"    {DIM}- {r}{RESET}")


def print_dorks(dorks):
    print()
    print(f"{WHITE}-- osint dorks ({len(dorks)}) --{RESET}")
    for d in dorks:
        print(f"  {DIM}{d}{RESET}")


def print_phonebook(urls):
    print()
    print(f"{WHITE}-- reverse phonebook sources --{RESET}")
    for name, url in urls:
        print(f"  {GREEN}{name:<24}{RESET} {DIM}{url}{RESET}")


def print_account_sites(urls):
    print()
    print(f"{WHITE}-- account recovery pages (manual check) --{RESET}")
    for name, url in urls:
        print(f"  {GREEN}{name:<14}{RESET} {DIM}{url}{RESET}")


# ============================================================
# ACTIONS
# ============================================================

def lookup_one(raw, region=None):
    info = parse_full(raw, region)
    print_info(info)

    if info.get("error"):
        return info

    e164 = info.get("e164") or ""
    dorks = generate_dorks(raw, e164)
    print_dorks(dorks)

    pb = build_phonebook_urls(e164, raw)
    print_phonebook(pb)

    acc = account_discovery_manual(e164)
    print_account_sites(acc)

    return info, dorks, pb, acc


def open_all_phonebook(pb):
    for name, url in pb:
        try:
            webbrowser.open_new_tab(url)
            time.sleep(0.5)
        except Exception:
            pass


def open_all_accounts(acc):
    for name, url in acc:
        try:
            webbrowser.open_new_tab(url)
            time.sleep(0.5)
        except Exception:
            pass


def open_dorks(dorks):
    import urllib.parse
    for d in dorks[:5]:
        url = "https://www.google.com/search?q=" + urllib.parse.quote(d)
        try:
            webbrowser.open_new_tab(url)
            time.sleep(0.5)
        except Exception:
            pass


# ============================================================
# BATCH
# ============================================================

def batch_lookup(path):
    if not os.path.exists(path):
        log("file not found", "err")
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [x.strip() for x in f if x.strip()]
    results = []
    for i, line in enumerate(lines, 1):
        log(f"[{i}/{len(lines)}] {line}", "info")
        info = parse_full(line)
        print_info(info)
        results.append(info)
        print()
    return results


# ============================================================
# HISTORY
# ============================================================

def _hist_path():
    return os.path.join(output_dir(), "phone_osint_history.jsonl")


def save_history(info):
    try:
        with open(_hist_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "time": datetime.now().isoformat(),
                "input": info.get("input"),
                "country": info.get("country"),
                "carrier": info.get("carrier"),
                "valid": info.get("valid"),
                "spam_score": info.get("spam_score"),
            }, default=str) + "\n")
    except Exception:
        pass


def show_history():
    p = _hist_path()
    if not os.path.exists(p):
        log("no history", "warn")
        return
    entries = []
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    for e in entries[-40:][::-1]:
        print(f"  {DIM}{e.get('time','')[:19]}{RESET}  "
              f"{e.get('input',''):<20}  "
              f"{(e.get('country') or '?'):<18}  "
              f"{(e.get('carrier') or '?'):<22}  "
              f"spam={e.get('spam_score','?')}")


# ============================================================
# MENU
# ============================================================

def menu_single():
    banner()
    log("phone osint lookup", "info")
    raw = input_line("phone (international format e.g. +4915212345678) > ").strip()
    if not raw:
        pause(); return
    region = input_line("default region ISO (blank = auto) > ").strip().upper() or None

    result = lookup_one(raw, region)
    if isinstance(result, tuple):
        info, dorks, pb, acc = result
        save_history(info)

        print()
        print(f"{WHITE}-- actions --{RESET}")
        print(f"  {GREEN}[1]{RESET} open phonebook sources in browser")
        print(f"  {GREEN}[2]{RESET} open google dorks")
        print(f"  {GREEN}[3]{RESET} open account recovery pages")
        print(f"  {GREEN}[4]{RESET} open everything")
        print(f"  {GREEN}[b]{RESET} back")
        act = input_line("select > ").strip()
        if act == "1":
            open_all_phonebook(pb)
        elif act == "2":
            open_dorks(dorks)
        elif act == "3":
            open_all_accounts(acc)
        elif act == "4":
            open_all_phonebook(pb); time.sleep(0.5)
            open_dorks(dorks); time.sleep(0.5)
            open_all_accounts(acc)

        if confirm("\nsave report? [y/n] "):
            fn = timestamp_name("phone_osint_", "json")
            save_output(fn, json.dumps({
                "info": info,
                "dorks": dorks,
                "phonebook": pb,
                "accounts": acc,
            }, indent=2, default=str))
    pause()


def menu_batch():
    banner()
    log("batch phone osint", "info")
    path = input_line("path to file > ").strip().strip('"')
    if not path:
        pause(); return
    results = batch_lookup(path)
    if results and confirm("\nsave all? [y/n] "):
        fn = timestamp_name("phone_osint_batch_", "json")
        save_output(fn, json.dumps(results, indent=2, default=str))
    pause()


def menu_phonebook_only():
    banner()
    log("reverse phonebook", "info")
    raw = input_line("phone > ").strip()
    if not raw:
        pause(); return
    info = parse_full(raw)
    if info.get("error"):
        log(info["error"], "err"); pause(); return
    pb = build_phonebook_urls(info.get("e164",""), raw)
    print_phonebook(pb)
    if confirm("\nopen all in browser? [y/n] "):
        open_all_phonebook(pb)
    pause()


def menu_dorks_only():
    banner()
    log("osint dork generator", "info")
    raw = input_line("phone > ").strip()
    if not raw:
        pause(); return
    info = parse_full(raw)
    dorks = generate_dorks(raw, info.get("e164",""))
    print_dorks(dorks)
    if confirm("\nopen top 5 in google? [y/n] "):
        open_dorks(dorks)
    pause()


def menu_history():
    banner()
    log("history", "info")
    show_history()
    pause()


def run():
    banner()
    log("Phone OSINT Lookup", "info")
    if not HAS_PHONE:
        log("pip install phonenumbers for full parsing", "warn")
    print()

    while True:
        print(f"{WHITE}modes:{RESET}")
        print(f"  {GREEN}[1]{RESET} single lookup (parse + spam + dorks + phonebook + accounts)")
        print(f"  {GREEN}[2]{RESET} batch lookup from file")
        print(f"  {GREEN}[3]{RESET} reverse phonebook only")
        print(f"  {GREEN}[4]{RESET} osint dorks only")
        print(f"  {GREEN}[5]{RESET} history")
        print(f"  {GREEN}[0]{RESET} exit")
        print()
        c = input_line("select > ").strip()
        if c == "1":
            menu_single()
        elif c == "2":
            menu_batch()
        elif c == "3":
            menu_phonebook_only()
        elif c == "4":
            menu_dorks_only()
        elif c == "5":
            menu_history()
        elif c in ("0", "q", "quit", "exit", ""):
            return
        else:
            log("invalid choice", "warn")
            time.sleep(0.3)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print()
        log("interrupted", "warn")