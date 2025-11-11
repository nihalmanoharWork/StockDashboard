#!/usr/bin/env python3
"""
fetch_and_save.py
Fetch NSE /api/event-calendar and write data/events.json
"""

import json
import time
import random
import requests
from pathlib import Path

BASE_URL = "https://www.nseindia.com"
API_URL = f"{BASE_URL}/api/event-calendar"
OUT_PATH = Path("data/events.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "application/json, text/plain, */*",
    "Referer": BASE_URL,
}

def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

def fetch_events(retries=4):
    session = make_session()
    try:
        session.get(BASE_URL, timeout=10)
    except Exception:
        # ignore warm-up failures; still attempt API
        pass

    for attempt in range(1, retries + 1):
        try:
            time.sleep(random.uniform(0.5, 2.0))
            resp = session.get(API_URL, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            print(f"HTTP error on attempt {attempt}: {status}")
            if status in (429, 403):
                wait = 2 ** attempt + random.uniform(0, 2)
                print(f"Rate-limited; backing off {wait:.1f}s")
                time.sleep(wait)
            else:
                if attempt == retries:
                    raise
                time.sleep(1 + attempt)
        except requests.RequestException as e:
            print(f"Request exception on attempt {attempt}: {e}")
            if attempt == retries:
                raise
            time.sleep(1 + attempt)

def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_events()
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved events to {OUT_PATH}")

if __name__ == "__main__":
    main()
