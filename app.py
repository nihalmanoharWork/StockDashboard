import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import textwrap

# ---------------- Page config ----------------
st.set_page_config(page_title="NSE Earnings Calendar", layout="wide")
st.title("📅 NSE Upcoming Earnings (Next 7 Days)")

# ---------------- Settings ----------------
PRIMARY_PATH = Path("data/events.json")
FALLBACK_PATH = Path("events.json")
SEARCH_PATHS = [PRIMARY_PATH, FALLBACK_PATH]

# ---------------- Helpers ----------------
def find_events_file():
    for p in SEARCH_PATHS:
        if p.exists():
            return p
    return None


@st.cache_data(ttl=3600)
def load_json_file(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        st.error(f"❌ Invalid JSON format in {path}.")
        return None
    except Exception as e:
        st.error(f"❌ Error reading {path}: {e}")
        return None


def normalize_to_df(payload):
    """
    Accept payload that may be a list or a dict with 'data' key and return a DataFrame.
    Ensures columns 'symbol', 'name', 'date', 'estimated_eps' exist and parses the date column safely.
    """
    if payload is None:
        return pd.DataFrame(columns=["symbol", "name", "date", "estimated_eps"])

    if isinstance(payload, dict):
        records = payload.get("data") or payload.get("Data") or []
    elif isinstance(payload, list):
        records = payload
    else:
        return pd.DataFrame(columns=["symbol", "name", "date", "estimated_eps"])

    if not isinstance(records, list):
        if isinstance(records, dict):
            records = [records]
        else:
            return pd.DataFrame(columns=["symbol", "name", "date", "estimated_eps"])

    df = pd.DataFrame(records)

    # 🔧 Normalize column names to lowercase for case-insensitive matching
    df.columns = df.columns.str.lower()

    # map known columns (all keys lowercase)
    col_map = {
        "company": "name",
        "companyname": "name",
        "bm_desc": "remarks",
         "boardmeetingdate": "date",
        "date": "date",
        "symbol": "symbol",
        "estimated_eps": "estimated_eps",
    }

    rename_dict = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename_dict)


    # ensure required columns exist
    for c in ("symbol", "name", "date", "estimated_eps"):
        if c not in df.columns:
            df[c] = None

    # parse date safely
    df["date"] = pd.to_datetime(df["date"], dayfirst=False, errors="coerce")

    return df[["symbol", "name", "date", "estimated_eps"]]


# ---------------- Sidebar Tools ----------------
with st.sidebar:
    st.markdown("### Developer Tools")
    if st.button("Generate small sample data file (data/events.json)"):
        SAMPLE = [
            {"symbol": "ABC", "company": "ABC Industries", "date": "12-Nov-2025", "estimated_eps": 3.25},
            {"symbol": "XYZ", "company": "XYZ Ltd", "date": "13-Nov-2025", "estimated_eps": 1.78},
            {"symbol": "TST", "company": "Test Corp", "date": "20-Nov-2025", "estimated_eps": 0.95},
        ]
        PRIMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        PRIMARY_PATH.write_text(json.dumps(SAMPLE, indent=2, ensure_ascii=False), encoding="utf-8")
        st.success(f"Sample created at: {PRIMARY_PATH}")
        st.experimental_rerun()


# ---------------- Load data ----------------
events_file = find_events_file()
if not events_file:
    st.error(textwrap.dedent(
        """
        ❌ events.json not found.
        Please place your JSON file at either:
          - data/events.json
          - events.json (project root)
        Or use the sidebar button to generate a small sample file for testing.
        """
    ))
    st.stop()

payload = load_json_file(events_file)
if payload is None:
    st.stop()

df_all = normalize_to_df(payload)
if df_all.empty:
    st.warning("No usable records found in the JSON file.")
    st.stop()

# ---------------- Ensure date column is datetimelike ----------------
if not pd.api.types.is_datetime64_any_dtype(df_all["date"]):
    df_all["date"] = pd.to_datetime(df_all["date"], errors="coerce")

df_all = df_all.dropna(subset=["date"]).reset_index(drop=True)
if df_all.empty:
    st.warning("No records with valid dates found after parsing.")
    st.stop()

# ---------------- Filter upcoming (next 7 days) ----------------
today = datetime.now().date()
next_week = today + timedelta(days=7)
mask = (df_all["date"].dt.date >= today) & (df_all["date"].dt.date <= next_week)
upcoming = df_all.loc[mask].copy()

# ---------------- Display ----------------
st.subheader(f"📅 Upcoming Earnings — {today} to {next_week}")
st.caption(f"Data source: {events_file} — {len(upcoming)} upcoming record(s)")

if upcoming.empty:
    st.info("No upcoming earnings found in the next 7 days.")
else:
    upcoming_sorted = upcoming.sort_values("date").reset_index(drop=True)
    upcoming_sorted["date"] = upcoming_sorted["date"].dt.strftime("%d-%b-%Y")

    # format EPS nicely
    def fmt_eps(val):
        if pd.isna(val) or val == "":
            return "—"
        try:
            return f"{float(val):.2f}"
        except Exception:
            return str(val)

    upcoming_sorted["estimated_eps"] = upcoming_sorted["estimated_eps"].apply(fmt_eps)

    # Display with all 4 columns
    st.dataframe(
        upcoming_sorted[["symbol", "name", "date", "estimated_eps"]],
        use_container_width=True,
        hide_index=True
    )

    csv_bytes = upcoming_sorted[["symbol", "name", "date", "estimated_eps"]].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Upcoming Earnings (CSV)",
        csv_bytes,
        "upcoming_earnings.csv",
        mime="text/csv"
    )

# ---------------- Debug: view raw JSON ----------------
with st.expander("🧾 View raw JSON (debug)"):
    st.write(f"Loaded from: {events_file}")
    st.json(payload)
