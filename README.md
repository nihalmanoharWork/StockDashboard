# 📅 NSE Earnings Calendar Dashboard

A simple Streamlit web app that displays upcoming **NSE-listed company earnings** and their **estimated EPS** for the next 7 days.

Built using:
- 🐍 Python 3.11
- 💹 Streamlit
- 🤖 GitHub Actions (for automated data updates)
- 🌐 BeautifulSoup (for scraping)
- ⏱️ Scheduled to refresh daily at **6:00 AM IST**

---

## 🚀 Features

- 📆 Displays all upcoming NSE board meetings and earnings announcements within 7 days.
- 💰 Automatically fetches **estimated EPS** data (no API keys required).
- ♻️ Refreshes every morning using GitHub Actions.
- 📊 Download upcoming earnings as a CSV.
- ☁️ Hosted free on [Streamlit Cloud](https://streamlit.io/cloud).

---

## 🧩 Project Structure
├── app.py # Streamlit app
├── fetch_and_save.py # Scrapes upcoming NSE events
├── update_eps.py # Fetches estimated EPS for companies
├── requirements.txt # Python dependencies
├── data/
│ └── events.json # Stored events and EPS data
└── .github/
└── workflows/
└── fetch-nse-event-calendar.yml # Daily GitHub Action

🕒 Automated Data Updates

Data is refreshed daily at 6:00 AM IST via a GitHub Actions workflow.

📊 Example Output
Symbol	Name	Date	Estimated EPS
INFY	Infosys Limited	14-Nov-2025	₹19.4
TCS	Tata Consultancy Services Ltd	13-Nov-2025	₹27.6
HDFCBANK	HDFC Bank Limited	15-Nov-2025	₹22.1

🧠 Developer Notes

No API keys required — uses Google Finance & NSE scraping with rate limiting.

Designed for corporate environments (resilient to SSL and retry issues).

The app automatically reloads data when updated by the GitHub Action.

🧾 License

MIT License © [Nihal Manohar]
