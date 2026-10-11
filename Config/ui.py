# Config/ui.py
# shared ui helpers — clean, consistent across every tool
# works on windows (cmd / powershell / wt) and *nix (bash / zsh)

import os
import sys
import shutil

# ============================================================
# colors (no external dep — plain ansi)
# ============================================================

class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"

    # bright aliases
    OK      = GREEN
    WARN    = YELLOW
    ERR     = RED
    INFO    = BLUE
    ACCENT  = CYAN
    MAIN    = RED


# enable ansi on windows 10+ terminals automatically
if os.name == "nt":
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)
    except Exception:
        pass


# ============================================================
# terminal primitives
# ============================================================

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def term_width(default=72):
    try:
        w = shutil.get_terminal_size((default, 24)).columns
        return min(w, 100)
    except Exception:
        return default


def rule(char="─", color=None):
    color = color or C.DIM
    print(f"{color}{char * term_width()}{C.RESET}")


def title(text, color=None):
    color = color or C.WHITE
    w = term_width()
    pad = max(0, (w - len(text) - 2) // 2)
    print(f"\n{color}{' ' * pad}{C.BOLD}{text}{C.RESET}\n")


def section(text, color=None):
    color = color or C.CYAN
    print(f"\n{color}{C.BOLD}▸ {text}{C.RESET}")


def kv(key, value, key_color=None, val_color=None, width=18):
    key_color = key_color or C.CYAN
    val_color = val_color or C.WHITE
    print(f"  {key_color}{key:<{width}}{C.RESET} {val_color}{value}{C.RESET}")


def log(msg, level="info"):
    icons = {
        "info":  (f"{C.BLUE}[*]{C.RESET}",  msg),
        "ok":    (f"{C.GREEN}[+]{C.RESET}", msg),
        "warn":  (f"{C.YELLOW}[!]{C.RESET}",msg),
        "err":   (f"{C.RED}[-]{C.RESET}",   msg),
        "ask":   (f"{C.MAGENTA}[?]{C.RESET}",msg),
    }
    prefix, text = icons.get(level, (f"{C.WHITE}[?]{C.RESET}", msg))
    print(f"{prefix} {text}")


def input_line(prompt="> ", color=None):
    color = color or C.GREEN
    try:
        return input(f"{color}{prompt}{C.RESET}")
    except (KeyboardInterrupt, EOFError):
        print()
        return ""


def pause(text="press enter to continue..."):
    try:
        input(f"\n{C.DIM}{text}{C.RESET}")
    except (KeyboardInterrupt, EOFError):
        print()


def confirm(prompt="continue? [y/n] "):
    r = input_line(prompt).strip().lower()
    return r in ("y", "yes", "j", "ja", "")


# ============================================================
# menu helpers — the clean way
# ============================================================

def menu(title_text, options, subtitle=None, back=True, extra_help=None):
    """
    options: list of (label, value) tuples, or list of strings
    returns the value of the chosen option, or None for back/exit

    example:
        choice = menu("OSINT", [
            ("email lookup",   "email"),
            ("username search","user"),
            ("phone lookup",   "phone"),
        ])
        if choice == "email": ...
    """
    clear()
    banner()
    title(title_text)
    if subtitle:
        print(f"  {C.DIM}{subtitle}{C.RESET}\n")

    values = []
    for i, opt in enumerate(options, 1):
        if isinstance(opt, tuple):
            label, val = opt[0], opt[1]
            desc = opt[2] if len(opt) > 2 else ""
        else:
            label, val, desc = opt, opt, ""
            values.append(val)

        key = f"[{i:>2}]"
        line = f"  {C.GREEN}{key}{C.RESET} {C.WHITE}{label}{C.RESET}"
        if desc:
            line += f"  {C.DIM}{desc}{C.RESET}"
        print(line)
        values.append(val)

    print()
    if back:
        print(f"  {C.RED}[ 0]{C.RESET} back")
    if extra_help:
        print(f"  {C.DIM}{extra_help}{C.RESET}")

    raw = input_line("select > ").strip()
    if raw in ("0", "", "b", "back", "q", "quit"):
        return None
    try:
        idx = int(raw) - 1
    except ValueError:
        return None
    if 0 <= idx < len(values):
        return values[idx]
    return None


# ============================================================
# banner
# ============================================================

_BANNER = r"""
   ██████╗ ██╗      █████╗  ██████╗██╗  ██╗███████╗██╗   ██╗███████╗
   ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝██╔════╝╚██╗ ██╔╝██╔════╝
   ██████╔╝██║     ███████║██║     █████╔╝ █████╗   ╚████╔╝ █████╗
   ██╔══██╗██║     ██╔══██║██║     ██╔═██╗ ██╔══╝    ╚██╔╝  ██╔══╝
   ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗███████╗   ██║   ███████╗
   ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝
"""

_BANNER_ASCII = r"""
   +-------------------------------------------------+
   |   B L A C K E Y E   M U L T I - T O O L         |
   +-------------------------------------------------+
"""


def banner(subtitle=None):
    # prefer unicode, fall back to ascii on old windows consoles
    if os.name == "nt":
        try:
            print(_BANNER)
        except UnicodeEncodeError:
            print(_BANNER_ASCII)
    else:
        print(_BANNER)
    if subtitle:
        print(f"   {C.DIM}{subtitle}{C.RESET}")
    print(f"   {C.DIM}Multi-tools / self-testing only{C.RESET}\n")


def header(tool_name, category=None):
    banner()
    t = f"{tool_name}"
    if category:
        t += f"  {C.DIM}·  {category}{C.RESET}"
    title(t, C.MAIN)