import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta

st.set_page_config(page_title="NSE Earnings Calendar", layout="wide")
st.title("📅 NSE Upcoming Earnings (Next 7 Days)")

# -----------------------------------
# Fetch or read data
# -----------------------------------

@st.cache_data(ttl=3600)
def fetch_event_calendar(url: str = None, local_file: str = "events.json"):
    """
    Fetches NSE event data from URL or local JSON file.
    Cached for 1 hour.
    """
    try:
        if url:
            st.info("🔄 Fetching latest data from NSE...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json, text/html",
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
        else:
            st.info(f"📂 Loading local file: {local_file}")
            with open(local_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
    except json.JSONDecodeError:
        st.error("❌ Invalid JSON file. Please check the format of events.json.")
        return []
    except Exception as e:
        st.error(f"⚠️ Error fetching data: {e}")
        return []

    return payload


# -----------------------------------
# Parse event JSON into DataFrame
# -----------------------------------

@st.cache_data(ttl=3600)
def parse_events_from_payload(payload):
    """
    Handles both list and dict JSON formats.
    """
    if isinstance(payload, dict):
        records = payload.get("data") or payload.get("Data") or []
    elif isinstance(payload, list):
        records = payload
    else:
        st.warning("Unexpected payload format.")
        return pd.DataFrame()

    if not records:
        st.warning("No events found in data.")
        return pd.DataFrame()

    df = pd.DataFrame(records)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])  # drop invalid dates

    return df


# -----------------------------------
# Main Execution
# -----------------------------------

# Replace `local_file` with URL later if needed
payload = fetch_event_calendar(local_file="events.json")
df_all = parse_events_from_payload(payload)

with st.expander("🧾 View Raw JSON (debug)"):
    st.json(payload)

# -----------------------------------
# Filter for next 7 days
# -----------------------------------

today = datetime.today().date()
upcoming = df_all[df_all["date"].dt.date.between(today, today + timedelta(days=7))]

st.subheader(f"🗓️ Earnings Due Between {today} and {today + timedelta(days=7)}")

if upcoming.empty:
    st.warning("No upcoming earnings in the next 7 days.")
else:
    st.dataframe(
        upcoming.sort_values("date"),
        use_container_width=True,
        hide_index=True,
    )

    csv = upcoming.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Upcoming Earnings (CSV)", csv, "upcoming_earnings.csv")
