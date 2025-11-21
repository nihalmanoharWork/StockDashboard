"""
ai_groq_predict_groq.py (Verbose Version with .env support + rate limiting)

Logs every major step and ensures Groq API calls respect free-tier limits.
"""

import os
import subprocess
import json
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import yfinance as yf
import re
from tqdm import tqdm
from dateutil import parser as dparser
from groq import Groq
import time
from collections import deque

# NEW: Load .env file
from dotenv import load_dotenv

# ======================================================
# CONFIG
# ======================================================
print("🔧 Initializing configuration...")

# Load .env first
load_dotenv()
print("📄 Loaded .env file")

# Fetch key
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_KEY")
if not GROQ_API_KEY:
    raise SystemExit(
        "❌ ERROR: GROQ_API_KEY not found.\n"
        "Ensure your `.env` contains:\n"
        "GROQ_API_KEY=your_key_here"
    )

# Use free-tier supported model by default
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

EVENTS_PATH = Path("data/events.json")
OUTPUT_PATH = Path("ai_groq_predictions.json")
FETCH_SCRIPT_PATH = Path("fetch_and_save.py")
UPDATE_EPS_SCRIPT_PATH = Path("update_eps.py")

print(f"📌 Using Groq model: {GROQ_MODEL}")
print(f"📌 Events path: {EVENTS_PATH}")
print(f"📌 Output path: {OUTPUT_PATH}")

client = Groq(api_key=GROQ_API_KEY)

# ======================================================
# Rate Limiter for Free Tier
# ======================================================
MAX_REQS_PER_MIN = 30  # Free tier limit
req_timestamps = deque()

def throttle_requests():
    now = time.time()
    # Remove old timestamps
    while req_timestamps and now - req_timestamps[0] > 60:
        req_timestamps.popleft()
    if len(req_timestamps) >= MAX_REQS_PER_MIN:
        wait = 60 - (now - req_timestamps[0]) + 0.1
        print(f"⏳ Rate limit reached: sleeping for {wait:.1f} sec")
        time.sleep(wait)
    req_timestamps.append(time.time())

# ======================================================
# Helpers
# ======================================================

def run_script_if_present(script_path: Path):
    if script_path.exists():
        print(f"🚀 Running script: {script_path}")
        try:
            subprocess.check_call(["python", str(script_path)])
        except subprocess.CalledProcessError as e:
            print(f"⚠️ WARNING: Script {script_path} failed with: {e}")
    else:
        print(f"⚠️ Script not found, skipping: {script_path}")

def days_to_event(date_str):
    if not date_str:
        return None
    try:
        parsed = dparser.parse(date_str).date()
        today = datetime.now(timezone.utc).date()
        delta = (parsed - today).days
        print(f"📅 Days to event ({date_str}) = {delta}")
        return delta
    except Exception as e:
        print(f"⚠️ Could not parse date '{date_str}': {e}")
        return None

def fetch_price_features(symbol: str, period="180d"):
    print(f"📈 Fetching price data for {symbol}...")
    try:
        tk = yf.Ticker(symbol + ".NS")
        hist = tk.history(period=period)

        if hist.empty:
            print(f"⚠️ No price data found for {symbol}")
            return {}

        close = hist["Close"].dropna()
        if close.empty:
            print(f"⚠️ No closing price data found for {symbol}")
            return {}

        def pct(n):
            if len(close) > n:
                return float(close.iloc[-1] / close.iloc[-n-1] - 1)
            return None

        features = {
            "last_price": float(close.iloc[-1]),
            "pct_7": pct(6),
            "pct_30": pct(22),
            "sma20": float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None,
            "vol_30": float(hist["Volume"][-30:].std()) if len(hist) >= 30 else None,
        }

        print(f"📊 Price features for {symbol} → {features}")
        return features

    except Exception as e:
        print(f"❌ ERROR fetching price data for {symbol}: {e}")
        return {}

def purpose_sentiment(purpose, bm_desc):
    t = (purpose + " " + bm_desc).lower()
    print(f"📝 Analyzing purpose/bm_desc sentiment...")

    score, reasons = 0.0, []

    if "dividend" in t:
        score += 0.2; reasons.append("dividend mentioned")
    if "results" in t:
        score += 0.05
    if any(x in t for x in ["rights issue", "fund raising", "preferential", "capital raise"]):
        score -= 0.3; reasons.append("dilution-related terms")

    print(f"🎯 Sentiment score={score}, reasons={reasons}")
    return score, "; ".join(reasons)

def build_prompt(detail):
    system = (
        "You are a financial assistant. Return ONLY JSON with:\n"
        "- recommendation (buy/hold/sell)\n"
        "- confidence (0-1)\n"
        "- rationale (short)\n"
        "- action (one sentence)\n"
        "- features_used (list)\n"
    )
    print("🧠 Building LLM prompt...")
    return system, json.dumps({"data": detail}, indent=2)

def extract_json(text):
    print("🔍 Extracting JSON from LLM response...")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0)) if m else None

def call_groq(system_msg, user_msg):
    throttle_requests()
    print("🤖 Calling Groq API...")
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=300,
        temperature=0,
    )

    # FIX: attribute access for ChatCompletionMessage
    raw = response.choices[0].message.content
    print(f"📥 Raw Groq output:\n{raw}\n")

    parsed = extract_json(raw)
    if not parsed:
        print("⚠️ FAILED TO PARSE JSON — Falling back to HOLD.")
        return {
            "recommendation": "hold",
            "confidence": 0.5,
            "rationale": "Model returned invalid JSON",
            "action": "Hold position",
            "features_used": []
        }

    print(f"✅ Parsed JSON: {parsed}")
    return parsed

# ======================================================
# MAIN PIPELINE
# ======================================================

def main():
    print("\n============================")
    print("🚀 Starting Groq Predictor (with .env + rate limiting)")
    print("============================\n")

    print("📌 Step 1 — Running source scripts...")
    run_script_if_present(FETCH_SCRIPT_PATH)
    run_script_if_present(UPDATE_EPS_SCRIPT_PATH)

    print("\n📌 Step 2 — Reading events.json...")
    if not EVENTS_PATH.exists():
        raise SystemExit("❌ ERROR: events.json not found!")

    events = json.loads(EVENTS_PATH.read_text())
    if isinstance(events, dict) and "data" in events:
        events = events["data"]

    print(f"📄 Loaded {len(events)} events.")

    rows = []
    print("\n📌 Step 3 — Preparing features...")
    for ev in tqdm(events):
        symbol = ev["symbol"]
        print(f"\n🔎 Processing symbol: {symbol}")

        price = fetch_price_features(symbol)
        days = days_to_event(ev["date"])
        sentiment_score, sentiment_reason = purpose_sentiment(ev["purpose"], ev["bm_desc"])

        detail = {
            **ev,
            "days_to_event": days,
            "sentiment_score": sentiment_score,
            "sentiment_reason": sentiment_reason,
            **price
        }

        rows.append(detail)

    predictions = []
    print("\n📌 Step 4 — Calling Groq for each symbol...\n")
    for detail in tqdm(rows):
        system_msg, user_msg = build_prompt(detail)
        prediction = call_groq(system_msg, user_msg)

        predictions.append({
            "symbol": detail["symbol"],
            "company": detail["company"],
            "input": detail,
            "prediction": prediction
        })

    print("\n📌 Step 5 — Saving output...")
    OUTPUT_PATH.write_text(json.dumps(predictions, indent=2))

    print("\n🎉 DONE! Predictions saved to:", OUTPUT_PATH)

if __name__ == "__main__":
    main()
