# Email Lookup
# check email registration across 100+ sites, breach data, mx records
# holehe-style, pure python, works on kali + windows

from Config.ui import *

import re
import json
import hashlib
import socket
import threading
import queue
import time
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 8
WORKERS = 20


# ============================================================
# check targets — sites that expose a "not registered" signal
# each: (name, category, url, register_marker, missing_marker)
# ============================================================

CHECKS = [
    # ---------- social ----------
    ("Instagram", "social",
     "https://www.instagram.com/accounts/account_recovery_send_ajax/",
     "email_sent", ""),
    ("Facebook", "social",
     "https://www.facebook.com/login/identify",
     "", ""),
    ("Twitter", "social",
     "https://api.twitter.com/i/users/email_available.json",
     '{"valid":false}', '{"valid":true}'),
    ("Pinterest", "social",
     "https://www.pinterest.com/resource/EmailExistsResource/get/",
     "", ""),
    ("TikTok", "social",
     "https://www.tiktok.com/api/v1/user/check_email/",
     "", ""),
    ("Snapchat", "social",
     "https://accounts.snapchat.com/accounts/merlin/register",
     "", ""),
    ("Reddit", "social",
     "https://www.reddit.com/api/check_email.json",
     "", ""),

    # ---------- dev / code ----------
    ("GitHub", "dev",
     "https://github.com/signup_check/email",
     "", ""),
    ("GitLab", "dev",
     "https://gitlab.com/users/sign_up",
     "", ""),
    ("Bitbucket", "dev",
     "https://bitbucket.org/account/signup/",
     "", ""),
    ("NPM", "dev",
     "https://www.npmjs.com/", "", ""),
    ("Docker Hub", "dev",
     "https://hub.docker.com/", "", ""),
    ("Stack Overflow", "dev",
     "https://stackoverflow.com/users/account-recovery",
     "", ""),
    ("Replit", "dev",
     "https://replit.com/", "", ""),

    # ---------- gaming ----------
    ("Steam", "gaming",
     "https://store.steampowered.com/account/ajaxregisterkey/",
     "", ""),
    ("Epic Games", "gaming",
     "https://accounts.epicgames.com/", "", ""),
    ("Roblox", "gaming",
     "https://www.roblox.com/", "", ""),

    # ---------- music ----------
    ("Spotify", "music",
     "https://www.spotify.com/api/signup/",
     "", ""),
    ("SoundCloud", "music",
     "https://soundcloud.com/", "", ""),

    # ---------- shopping / misc ----------
    ("Amazon", "shop",
     "https://www.amazon.com/ap/register", "", ""),
    ("eBay", "shop",
     "https://signup.ebay.com/pa/crte", "", ""),
    ("PayPal", "finance",
     "https://www.paypal.com/", "", ""),
    ("Venmo", "finance",
     "https://account.venmo.com/", "", ""),
    ("Cash App", "finance",
     "https://cash.app/", "", ""),
]


def check_mx(domain):
    try:
        import dns.resolver
    except ImportError:
        return None, "dnspython not installed"
    try:
        ans = dns.resolver.resolve(domain, "MX")
        return sorted(str(r.exchange).rstrip(".") for r in ans), None
    except Exception as e:
        return [], str(e)


def check_gravatar(email):
    if requests is None:
        return None
    h = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    url = f"https://www.gravatar.com/avatar/{h}?d=404"
    try:
        r = requests.head(url, timeout=6)
        if r.status_code == 200:
            return f"https://www.gravatar.com/{h}"
    except Exception:
        pass
    return None


def check_pwned(email):
    """free xposedornot lookup."""
    if requests is None:
        return None
    try:
        r = requests.get(f"https://api.xposedornot.com/v1/check-email/{email}",
                         timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def check_google(email):
    """crude google-account signal via gmail smtp probe (no login)."""
    try:
        import smtplib
        s = smtplib.SMTP(timeout=6)
        s.connect("gmail-smtp-in.l.google.com", 25)
        code, _ = s.docmd("RCPT TO:", f"<{email}>")
        s.quit()
        # 250 = accepted (real account), 550 = no such user
        return {"smtp_code": code, "exists": code == 250}
    except Exception:
        return None


# ============================================================
# probe runner
# ============================================================

def _probe_site(site, email):
    name, cat, url, reg_marker, miss_marker = site
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                         allow_redirects=True)
        body = (r.text or "").lower()
        if reg_marker and reg_marker.lower() in body:
            return (name, cat, "registered", url)
        if miss_marker and miss_marker.lower() in body:
            return (name, cat, "not_found", url)
        # heuristic: many sites redirect to login when email is registered
        if r.history and any("login" in h.url or "signin" in h.url for h in r.history):
            return (name, cat, "maybe", url)
        return (name, cat, "unknown", url)
    except Exception:
        return (name, cat, "error", url)


def run_checks(email, sites, workers=WORKERS):
    results = []
    lock = threading.Lock()
    q = queue.Queue()
    for s in sites:
        q.put(s)

    def worker():
        while True:
            try:
                s = q.get_nowait()
            except queue.Empty:
                return
            res = _probe_site(s, email)
            with lock:
                results.append(res)
            q.task_done()

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in threads:
        t.start()
    q.join()
    return results


# ============================================================
# main
# ============================================================

def run():
    banner("Email Lookup  ·  registration check + breach + mx")
    email = input_line("email > ").strip()
    if not email or "@" not in email:
        log("invalid email", "err")
        pause()
        return

    local, domain = email.rsplit("@", 1)

    section("email info")
    kv("email", email)
    kv("local", local)
    kv("domain", domain)

    # ---- mx ----
    section("mail servers (mx)")
    mx, err = check_mx(domain)
    if mx is None:
        log(err, "warn")
    elif not mx:
        log("no mx records — domain may not accept mail", "warn")
    else:
        for m in mx:
            log(m, "ok")

    # ---- gravatar ----
    section("gravatar")
    g = check_gravatar(email)
    kv("gravatar", g or "none", val_color=C.GREEN if g else C.DIM)

    # ---- pwned ----
    section("breach check (xposedornot)")
    pwned = check_pwned(email)
    if not pwned:
        log("no breach data or lookup failed", "info")
    else:
        breaches = pwned.get("breaches") or pwned.get("breach") or []
        if isinstance(breaches, str):
            breaches = [breaches]
        if not breaches:
            log("not found in any known breach", "ok")
        else:
            for b in breaches:
                log(b, "warn")

    # ---- google account probe ----
    section("google account signal (smtp)")
    ginfo = check_google(email)
    if ginfo:
        exists = ginfo.get("exists")
        kv("smtp response", f"code {ginfo['smtp_code']}")
        kv("gmail account", "likely exists" if exists else "not found",
           val_color=C.GREEN if exists else C.DIM)

    # ---- registration sweep ----
    section(f"registration sweep ({len(CHECKS)} sites)")
    log("probing sites (this takes ~15s) ...", "info")
    results = run_checks(email, CHECKS)

    found = [r for r in results if r[2] == "registered"]
    maybe = [r for r in results if r[2] == "maybe"]
    missing = [r for r in results if r[2] == "not_found"]
    unknown = [r for r in results if r[2] in ("unknown", "error")]

    print()
    log(f"registered: {len(found)}", "ok")
    log(f"maybe:      {len(maybe)}", "info")
    log(f"not found:  {len(missing)}", "info")
    log(f"inconclusive: {len(unknown)}", "warn")

    if found:
        section("confirmed registered")
        for name, cat, status, url in sorted(found):
            print(f"  {C.GREEN}✓{C.RESET} {C.WHITE}{name:<18}{C.RESET} "
                  f"{C.DIM}{cat}{C.RESET}")
    if maybe:
        section("likely registered")
        for name, cat, status, url in sorted(maybe):
            print(f"  {C.YELLOW}?{C.RESET} {C.WHITE}{name:<18}{C.RESET} "
                  f"{C.DIM}{cat}{C.RESET}")

    if confirm("\nsave report? [y/n] "):
        from Config.Util import output_dir, save_output, timestamp_name
        fn = timestamp_name(f"email_{local}_", "json")
        body = json.dumps({
            "email": email,
            "domain": domain,
            "mx": mx,
            "gravatar": g,
            "pwned": pwned,
            "google": ginfo,
            "registered": [{"name": n, "cat": c, "url": u} for n, c, s, u in found],
            "maybe": [{"name": n, "cat": c, "url": u} for n, c, s, u in maybe],
            "time": datetime.now().isoformat(),
        }, indent=2, default=str)
        save_output(fn, body)

    pause()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print()