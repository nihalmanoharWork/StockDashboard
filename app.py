import streamlit as st
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta

DATA_FILE = Path("data/events.json")
CACHE_MAX_AGE = timedelta(hours=4)  # treat local cache as fresh for 4 hours

st.set_page_config(page_title="📅 NSE Upcoming Results", layout="wide")
st.title("📅 NSE Upcoming Corporate Events (7 Days)")

def read_local_cache():
    if not DATA_FILE.exists():
        return None
    mtime = datetime.fromtimestamp(DATA_FILE.stat().st_mtime)
    age = datetime.now() - mtime
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None
    # If cache is too old return it anyway but mark as stale in UI
    return {"payload": payload, "mtime": mtime, "age": age}

@st.cache_data(ttl=15 * 60)
def parse_events_from_payload(payload: dict):
    """Normalize the NSE payload into a DataFrame."""
    records = payload.get("data") or payload.get("Data") or payload
    df = pd.DataFrame(records)
    # Standardize names if present
    df.rename(columns={
        "symbol": "Symbol",
        "companyName": "Company",
        "purpose": "Purpose",
        "boardMeetingDate": "Meeting Date",
        "remarks": "Remarks",
        "industry": "Industry",
        "segment": "Segment"
    }, inplace=True)
    # Parse Meeting Date
    def parse_date(x):
        try:
            return pd.to_datetime(x, dayfirst=True).date()
        except Exception:
            return pd.NaT
    if "Meeting Date" in df.columns:
        df["Meeting Date"] = df["Meeting Date"].astype(str).apply(parse_date)
    return df

# UI controls
col1, col2 = st.columns([2, 1])
with col1:
    lookahead = st.slider("Show results due in next N days", 1, 30, 7)
with col2:
    refresh_btn = st.button("🔄 Refresh (force live fetch)")

# Try local cache first
cached = read_local_cache()
if cached:
    payload = cached["payload"]
    age = cached["age"]
    st.success(f"Using local cached data (age: {int(age.total_seconds()/60)} min).")
    df_all = parse_events_from_payload(payload)
else:
    st.warning("No local cache found. Attempting live fetch (may fail inside corporate network).")
    # Try a live fetch if cache missing; re-use code used in prior steps (a minimal live fetch)
    import requests, random, time
    def live_fetch():
        BASE = "https://www.nseindia.com"
        API = f"{BASE}/api/event-calendar"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json, text/plain, */*",
            "Referer": BASE,
        }
        session = requests.Session()
        session.headers.update(headers)
        try:
            session.get(BASE, timeout=10)
        except Exception:
            pass
        for attempt in range(3):
            try:
                time.sleep(random.uniform(0.5, 1.5))
                r = session.get(API, timeout=15)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                st.warning(f"Live fetch attempt {attempt+1} failed: {e}")
                time.sleep(1 + attempt)
        return None
    payload = live_fetch()
    if payload:
        df_all = parse_events_from_payload(payload)
    else:
        st.error("Live fetch failed and no local cache available. The app cannot proceed.")
        st.stop()

# Optional force refresh: if user clicks "Refresh", try live fetch and overwrite local cache if successful
if refresh_btn:
    st.info("Attempting forced live fetch...")
    import subprocess, sys
    try:
        import fetch_and_save  # if this script exists locally & works
        # Prefer running fetch_and_save.py directly
        import runpy
        runpy.run_path("fetch_and_save.py", run_name="__main__")
        st.success("Live fetch via fetch_and_save.py completed — reloading local cache...")
        cached = read_local_cache()
        if cached:
            df_all = parse_events_from_payload(cached["payload"])
    except Exception as e:
        st.warning(f"Could not run fetch script locally: {e}. Trying inline live fetch...")
        # fallback inline live fetch
        # (reuse inline fetch from above)
        payload2 = None
        try:
            payload2 = live_fetch()
        except Exception:
            payload2 = None
        if payload2:
            df_all = parse_events_from_payload(payload2)
        else:
            st.error("Forced live fetch failed.")

# Filter upcoming
today = datetime.now().date()
end_date = today + pd.Timedelta(days=lookahead)
if "Meeting Date" in df_all.columns:
    df_upcoming = df_all[(df_all["Meeting Date"].notna()) & (df_all["Meeting Date"] >= today) & (df_all["Meeting Date"] <= end_date)].copy()
else:
    df_upcoming = pd.DataFrame()

# Display
st.markdown("### Results")
st.metric("Today", today.strftime("%d %b %Y"))
st.metric(f"Upcoming (next {lookahead} days)", len(df_upcoming))

search = st.text_input("Search company/purpose/industry")
df_display = df_upcoming.copy()
if search:
    mask = df_display.astype(str).apply(lambda x: x.str.contains(search, case=False, na=False)).any(axis=1)
    df_display = df_display[mask]

if df_display.empty:
    st.info("No upcoming events found.")
else:
    st.dataframe(df_display[["Symbol", "Company", "Meeting Date", "Purpose", "Remarks", "Industry", "Segment"]].sort_values("Meeting Date").reset_index(drop=True), use_container_width=True, height=480)

csv = df_display.to_csv(index=False)
st.download_button("💾 Download CSV", csv, "nse_upcoming_events.csv", "text/csv")

st.caption("Local cache provided by GitHub Actions workflow (fetch_nse.yml).")
