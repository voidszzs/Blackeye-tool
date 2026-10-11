#!/usr/bin/env python3
"""
Blackeye Tool Suite — setup / dependency installer
works on: Kali Linux, Debian, Ubuntu, macOS, Windows 10/11

usage:
    python setup.py            install everything
    python setup.py --check    only report what's missing
    python setup.py --minimal  skip optional heavy deps
"""

import os
import sys
import subprocess
import importlib
import platform
import shutil

MIN_PY = (3, 9)

# ============================================================
# dependency groups
# ============================================================

REQUIRED = [
    "requests",
    "colorama",
]

OPTIONAL = [
    ("phonenumbers", "phone number parsing"),
    ("qrcode[pil]",  "QR generation"),
    ("pillow",       "image handling"),
    ("dnspython",    "dns lookups"),
    ("cryptography", "account manager encryption"),
    ("beautifulsoup4", "html parsing"),
    ("lxml",         "fast html/xml parsing"),
    ("dnspython",    "mx / dns records"),
]

# ============================================================
# helpers
# ============================================================

C_GREEN  = "\033[92m"
C_RED    = "\033[91m"
C_YELLOW = "\033[93m"
C_BLUE   = "\033[94m"
C_DIM    = "\033[2m"
C_RESET  = "\033[0m"


def _ok(msg):    print(f"{C_GREEN}[+]{C_RESET} {msg}")
def _bad(msg):   print(f"{C_RED}[-]{C_RESET} {msg}")
def _warn(msg):  print(f"{C_YELLOW}[!]{C_RESET} {msg}")
def _info(msg):  print(f"{C_BLUE}[*]{C_RESET} {msg}")
def _dim(msg):   print(f"{C_DIM}    {msg}{C_RESET}")


def check_python():
    if sys.version_info < MIN_PY:
        _bad(f"python {MIN_PY[0]}.{MIN_PY[1]}+ required, you have "
             f"{sys.version_info.major}.{sys.version_info.minor}")
        return False
    _ok(f"python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True


def check_os():
    s = platform.system().lower()
    _ok(f"os: {platform.system()} {platform.release()}")
    if s == "windows":
        _dim("windows mode: some tools fall back to pure-python paths")
    return s


def pkg_installed(name):
    """check if a pip package is importable (handles extras like qrcode[pil])."""
    base = name.split("[")[0].strip()
    try:
        importlib.import_module(base)
        return True
    except ImportError:
        return False


def pip_install(pkg, quiet=True):
    cmd = [sys.executable, "-m", "pip", "install", pkg]
    if quiet:
        cmd += ["--quiet", "--disable-pip-version-check"]
    try:
        rc = subprocess.call(cmd)
        return rc == 0
    except Exception as e:
        _bad(f"pip failed: {e}")
        return False


def check_external_binary(name):
    return shutil.which(name) is not None


# ============================================================
# main installer
# ============================================================

def install_all(minimal=False):
    print()
    _info("checking required dependencies ...")
    for pkg in REQUIRED:
        if pkg_installed(pkg):
            _ok(f"{pkg} already installed")
        else:
            _info(f"installing {pkg} ...")
            if pip_install(pkg):
                _ok(f"{pkg} installed")
            else:
                _bad(f"{pkg} install failed — try manually: pip install {pkg}")

    if minimal:
        _warn("skipping optional deps (--minimal)")
        return

    print()
    _info("checking optional dependencies ...")
    for pkg, why in OPTIONAL:
        if pkg_installed(pkg):
            _ok(f"{pkg} already installed  {C_DIM}({why}){C_RESET}")
        else:
            _info(f"installing {pkg}  {C_DIM}({why}){C_RESET}")
            if pip_install(pkg):
                _ok(f"{pkg} installed")
            else:
                _warn(f"{pkg} failed — optional, tool will degrade gracefully")

    print()
    _info("checking external binaries ...")
    externals = [
        ("cloudflared", "public tunnel for QR phisher"),
        ("ngrok",       "alternative public tunnel"),
        ("exiftool",    "image metadata extraction"),
        ("git",         "for cloning tools / updates"),
    ]
    for name, why in externals:
        if check_external_binary(name):
            _ok(f"{name} found")
        else:
            _warn(f"{name} not found  {C_DIM}({why}){C_RESET}")
            _dim(f"install: https://example.com/{name} (optional)")


def check_only():
    print()
    _info("dependency report:")
    all_ok = True
    for pkg in REQUIRED:
        if pkg_installed(pkg):
            _ok(f"{pkg}  (required)")
        else:
            _bad(f"{pkg}  (required) — MISSING")
            all_ok = False
    for pkg, why in OPTIONAL:
        if pkg_installed(pkg):
            _ok(f"{pkg}  ({why})")
        else:
            _warn(f"{pkg}  ({why}) — missing (optional)")
    print()
    _info("external binaries:")
    for name, why in [("cloudflared","tunnel"), ("ngrok","tunnel"), ("exiftool","metadata")]:
        if check_external_binary(name):
            _ok(f"{name}")
        else:
            _warn(f"{name}  not found")
    print()
    if all_ok:
        _ok("all required deps present")
    else:
        _bad("some required deps missing — run: python setup.py")


def main():
    args = sys.argv[1:]
    print(f"{C_RED}Blackeye Tool Suite — setup{C_RESET}")
    print(f"{C_DIM}cross-platform installer for kali / debian / mac / windows{C_RESET}")
    print()

    if not check_python():
        sys.exit(1)
    check_os()
    print()

    if "--check" in args:
        check_only()
        return
    install_all(minimal="--minimal" in args)

    print()
    _ok("setup complete. run the launcher:  python Blackeye.py")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        _warn("interrupted")
        sys.exit(1)