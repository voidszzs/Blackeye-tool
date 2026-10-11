# IP Generator
# random v4 / v6

from Config.Colors import *
from Config.Util import *

import random
import ipaddress


def run():
    banner()
    log("IP Generator", "info")

    print(f"  {GREEN}[1]{RESET} random ipv4")
    print(f"  {GREEN}[2]{RESET} random ipv6")
    print(f"  {GREEN}[3]{RESET} ipv4 in cidr")
    print(f"  {GREEN}[4]{RESET} bulk list")
    mode = input_line("select > ").strip()

    def rand_v4():
        return str(ipaddress.IPv4Address(random.getrandbits(32)))

    def rand_v6():
        return str(ipaddress.IPv6Address(random.getrandbits(128)))

    if mode == "1":
        print(f"\n{rand_v4()}")
    elif mode == "2":
        print(f"\n{rand_v6()}")
    elif mode == "3":
        cidr = input_line("cidr (e.g. 10.0.0.0/24) > ").strip()
        try:
            net = ipaddress.ip_network(cidr, strict=False)
            n = random.randint(0, net.num_addresses - 1)
            print(f"\n{net[n]}")
        except Exception as e:
            log(f"bad cidr: {e}", "err")
    elif mode == "4":
        cnt_str = input_line("count [50] > ").strip()
        try:
            cnt = int(cnt_str) if cnt_str else 50
        except ValueError:
            cnt = 50
        kind = input_line("v4 or v6? [v4] > ").strip().lower() or "v4"
        ips = [rand_v4() if kind == "v4" else rand_v6() for _ in range(cnt)]
        print()
        for x in ips:
            print(f"  {x}")
        if confirm("\nsave? [y/n] "):
            save_output(timestamp_name("ipgen_", "txt"), "\n".join(ips))
    else:
        log("bad choice", "warn")

    pause()