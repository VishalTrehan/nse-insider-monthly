import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime, timedelta
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText

# -------------------------------
# STEP 1: Fetch NSE Data
# -------------------------------
url = "https://www.nseindia.com/api/corporates-pit"

headers = {
    "User-Agent": "Mozilla/5.0"
}

session = requests.Session()
session.get("https://www.nseindia.com", headers=headers)

response = session.get(url, headers=headers)
data = response.json().get("data", [])

df = pd.DataFrame(data)

if df.empty:
    raise ValueError("No data fetched from NSE")

# -------------------------------
# STEP 2: CLEAN + STANDARDIZE
# -------------------------------

# Normalize column names
df.columns = [col.strip() for col in df.columns]

# Flexible mapping (based on ALL your earlier failures)
column_map = {
    'symbol': 'symbol',
    'acqName': 'acqName',
    'personCategory': 'person',
    'personCat': 'person',
    'category': 'person',

    'modeOfAcquisition': 'mode',
    'acqMode': 'mode',
    'mode': 'mode',

    'secVal': 'secVal',

    'secAcq': 'stake_change',
    'changeInShareholding': 'stake_change',
    'secValChange': 'stake_change',

    'date': 'date',
    'acqfromDt': 'date',
    'acqtoDt': 'date'
}

# Apply mapping
df = df.rename(columns={col: column_map[col] for col in df.columns if col in column_map})

# Remove duplicate columns (VERY IMPORTANT)
df = df.loc[:, ~df.columns.duplicated()]

# Ensure required columns exist
required_cols = ['symbol', 'person', 'mode', 'secVal', 'stake_change', 'date']

for col in required_cols:
    if col not in df.columns:
        df[col] = np.nan

df = df[required_cols]

# -------------------------------
# STEP 3: TYPE CLEANING
# -------------------------------
df['secVal'] = pd.to_numeric(df['secVal'], errors='coerce')
df['stake_change'] = pd.to_numeric(df['stake_change'], errors='coerce')

# Safe date parsing
df['date'] = pd.to_datetime(df['date'], errors='coerce', dayfirst=True)

# Drop junk rows
df = df.dropna(subset=['symbol', 'secVal'])

# -------------------------------
# STEP 4: LAST MONTH FILTER
# -------------------------------
today = datetime.today()
first_day_this_month = today.replace(day=1)
last_month_end = first_day_this_month - timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

df = df[(df['date'] >= last_month_start) & (df['date'] <= last_month_end)]

# Fallback (VERY IMPORTANT — NSE delay issue)
if df.empty:
    df = df.sort_values('date', ascending=False).head(1000)

# -------------------------------
# STEP 5: PROMOTER FILTER
# -------------------------------
df['is_promoter'] = df['person'].str.contains("PROMOTER", case=False, na=False)
df = df[df['is_promoter']]

# -------------------------------
# STEP 6: AGGREGATION
# -------------------------------
summary = df.groupby('symbol').agg({
    'secVal': 'sum',
    'stake_change': 'sum',
    'symbol': 'count'
}).rename(columns={'symbol': 'txn_count'}).reset_index()

if summary.empty:
    raise ValueError("No promoter transactions found")

# -------------------------------
# STEP 7: SCORING (your working logic)
# -------------------------------
summary['score_value'] = summary['secVal'] / summary['secVal'].max()
summary['score_txn'] = summary['txn_count'] / summary['txn_count'].max()

summary['score_stake'] = (
    (summary['stake_change'] - summary['stake_change'].min()) /
    (summary['stake_change'].max() - summary['stake_change'].min() + 1e-9)
)

summary['final_score'] = (
    0.4 * summary['score_value'] +
    0.3 * summary['score_txn'] +
    0.3 * summary['score_stake']
)

summary = summary.sort_values('final_score', ascending=False)

top_stocks = summary.head(10)

# -------------------------------
# STEP 8: AI ANALYSIS
# -------------------------------
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompt = f"""
You are a stock market analyst.

Here is insider trading summary:

{top_stocks.to_string(index=False)}

Give:
1. Bullish signals
2. Red flags
3. Top 3 stocks
4. Final insight
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

analysis = response.choices[0].message.content

# -------------------------------
# STEP 9: EMAIL
# -------------------------------
sender = os.environ["EMAIL"]
password = os.environ["GMAIL_APP_PASSWORD"]

msg = MIMEText(analysis)
msg['Subject'] = "Monthly NSE Insider Report"
msg['From'] = sender
msg['To'] = sender

server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
server.login(sender, password)
server.sendmail(sender, sender, msg.as_string())
server.quit()

print("✅ Email Sent Successfully")
