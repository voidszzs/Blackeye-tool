# Shared utilities
import os
import sys
import socket
from datetime import datetime
from Config.Colors import *
from Config import Settings as S

# ---------- terminal ----------

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print(f"{RED}")
    print("  ██████╗ ██╗      █████╗  ██████╗██╗  ██╗███████╗██╗   ██╗███████╗")
    print("  ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝██╔════╝╚██╗ ██╔╝██╔════╝")
    print("  ██████╔╝██║     ███████║██║     █████╔╝ █████╗   ╚████╔╝ █████╗  ")
    print("  ██╔══██╗██║     ██╔══██║██║     ██╔═██╗ ██╔══╝    ╚██╔╝  ██╔══╝  ")
    print("  ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗███████╗   ██║   ███████╗")
    print("  ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝")
    print(f"{RESET}{WHITE}  Blackeye Multi-Tool v{S.VERSION}{RESET}")
    print(f"{DIM}  Multi-Tool / Educational purpose only{RESET}\n")


def log(msg, level="info"):
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "info": f"{BLUE}[*]{RESET}",
        "ok": f"{GREEN}[+]{RESET}",
        "warn": f"{YELLOW}[!]{RESET}",
        "err": f"{RED}[-]{RESET}",
        "ask": f"{MAGENTA}[?]{RESET}",
    }.get(level, f"{WHITE}[?]{RESET}")
    if S.SHOW_TIMESTAMPS:
        print(f"{WHITE}[{ts}]{RESET} {prefix} {msg}")
    else:
        print(f"{prefix} {msg}")


def input_line(prompt="> "):
    try:
        return input(f"{GREEN}{prompt}{RESET}")
    except (KeyboardInterrupt, EOFError):
        print()
        return ""


def pause():
    try:
        input(f"\n{WHITE}press enter to continue...{RESET}")
    except (KeyboardInterrupt, EOFError):
        print()


def confirm(prompt="continue? [y/n] "):
    r = input_line(prompt).strip().lower()
    return r in ("y", "yes", "j", "ja")

# ---------- paths ----------

def base_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_path(*parts):
    return os.path.join(base_dir(), *parts)


def output_dir():
    p = resolve_path(S.OUTPUT_DIR)
    os.makedirs(p, exist_ok=True)
    return p


def wordlist_dir():
    p = resolve_path(S.WORDLIST_DIR)
    os.makedirs(p, exist_ok=True)
    return p


def template_dir():
    p = resolve_path(S.TEMPLATE_DIR)
    os.makedirs(p, exist_ok=True)
    return p

# ---------- output ----------

def timestamp_name(prefix, ext="txt"):
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"


def save_output(filename, data, binary=False):
    p = os.path.join(output_dir(), filename)
    mode = "wb" if binary else "w"
    kwargs = {} if binary else {"encoding": "utf-8", "errors": "ignore"}
    with open(p, mode, **kwargs) as f:
        f.write(data)
    log(f"saved -> {p}", "ok")
    return p

# ---------- http ----------

def http_get(url, headers=None, timeout=None, **kwargs):
    import requests
    h = {"User-Agent": S.USER_AGENT}
    if headers:
        h.update(headers)
    return requests.get(url, headers=h, timeout=timeout or S.DEFAULT_TIMEOUT, **kwargs)


def http_post(url, headers=None, timeout=None, **kwargs):
    import requests
    h = {"User-Agent": S.USER_AGENT}
    if headers:
        h.update(headers)
    return requests.post(url, headers=h, timeout=timeout or S.DEFAULT_TIMEOUT, **kwargs)


def resolve_host(host):
    try:
        return socket.gethostbyname(host)
    except Exception:
        return None

# ---------- threading ----------

def thread_pool(items, func, workers=None):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    workers = workers or S.MAX_THREADS
    results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(func, i): i for i in items}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                log(f"thread error: {e}", "warn")
    return results

# ---------- misc ----------

def split_list(text, sep=","):
    return [x.strip() for x in text.split(sep) if x.strip()]


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def die(msg="exiting"):
    log(msg, "err")
    sys.exit(1)
