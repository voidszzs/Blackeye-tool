# Stealer Log OSINT Tool
# ------------------------------------------------------------
# free, no-login, multi-source osint aggregator
#
# sources:
#   - hudson rock cavalier (free, no key)  -> stealer log search
#   - hibp pwned passwords (free, no key)  -> password breach check
#   - local username enumeration           -> variant generation
#
# modes:
#   1) full osint scan (email)
#   2) stealer log search only
#   3) password breach check (sha1 k-anonymity)
#   4) username enumeration
#   5) batch from file
#   6) history
#   7) export formats
#
# dependencies: pip install requests

from Config.Colors import *
from Config.Util import *

import os
import json
import time
import hashlib
import random
import string
import threading
import queue
from datetime import datetime
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None


# ============================================================
# CONSTANTS
# ============================================================

HUDSON_BASE = "https://cavalier.hudsonrock.com/api/json/v2/osint-tools"
HIBP_PWNED_BASE = "https://api.pwnedpasswords.com"

HEADERS = {
    "User-Agent": "stealer-osint/1.0",
    "Accept": "application/json",
}

# thread pool size
MAX_WORKERS = 8
REQUEST_TIMEOUT = 12


# ============================================================
# LOGGER
# ============================================================

class ReportLogger:
    """thread-safe jsonl logger for scan results"""
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def write(self, entry):
        with self.lock:
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
            except Exception:
                pass

    def read_all(self):
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return out


# ============================================================
# HUDSON ROCK CAVALIER (free, no key)
# ============================================================

def hudson_search_email(email):
    """free endpoint. returns list of result dicts or empty list."""
    try:
        r = requests.get(
            f"{HUDSON_BASE}/search-by-email",
            params={"email": email},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return _parse_hudson_response(data)
    except Exception:
        return []


def hudson_search_domain(domain):
    try:
        r = requests.get(
            f"{HUDSON_BASE}/search-by-domain",
            params={"domain": domain},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return _parse_hudson_response(data)
    except Exception:
        return []


def hudson_search_username(username):
    try:
        r = requests.get(
            f"{HUDSON_BASE}/search-by-username",
            params={"username": username},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return _parse_hudson_response(data)
    except Exception:
        return []


def hudson_search_ip(ip):
    try:
        r = requests.get(
            f"{HUDSON_BASE}/search-by-ip",
            params={"ip": ip},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return _parse_hudson_response(data)
    except Exception:
        return []


def _parse_hudson_response(data):
    """normalize hudson rock response into flat rows."""
    if not data or not isinstance(data, dict):
        return []
    rows = []
    payload = data.get("data") or data

    # employees + users
    for key in ("employees", "users"):
        for item in (payload.get(key) or []):
            rows.append({
                "source": "hudsonrock",
                "type": key[:-1],
                "email": item.get("email") or "",
                "username": item.get("username") or "",
                "password": item.get("password") or "",
                "computer": item.get("computer_name") or "",
                "os": item.get("operating_system") or "",
                "ip": item.get("ip") or "",
                "malware": item.get("malware_path") or "",
                "date": item.get("date_compromised") or "",
                "url": item.get("url") or "",
                "antiviruses": item.get("antiviruses") or [],
                "corporate_services": item.get("total_corporate_services") or 0,
                "user_services": item.get("total_user_services") or 0,
            })

    # stealer families stats
    stats = payload.get("stealerFamilies") or payload.get("stealers") or {}
    if stats:
        rows.append({
            "source": "hudsonrock",
            "type": "stats",
            "payload": stats,
        })

    return rows


# ============================================================
# HIBP PWNED PASSWORDS (free, no key, k-anonymity)
# ============================================================

def check_password_pwned(password):
    """
    free k-anonymity lookup. returns count of times password seen,
    or 0 if not found, or -1 on error.
    """
    if not password:
        return 0
    try:
        sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        r = requests.get(
            f"{HIBP_PWNED_BASE}/range/{prefix}",
            headers={"User-Agent": "stealer-osint-check"},
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return -1
        for line in r.text.splitlines():
            parts = line.split(":")
            if len(parts) == 2 and parts[0].strip() == suffix:
                return int(parts[1].strip())
        return 0
    except Exception:
        return -1


def check_password_batch(passwords, workers=MAX_WORKERS):
    """check multiple passwords. returns dict password -> count."""
    results = {}
    q = queue.Queue()
    for p in passwords:
        q.put(p)

    def worker():
        while True:
            try:
                p = q.get_nowait()
            except queue.Empty:
                return
            results[p] = check_password_pwned(p)
            q.task_done()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    q.join()
    return results


# ============================================================
# USERNAME VARIANT GENERATION
# ============================================================

LEET_MAP = {
    "a": ["4", "@"], "e": ["3"], "i": ["1", "!"], "o": ["0"],
    "s": ["5", "$"], "t": ["7"], "l": ["1"], "g": ["9"], "b": ["8"],
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


def _apply_leet(word, positions):
    choices = []
    for i, ch in enumerate(word):
        if i in positions and ch.lower() in LEET_MAP:
            choices.append([ch] + LEET_MAP[ch.lower()])
        else:
            choices.append([ch])
    import itertools
    return ["".join(t) for t in itertools.product(*choices)]


def generate_variants(base, limit=300):
    """generate username variants: leet, suffixes, prefixes, separators."""
    base = base.strip()
    if not base:
        return []
    seen = set()
    out = []

    def add(s):
        s = s.strip()
        if not s or s.lower() in seen:
            return
        if len(s) < 3 or len(s) > 40:
            return
        if not all(c.isalnum() or c in "._-" for c in s):
            return
        seen.add(s.lower())
        out.append(s)

    add(base)
    add(base.lower())
    add(base.upper())
    add(base.capitalize())

    for i in range(len(base)):
        for v in _apply_leet(base, {i}):
            add(v)

    for i in range(len(base) - 1):
        for v in _apply_leet(base, {i, i + 1}):
            add(v)

    for suf in COMMON_SUFFIXES:
        if suf:
            add(base + suf)
            add(base.lower() + suf)

    for pre in COMMON_PREFIXES:
        if pre:
            add(pre + base)
            add(pre + base.lower())

    if len(base) > 4:
        mid = len(base) // 2
        add(base[:mid] + "_" + base[mid:])
        add(base[:mid] + "." + base[mid:])
        add(base[:mid] + "-" + base[mid:])

    return out[:limit]


# ============================================================
# VAULT CROSS-REFERENCE
# ============================================================

def _vault_path():
    return os.path.join(output_dir(), "accounts.json")


def _load_vault():
    p = _vault_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    accounts = data.get("accounts") if isinstance(data, dict) else None
    if not isinstance(accounts, list):
        return []
    return [
        {
            "service": (a.get("service") or "").lower().strip(),
            "username": a.get("username") or "",
            "password": a.get("password") or "",
            "email": a.get("email") or "",
        }
        for a in accounts if isinstance(a, dict)
    ]


SERVICE_ALIASES = {
    "gmail": ["gmail.com", "googlemail.com", "google.com"],
    "outlook": ["outlook.com", "hotmail.com", "live.com", "microsoft.com"],
    "protonmail": ["proton.me", "protonmail.com"],
    "instagram": ["instagram.com"],
    "twitter": ["twitter.com", "x.com"],
    "tiktok": ["tiktok.com"],
    "facebook": ["facebook.com", "fb.com"],
    "discord": ["discord.com", "discordapp.com"],
    "steam": ["steampowered.com", "steamcommunity.com"],
    "roblox": ["roblox.com"],
    "spotify": ["spotify.com"],
    "github": ["github.com"],
    "netflix": ["netflix.com"],
    "amazon": ["amazon.com"],
    "paypal": ["paypal.com"],
}


def _match_vault(row, vault):
    if not vault:
        return []
    blob = " ".join(str(row.get(k, "")).lower() for k in ("url", "domain", "email", "username"))
    if not blob:
        return []
    out = []
    for v in vault:
        svc = v["service"]
        if not svc:
            continue
        if svc in blob:
            out.append(v)
            continue
        for alias in SERVICE_ALIASES.get(svc, []):
            if alias in blob:
                out.append(v)
                break
    seen, deduped = set(), []
    for m in out:
        k = (m["service"], m["username"])
        if k not in seen:
            seen.add(k)
            deduped.append(m)
    return deduped


# ============================================================
# FULL OSINT SCAN
# ============================================================

def full_scan_email(email):
    """
    run all modules against an email.
    returns dict with hudsonrock, pwned, vault_matches.
    """
    print()
    print(f"{WHITE}── full osint scan: {email} ──{RESET}")

    result = {
        "target": email,
        "time": datetime.now().isoformat(),
        "hudsonrock": [],
        "pwned": {},
        "vault_matches": [],
    }

    # --- hudson rock ---
    log("hudson rock cavalier ...", "info")
    rows = hudson_search_email(email)
    result["hudsonrock"] = rows
    _print_hudson_rows(rows)

    # --- extract passwords from hudson results ---
    passwords = set()
    for r in rows:
        if r.get("password"):
            passwords.add(r["password"])
    if email and "@" in email:
        # also check the email local part as a password guess
        passwords.add(email.split("@")[0])

    # --- pwned passwords ---
    if passwords:
        log(f"checking {len(passwords)} password(s) against pwned db ...", "info")
        pwned = check_password_batch(list(passwords))
        result["pwned"] = {k: v for k, v in pwned.items() if v > 0}
        if result["pwned"]:
            print()
            print(f"{WHITE}── pwned passwords ──{RESET}")
            for pw, count in sorted(result["pwned"].items(), key=lambda x: -x[1]):
                print(f"  {RED}{count:>8}{RESET}  {DIM}{pw[:40]}{RESET}")
        else:
            log("no pwned passwords found", "info")

    # --- vault cross-reference ---
    vault = _load_vault()
    if vault:
        all_matches = []
        for r in rows:
            matches = _match_vault(r, vault)
            if matches:
                all_matches.extend(matches)
        if all_matches:
            print()
            print(f"{MAGENTA}── your vault matches ──{RESET}")
            for m in all_matches:
                print(f"  {MAGENTA}{m['service']:<14}{RESET} "
                      f"{m['username']:<26} {YELLOW}{m['password']}{RESET}")
            result["vault_matches"] = all_matches

    return result


def _print_hudson_rows(rows):
    if not rows:
        log("no hits from hudson rock", "info")
        return
    real = [r for r in rows if r["type"] in ("employee", "user")]
    if not real:
        return
    print()
    print(f"{WHITE}── hudson rock: {len(real)} hit(s) ──{RESET}")
    for r in real:
        print(f"  {GREEN}[{r['type']}]{RESET} "
              f"{r.get('email') or r.get('username') or '?'}  "
              f"{DIM}{r.get('ip','')} {r.get('os','')} "
              f"{r.get('malware','')} {r.get('date','')}{RESET}")


def full_scan_domain(domain):
    print()
    print(f"{WHITE}── full osint scan: {domain} ──{RESET}")
    result = {
        "target": domain,
        "time": datetime.now().isoformat(),
        "hudsonrock": [],
    }
    log("hudson rock cavalier ...", "info")
    rows = hudson_search_domain(domain)
    result["hudsonrock"] = rows
    _print_hudson_rows(rows)
    return result


# ============================================================
# MENU FUNCTIONS
# ============================================================

def menu_full_scan():
    banner()
    log("full osint scan", "info")
    target = input_line("email or domain > ").strip()
    if not target:
        pause(); return

    if "@" in target:
        result = full_scan_email(target)
    else:
        result = full_scan_domain(target)

    if confirm("\nsave report? [y/n] "):
        fn = timestamp_name(f"osint_scan_{target.replace('@','_at_').replace('.','_')}_", "json")
        save_output(fn, json.dumps(result, indent=2, default=str))
    pause()


def menu_stealer_only():
    banner()
    log("stealer log search", "info")
    print(f"  {GREEN}[1]{RESET} email")
    print(f"  {GREEN}[2]{RESET} domain")
    print(f"  {GREEN}[3]{RESET} username")
    print(f"  {GREEN}[4]{RESET} ip")
    choice = input_line("select > ").strip()

    target = input_line("target > ").strip()
    if not target:
        pause(); return

    log("hudson rock cavalier ...", "info")
    if choice == "1":
        rows = hudson_search_email(target)
    elif choice == "2":
        rows = hudson_search_domain(target)
    elif choice == "3":
        rows = hudson_search_username(target)
    else:
        rows = hudson_search_ip(target)

    _print_hudson_rows(rows)
    if confirm("\nsave? [y/n] "):
        fn = timestamp_name(f"stealer_{target.replace('@','_at_').replace('.','_')}_", "json")
        save_output(fn, json.dumps(rows, indent=2, default=str))
    pause()


def menu_pwned_password():
    banner()
    log("pwned password check (hibp k-anonymity)", "info")
    pw = input_line("password to check > ").strip()
    if not pw:
        pause(); return
    count = check_password_pwned(pw)
    if count < 0:
        log("lookup failed (network)", "err")
    elif count == 0:
        log("not found in pwned db", "ok")
    else:
        log(f"FOUND {count} time(s) in breaches!", "warn")
    pause()


def menu_username_variants():
    banner()
    log("username variant generator", "info")
    base = input_line("base username > ").strip()
    if not base:
        pause(); return
    limit_str = input_line("max variants [300] > ").strip()
    limit = int(limit_str) if limit_str.isdigit() else 300
    variants = generate_variants(base, limit=limit)
    print()
    for i, v in enumerate(variants, 1):
        print(f"  {GREEN}[{i:>3}]{RESET} {v}")
    log(f"{len(variants)} variants generated", "ok")
    if confirm("\nsave? [y/n] "):
        save_output(timestamp_name(f"variants_{base}_", "txt"), "\n".join(variants))
    pause()


def menu_batch():
    banner()
    log("batch scan", "info")
    path = input_line("path to file (one email/domain per line) > ").strip().strip('"')
    if not os.path.exists(path):
        log("file not found", "err"); pause(); return

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [x.strip() for x in f if x.strip()]

    log(f"{len(lines)} targets", "info")
    for i, line in enumerate(lines, 1):
        log(f"[{i}/{len(lines)}] {line}", "info")
        try:
            if "@" in line:
                full_scan_email(line)
            else:
                full_scan_domain(line)
        except Exception as e:
            log(f"error: {e}", "warn")
        time.sleep(0.8)
    pause()


def menu_history():
    banner()
    log("scan history", "info")
    od = output_dir()
    files = sorted(
        [f for f in os.listdir(od)
         if f.startswith("osint_scan_") or f.startswith("stealer_")],
        reverse=True
    )[:20]
    if not files:
        log("no history", "warn"); pause(); return
    for i, f in enumerate(files, 1):
        size = os.path.getsize(os.path.join(od, f))
        print(f"  {GREEN}[{i:>2}]{RESET} {f:<50} {size} bytes")
    sel = input_line("open # (blank cancel) > ").strip()
    if sel.isdigit() and 1 <= int(sel) <= len(files):
        path = os.path.join(od, files[int(sel)-1])
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        print()
        print(content[:3000])
        if len(content) > 3000:
            print(f"\n{DIM}... ({len(content)-3000} more bytes){RESET}")
    pause()


# ============================================================
# MAIN
# ============================================================

def run():
    banner()
    log("Stealer Log OSINT Tool", "info")
    print(f"{DIM}sources: hudson rock cavalier (free) + hibp pwned (free){RESET}")
    print()

    if requests is None:
        log("pip install requests", "err"); pause(); return

    while True:
        print(f"{WHITE}modes:{RESET}")
        print(f"  {GREEN}[1]{RESET} full osint scan (email / domain)")
        print(f"  {GREEN}[2]{RESET} stealer log search only")
        print(f"  {GREEN}[3]{RESET} pwned password check")
        print(f"  {GREEN}[4]{RESET} username variant generator")
        print(f"  {GREEN}[5]{RESET} batch scan from file")
        print(f"  {GREEN}[6]{RESET} history")
        print(f"  {GREEN}[0]{RESET} exit")
        print()
        choice = input_line("select > ").strip()

        if choice == "1":
            menu_full_scan()
        elif choice == "2":
            menu_stealer_only()
        elif choice == "3":
            menu_pwned_password()
        elif choice == "4":
            menu_username_variants()
        elif choice == "5":
            menu_batch()
        elif choice == "6":
            menu_history()
        elif choice in ("0", "q", "quit", "exit", ""):
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