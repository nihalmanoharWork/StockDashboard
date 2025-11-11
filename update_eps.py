import json
import time
import random
from pathlib import Path
from tqdm import tqdm
import yfinance as yf

# -----------------------------
# Config
# -----------------------------
DATA_PATH = Path("data/events.json")
OUTPUT_PATH = DATA_PATH  # overwrite same file
MAX_RETRIES = 3
BASE_DELAY = 1.5  # seconds between requests
BACKOFF_FACTOR = 2  # exponential backoff multiplier
RANDOM_JITTER = 0.3  # +/- jitter to look natural

# -----------------------------
# Helper Functions
# -----------------------------

def safe_fetch_forward_eps(symbol: str):
    """
    Fetch forward EPS with retry and exponential backoff.
    Uses Yahoo Finance (no API key required).
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ticker = yf.Ticker(symbol + ".NS")
            info = ticker.info
            eps = info.get("forwardEps")
            if eps is not None:
                return eps
            else:
                # Sometimes Yahoo returns partial data; retry after short delay
                raise ValueError("Missing EPS data")
        except Exception as e:
            if attempt == MAX_RETRIES:
                print(f"⚠️  [{symbol}] Failed after {MAX_RETRIES} attempts: {e}")
                return None
            delay = BASE_DELAY * (BACKOFF_FACTOR ** (attempt - 1))
            delay += random.uniform(-RANDOM_JITTER, RANDOM_JITTER)
            print(f"⏳ [{symbol}] Retry {attempt}/{MAX_RETRIES} in {delay:.1f}s...")
            time.sleep(delay)
    return None


def update_events_with_eps(filepath: Path):
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        return

    with filepath.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("❌ Invalid format: events.json must be a list.")
        return

    symbols = {entry.get("symbol") for entry in data if entry.get("symbol")}
    print(f"🔍 Found {len(symbols)} unique NSE symbols.")

    # Cache previously fetched EPS to avoid redundant calls
    eps_cache = {}

    for symbol in tqdm(symbols, desc="Fetching EPS", ncols=80):
        if not symbol:
            continue
        if symbol in eps_cache:
            continue  # already fetched
        eps = safe_fetch_forward_eps(symbol)
        eps_cache[symbol] = eps
        # Respect rate limit: base delay + random jitter
        sleep_time = BASE_DELAY + random.uniform(0, RANDOM_JITTER)
        time.sleep(sleep_time)

    # Update the data
    for entry in data:
        symbol = entry.get("symbol")
        if symbol in eps_cache:
            entry["estimated_EPS"] = eps_cache[symbol]

    # Write back to same file
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Updated EPS for {len(symbols)} companies.")
    print(f"💾 Saved updated file to {OUTPUT_PATH.resolve()}")


if __name__ == "__main__":
    print("🚀 Starting EPS updater...")
    update_events_with_eps(DATA_PATH)
    print("🎯 Done.")
