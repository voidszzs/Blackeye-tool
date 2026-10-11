# IP Port Scanner
# common / full / range port scan

from Config.Colors import *
from Config.Util import *

import socket
import threading

TOP_PORTS = [
    21, 22, 23, 25, 53, 67, 68, 69, 80, 110, 111, 119, 123, 135, 137, 138,
    139, 143, 161, 162, 179, 389, 443, 445, 465, 500, 514, 515, 520, 587,
    636, 646, 993, 995, 1025, 1080, 1433, 1434, 1521, 1701, 1723, 1755,
    1812, 1813, 1900, 2000, 2049, 2082, 2083, 2086, 2087, 2095, 2096, 2121,
    2222, 2483, 2484, 3128, 3306, 3389, 4443, 4664, 5000, 5222, 5223, 5432,
    5500, 5632, 5672, 5800, 5900, 5901, 5938, 6000, 6379, 6667, 7000, 7070,
    8000, 8008, 8080, 8081, 8086, 8088, 8090, 8181, 8443, 8880, 8888, 9000,
    9090, 9100, 9200, 9443, 10000, 11211, 27017, 27018, 28017, 50000, 50070,
]


def _grab_banner(ip, port, timeout=1.2):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, port))
        # try a lightweight read
        s.settimeout(0.6)
        try:
            s.send(b"\r\n")
        except Exception:
            pass
        try:
            data = s.recv(256)
        except Exception:
            data = b""
        s.close()
        banner = data.decode("utf-8", "ignore").strip()
        return banner.split("\n")[0][:80]
    except Exception:
        return ""


def _scan_one(ip, port, timeout, out, lock):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        rc = s.connect_ex((ip, port))
        s.close()
        if rc == 0:
            banner = _grab_banner(ip, port)
            with lock:
                out.append((port, banner))
                line = f"  {GREEN}[+]{RESET} port {port:<6} open"
                if banner:
                    line += f"  {DIM}{banner}{RESET}"
                print(line)
    except Exception:
        pass


def run():
    banner()
    log("IP Port Scanner", "info")

    target = input_line("ip or host > ").strip()
    if not target:
        pause(); return

    ip = resolve_host(target) or target
    if not resolve_host(ip):
        log(f"could not resolve {target}", "err"); pause(); return

    print(f"\n{WHITE}scan mode:{RESET}")
    print(f"  {GREEN}[1]{RESET} top 100 ports")
    print(f"  {GREEN}[2]{RESET} single port")
    print(f"  {GREEN}[3]{RESET} range (start-end)")
    print(f"  {GREEN}[4]{RESET} full 1-65535 (slow)")
    mode = input_line("select > ").strip()

    if mode == "1":
        ports = TOP_PORTS
    elif mode == "2":
        p = input_line("port > ").strip()
        ports = [int(p)] if p.isdigit() else []
    elif mode == "3":
        rng = input_line("start-end > ").strip()
        try:
            a, b = rng.split("-")
            ports = list(range(int(a), int(b) + 1))
        except Exception:
            log("bad range", "err"); pause(); return
    elif mode == "4":
        ports = list(range(1, 65536))
        log("this will take a while", "warn")
    else:
        log("bad mode", "warn"); pause(); return

    if not ports:
        log("no ports to scan", "warn"); pause(); return

    timeout_str = input_line("timeout seconds [0.5] > ").strip()
    try:
        timeout = float(timeout_str) if timeout_str else 0.5
    except ValueError:
        timeout = 0.5

    workers_str = input_line("threads [200] > ").strip()
    try:
        workers = int(workers_str) if workers_str else 200
    except ValueError:
        workers = 200

    print(f"\n{WHITE}scanning {ip} — {len(ports)} ports, {workers} threads{RESET}\n")

    import time as _t
    t0 = _t.time()
    out = []
    lock = threading.Lock()
    idx = [0]

    def worker(port):
        _scan_one(ip, port, timeout, out, lock)
        with lock:
            idx[0] += 1
            if idx[0] % 500 == 0:
                print(f"{DIM}  ... {idx[0]}/{len(ports)}{RESET}")

    threads = []
    sem = threading.Semaphore(workers)

    def run_one(p):
        with sem:
            worker(p)

    for p in ports:
        t = threading.Thread(target=run_one, args=(p,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    dt = _t.time() - t0
    print()
    log(f"done in {dt:.1f}s — {len(out)} open ports", "ok")

    if out and confirm("save results? [y/n] "):
        body = "\n".join(f"{p}\t{b}" for p, b in sorted(out))
        save_output(timestamp_name(f"portscan_{ip.replace('.','_')}_", "txt"), body)

    pause()