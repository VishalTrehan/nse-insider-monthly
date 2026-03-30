import pandas as pd
import numpy as np
import requests
import os
import time
from datetime import datetime, timedelta
from openai import OpenAI
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# -------------------------------
# NSE SESSION (CRITICAL FIX)
# -------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/"
}

session = requests.Session()
session.headers.update(HEADERS)

# Warm-up request (MANDATORY)
session.get("https://www.nseindia.com", timeout=10)
time.sleep(2)

# -------------------------------
# DATE RANGE (LAST MONTH)
# -------------------------------
today = datetime.today()
first_day = today.replace(day=1)
last_month_end = first_day - timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

from_date = last_month_start.strftime("%d-%m-%Y")
to_date = last_month_end.strftime("%d-%m-%Y")

# -------------------------------
# FETCH DATA
# -------------------------------
url = f"https://www.nseindia.com/api/corporate-sast-reg29?from_date={from_date}&to_date={to_date}"

resp = session.get(url, timeout=20)

try:
    data = resp.json()
except:
    raise ValueError("NSE did not return JSON. Likely blocked or changed API.")

df = pd.DataFrame(data)

if df.empty:
    raise ValueError("No data received from NSE")

# -------------------------------
# STANDARDIZE (BASED ON YOUR COLAB LEARNINGS)
# -------------------------------
df.columns = df.columns.str.strip()

rename_map = {
    'symbol': 'symbol',
    'acqName': 'person',
    'modeOfAcquisition': 'mode',
    'secVal': 'secVal',
    'secAcq': 'stake_change',
    'acqtoDt': 'date'
}

df = df.rename(columns=rename_map)

required = ['symbol','person','mode','secVal','stake_change','date']
df = df[[c for c in required if c in df.columns]]

# -------------------------------
# CLEAN
# -------------------------------
df['date'] = pd.to_datetime(df['date'], errors='coerce')
df = df.dropna(subset=['date'])

df['person'] = df['person'].astype(str)

df['is_promoter'] = df['person'].str.contains("promoter", case=False, na=False).astype(int)

df['is_market'] = df['mode'].str.contains("market", case=False, na=False).astype(int)

# -------------------------------
# FILTER (IMPORTANT)
# -------------------------------
df = df[df['is_market'] == 1]

if df.empty:
    raise ValueError("No market purchase transactions")

# -------------------------------
# AGGREGATE
# -------------------------------
agg = df.groupby('symbol').agg({
    'secVal': 'sum',
    'stake_change': 'sum',
    'symbol': 'count',
    'is_promoter': 'sum'
}).rename(columns={
    'symbol': 'txn_count',
    'is_promoter': 'promoter_txn'
}).reset_index()

# -------------------------------
# SCORING
# -------------------------------
def normalize(x):
    return (x - x.min()) / (x.max() - x.min() + 1e-9)

agg['score_value'] = normalize(agg['secVal'])
agg['score_txn'] = normalize(agg['txn_count'])
agg['score_stake'] = normalize(agg['stake_change'])
agg['score_promoter'] = (agg['promoter_txn'] > 0).astype(int)

agg['final_score'] = (
    0.4*agg['score_value'] +
    0.2*agg['score_txn'] +
    0.2*agg['score_stake'] +
    0.2*agg['score_promoter']
)

top = agg.sort_values('final_score', ascending=False).head(10)

# -------------------------------
# ANALYSIS (CLEAN STYLE)
# -------------------------------
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

prompt = f"""
Write a professional investor note.

No emojis. No markdown. No mention of AI.

Sections:
Key Observations
Concerns
Top Opportunities (3 stocks with reasoning)
Conclusion

DATA:
{top.to_string(index=False)}
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role":"user","content":prompt}]
)

analysis = response.choices[0].message.content

# -------------------------------
# EMAIL FORMAT (CLEAN LIKE YOUR OTHER BOT)
# -------------------------------
top['Rank'] = range(1, len(top)+1)

table_html = top[['Rank','symbol','secVal','stake_change','txn_count','promoter_txn','final_score']].to_html(index=False)

html = f"""
<html>
<body style="font-family:Arial;background:#f4f6fb;padding:20px;">
<div style="max-width:900px;margin:auto;background:#fff;border-radius:10px;">

<div style="background:#0b3d91;color:white;padding:20px;border-radius:10px 10px 0 0;">
<h2>NSE Insider Trading Report</h2>
<p>{from_date} to {to_date}</p>
</div>

<div style="padding:20px;">
<h3>Top Insider Activity</h3>
{table_html}

<h3>Insights</h3>
<p>{analysis.replace(chr(10), "<br>")}</p>
</div>

</div>
</body>
</html>
"""

# -------------------------------
# SEND EMAIL
# -------------------------------
sender = os.environ.get("EMAIL")
password = os.environ.get("GMAIL_APP_PASSWORD")

msg = MIMEMultipart()
msg["Subject"] = "NSE Insider Monthly Report"
msg["From"] = sender
msg["To"] = sender

msg.attach(MIMEText(html, "html"))

server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
server.login(sender, password)
server.sendmail(sender, sender, msg.as_string())
server.quit()

print("Report sent successfully")
