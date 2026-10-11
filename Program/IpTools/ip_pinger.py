# IP Pinger
# cross-platform ping

from Config.Colors import *
from Config.Util import *

import subprocess
import platform
import re


def ping_once(host, count=4, timeout=4):
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout), host]

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout * count + 5)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return 1, "timed out"
    except FileNotFoundError:
        return 1, "ping binary not found"
    except Exception as e:
        return 1, str(e)


def parse_times(output):
    # grab ms= values (win) or time= values (nix)
    hits = re.findall(r"(?:time[=<])\s*([\d.]+)\s*ms", output)
    try:
        return [float(x) for x in hits]
    except Exception:
        return []


def run():
    banner()
    log("IP Pinger", "info")

    host = input_line("host or ip > ").strip()
    if not host:
        pause(); return

    cnt = input_line("count [4] > ").strip()
    try:
        count = int(cnt) if cnt else 4
    except ValueError:
        count = 4

    print()
    rc, out = ping_once(host, count)
    print(out)

    times = parse_times(out)
    if times:
        avg = sum(times) / len(times)
        print(f"{GREEN}avg rtt: {avg:.1f} ms{RESET}  "
              f"min: {min(times):.1f}  max: {max(times):.1f}  "
              f"loss: {(count - len(times)) / count * 100:.0f}%")
    else:
        print(f"{YELLOW}no timing info parsed — host may be unreachable{RESET}")

    if confirm("\nsave output? [y/n] "):
        save_output(timestamp_name(f"ping_{host.replace('.','_')}_", "txt"), out)
    pause()