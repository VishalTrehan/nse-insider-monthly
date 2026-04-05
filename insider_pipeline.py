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
# NSE SESSION
# -------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/"
}

session = requests.Session()
session.headers.update(HEADERS)

session.get("https://www.nseindia.com", timeout=10)
time.sleep(2)

# -------------------------------
# DATE RANGE
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
data = resp.json()

records = data.get("data", [])
if not records:
    raise ValueError("No data received")

df = pd.DataFrame(records)
df.columns = df.columns.str.strip()

# -------------------------------
# USE ACTUAL COLUMNS
# -------------------------------
df['date'] = pd.to_datetime(df['acquirerDate'], errors='coerce')
df = df.dropna(subset=['date'])

df['symbol'] = df['symbol']
df['person'] = df['acquirerName']
df['mode'] = df['acquisitionMode']

# numeric fields
df['buy_qty'] = pd.to_numeric(df['totAcqShare'], errors='coerce').fillna(0)
df['sell_qty'] = pd.to_numeric(df['totSaleShare'], errors='coerce').fillna(0)

# promoter flag
df['is_promoter'] = df['promoterType'].str.contains("promoter", case=False, na=False).astype(int)

# buy/sell direction
df['is_buy'] = df['acqSaleType'].str.contains("buy", case=False, na=False).astype(int)

# -------------------------------
# FILTER ONLY MARKET BUYS
# -------------------------------
df = df[(df['is_buy'] == 1) & (df['buy_qty'] > 0)]

if df.empty:
    raise ValueError("No valid buy transactions")

# -------------------------------
# AGGREGATION
# -------------------------------
agg = df.groupby('symbol').agg({
    'buy_qty': 'sum',
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

agg['final_score'] = (
    0.5 * normalize(agg['buy_qty']) +
    0.3 * normalize(agg['txn_count']) +
    0.2 * (agg['promoter_txn'] > 0).astype(int)
)

top = agg.sort_values('final_score', ascending=False).head(10)

# -------------------------------
# ANALYSIS
# -------------------------------
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

prompt = f"""
Write a professional investor report.

No emojis. No markdown. No mention of AI.

Sections:
Key Observations
Risks
Top 3 Opportunities
Conclusion

Data:
{top.to_string(index=False)}
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

analysis = response.choices[0].message.content

# -------------------------------
# EMAIL
# -------------------------------
top['Rank'] = range(1, len(top)+1)

html_table = top.to_html(index=False)

html = f"""
<html>
<body style="font-family:Arial;background:#f5f7fb;padding:20px;">
<div style="max-width:900px;margin:auto;background:#fff;">
<h2>NSE Insider Trading Report</h2>
<p>{from_date} to {to_date}</p>

{html_table}

<br><br>
{analysis.replace(chr(10), "<br>")}
</div>
</body>
</html>
"""

sender = os.environ.get("EMAIL")
password = os.environ.get("GMAIL_APP_PASSWORD")

msg = MIMEMultipart()
msg["Subject"] = "NSE Insider Report"
msg["From"] = sender
msg["To"] = sender

msg.attach(MIMEText(html, "html"))

server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
server.login(sender, password)
server.sendmail(sender, sender, msg.as_string())
server.quit()

print("Success")
