#!/usr/bin/env python3
# ============================================================
# Blackeye Multi-Tool - hierarchical launcher
#
#   main menu  -> pick a category
#   cat menu   -> pick a tool
#   tool       -> runs
#
# keys:
#   number     -> select
#   b          -> back (from tool list to main menu)
#   s          -> search across every category
#   i          -> info
#   q          -> quit
# ============================================================

import os
import sys
import json
import time
import importlib.util

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from Config.Colors import *
from Config.Util import *
from Config import Settings as S

MANIFEST_FILE = os.path.join(BASE, "Config", "menu.json")
CATS_FILE     = os.path.join(BASE, "Config", "categories.json")
META_FILE     = os.path.join(BASE, "Config", "meta.json")


# ---------- io ----------

def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def short(s, n=44):
    s = (s or "").replace("-", " ")
    if len(s) > n:
        s = s[:n - 1] + "…"
    return s


# ---------- tool runner ----------

def run_tool(rel_path):
    full = os.path.join(BASE, rel_path.replace("/", os.sep))
    if not os.path.exists(full):
        log(f"tool not found: {rel_path}", "err")
        return
    log(f"launching {rel_path}", "info")
    try:
        spec = importlib.util.spec_from_file_location("blackeye_tool", full)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["blackeye_tool"] = mod
        spec.loader.exec_module(mod)
        if hasattr(mod, "run"):
            mod.run()
        else:
            log("tool has no run() entry point", "warn")
    except KeyboardInterrupt:
        log("interrupted", "warn")
    except Exception as e:
        log(f"tool crashed: {e}", "err")
        if S.VERBOSE:
            import traceback
            traceback.print_exc()


# ---------- main menu ----------

def draw_main_menu(cat_order, cat_meta, manifest, meta):
    clear()
    banner()
    print(f"{DIM} version {meta.get('version', '?')} | "
          f"{meta.get('tool_count', 0)} tools | "
          f"{len(cat_order)} categories{RESET}")
    print()

    width = 60
    print(f"  {RED}┌" + "─" * (width - 4) + f"┐{RESET}")
    print(f"  {RED}│{RESET}  {WHITE}MAIN MENU{RESET}"
          + " " * (width - 16) + f"{RED}│{RESET}")
    print(f"  {RED}├" + "─" * (width - 4) + f"┤{RESET}")

    for i, cat in enumerate(cat_order, 1):
        label, desc = cat_meta.get(cat, (cat, ""))
        count = len(manifest.get(cat, []))
        key = f"{i:02d}"
        line = (
            f"  {RED}│{RESET}  {GREEN}[{key}]{RESET} "
            f"{WHITE}{label:<16}{RESET} "
            f"{DIM}{short(desc, 22):<22}{RESET} "
            f"{YELLOW}({count:>3}){RESET} "
            f"{RED}│{RESET}"
        )
        # pad to width (crude but works because of ANSI)
        visible = (
            f"  │  [{key}] "
            f"{label:<16} "
            f"{short(desc, 22):<22} "
            f"({count:>3}) │"
        )
        pad = width - len(visible)
        print(line + (" " * max(0, pad)) if pad > 0 else line)

    print(f"  {RED}└" + "─" * (width - 4) + f"┘{RESET}")
    print()
    print(f"  {RED}[{WHITE}##{RED}]{WHITE} open category   "
          f"{RED}[{WHITE}S{RED}]{WHITE} search   "
          f"{RED}[{WHITE}I{RED}]{WHITE} info   "
          f"{RED}[{WHITE}Q{RED}]{WHITE} quit")
    print()


# ---------- category view ----------

def draw_category(cat, tools):
    clear()
    banner()
    label, desc = (cat, "")
    print(f"{DIM} category: {cat} | {len(tools)} tools{RESET}")
    print()
    print(f"  {RED}┌─ {WHITE}{cat.upper()} {RED}"
          + "─" * max(2, 50 - len(cat)) + f"{RESET}")

    index_map = {}
    for i, t in enumerate(tools, 1):
        key = f"{i:03d}"
        index_map[key] = t["file"]
        index_map[str(i)] = t["file"]
        name = short(t["name"], 34)
        d = short(t.get("desc", ""), 30)
        print(f"  {RED}│{RESET} {GREEN}[{i:>3}]{RESET} "
              f"{WHITE}{name:<34}{RESET} {DIM}{d}{RESET}")
    print(f"  {RED}└" + "─" * 54 + f"{RESET}")
    print()
    print(f"  {RED}[{WHITE}#{RED}]{WHITE} select tool   "
          f"{RED}[{WHITE}B{RED}]{WHITE} back to main menu")
    print()
    return index_map


def category_loop(cat, manifest):
    tools = manifest.get(cat, [])
    if not tools:
        log("empty category", "warn")
        pause()
        return
    while True:
        index_map = draw_category(cat, tools)
        choice = input_line("select > ").strip().lower()
        if choice in ("b", "back", "q", "quit", ""):
            return
        if choice in index_map:
            run_tool(index_map[choice])
            pause()
            continue
        if choice.isdigit():
            key = f"{int(choice):03d}"
            if key in index_map:
                run_tool(index_map[key])
                pause()
                continue
        log("invalid choice", "warn")
        time.sleep(0.4)


# ---------- search ----------

def do_search(manifest):
    clear()
    banner()
    term = input_line("search query > ").strip().lower()
    if not term:
        return
    hits = []
    for cat, tools in manifest.items():
        for t in tools:
            if (term in t["name"].lower()
                    or term in (t.get("desc") or "").lower()
                    or term in cat.lower()):
                hits.append((cat, t))
    print()
    if not hits:
        log("no matches", "warn")
        pause()
        return
    for i, (cat, t) in enumerate(hits, 1):
        print(f"  {RED}[{WHITE}{i:>3}{RED}]{WHITE} "
              f"{CYAN}{cat:<14}{RESET} {t['name']} "
              f"{DIM}{t.get('desc','')}{RESET}")
    print()
    sel = input_line("select (or blank to cancel) > ").strip()
    if sel.isdigit():
        i = int(sel) - 1
        if 0 <= i < len(hits):
            run_tool(hits[i][1]["file"])
        pause()


# ---------- info ----------

def do_info(meta):
    clear()
    banner()
    print(f"  {WHITE}Blackeye Multi-Tool{RESET}")
    print(f"  version    : {meta.get('version', '?')}")
    print(f"  built      : {meta.get('built', '?')}")
    print(f"  author     : {meta.get('author', '?')}")
    print(f"  tools      : {meta.get('tool_count', 0)}")
    print(f"  categories : {', '.join(meta.get('categories', []))}")
    print()
    print(f"  {DIM}Educational / self-testing use only.{RESET}")
    print()
    pause()


# ---------- main ----------

def main():
    manifest = load_json(MANIFEST_FILE, {})
    cats_data = load_json(CATS_FILE, {})
    meta = load_json(META_FILE, {})

    cat_order = cats_data.get("order") or list(manifest.keys())
    cat_meta = cats_data.get("meta") or {}

    if not manifest or not cat_order:
        log("missing config. run the builder first.", "err")
        return

    cat_index = {}
    while True:
        cat_index = {}
        draw_main_menu(cat_order, cat_meta, manifest, meta)
        for i, cat in enumerate(cat_order, 1):
            cat_index[str(i)] = cat
            cat_index[f"{i:02d}"] = cat

        choice = input_line("select > ").strip().lower()

        if choice in ("q", "quit", "exit", "0"):
            log("bye.", "ok")
            break
        if choice in ("s", "search", "/"):
            do_search(manifest)
            continue
        if choice in ("i", "info"):
            do_info(meta)
            continue
        if choice in cat_index:
            category_loop(cat_index[choice], manifest)
            continue

        log("invalid choice", "warn")
        time.sleep(0.4)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        log("interrupted", "warn")
