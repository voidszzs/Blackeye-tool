# Simple file logger
import os
from datetime import datetime

LOG_FILE = None


def set_log_file(path):
    global LOG_FILE
    LOG_FILE = path
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _write(level, msg):
    if not LOG_FILE:
        return
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {msg}\n")
    except Exception:
        pass


def debug(m): _write("DEBUG", m)
def info(m): _write("INFO", m)
def warn(m): _write("WARN", m)
def error(m): _write("ERROR", m)
