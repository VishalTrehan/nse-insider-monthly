import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime, timedelta
from openai import OpenAI
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# -------------------------------
# 1. FETCH DATA (NSE SAFE METHOD)
# -------------------------------

session = requests.Session()

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive"
}

# Get cookies first
session.get("https://www.nseindia.com", headers=headers)

# Fetch data
url = "https://www.nseindia.com/api/corporates-pit"
response = session.get(url, headers=headers)

data = response.json()
df = pd.json_normalize(data['data'])

# -------------------------------
# 2. CLEAN + STANDARDIZE
# -------------------------------

df.columns = df.columns.str.strip()

rename_map = {
    'acqName': 'person',
    'secVal': 'secVal',
    'secAcq': 'stake_change',
    'dt': 'date'
}

df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

required_cols = ['symbol', 'person', 'secVal', 'stake_change', 'date']
df = df[[c for c in required_cols if c in df.columns]]

# Fill missing safely
if 'stake_change' not in df.columns:
    df['stake_change'] = 0

# -------------------------------
# 3. FILTER LAST MONTH
# -------------------------------

df['date'] = pd.to_datetime(df['date'], errors='coerce')
df = df.dropna(subset=['date'])

today = datetime.today()
first_day = today.replace(day=1)
last_month_end = first_day - timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

df = df[(df['date'] >= last_month_start) & (df['date'] <= last_month_end)]

# -------------------------------
# 4. PROMOTER IDENTIFICATION
# -------------------------------

df['person'] = df['person'].astype(str)
df['is_promoter'] = df['person'].str.contains("promoter", case=False, na=False).astype(int)

# -------------------------------
# 5. AGGREGATION
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
# 6. SCORING
# -------------------------------

def normalize(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

agg['score_value'] = normalize(agg['secVal'])
agg['score_txn'] = normalize(agg['txn_count'])
agg['score_stake'] = normalize(agg['stake_change'])
agg['score_promoter'] = (agg['promoter_txn'] > 0).astype(int)

agg['final_score'] = (
    0.4 * agg['score_value'] +
    0.2 * agg['score_txn'] +
    0.2 * agg['score_stake'] +
    0.2 * agg['score_promoter']
)

top = agg.sort_values('final_score', ascending=False).head(10)

# -------------------------------
# 7. STOP IF NO DATA
# -------------------------------

if top.empty:
    raise ValueError("No insider data fetched for last month. Stopping.")

# -------------------------------
# 8. ANALYSIS (HUMAN STYLE)
# -------------------------------

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

prompt = f"""
You are writing a professional equity research note.

Write in clean, natural language like a human analyst.
Do NOT use markdown, symbols, hashtags, or mention AI.

Structure:

Key Observations:
- Bullet points

Concerns:
- Bullet points

Top Opportunities:
1. Stock name: reasoning
2. Stock name: reasoning
3. Stock name: reasoning

Closing Note:
Short 2–3 line conclusion.

DATA:
{top.to_string(index=False)}
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

analysis = response.choices[0].message.content

# -------------------------------
# 9. FORMAT TABLE
# -------------------------------

top['Rank'] = range(1, len(top) + 1)
top_display = top[['Rank','symbol','secVal','stake_change','txn_count','promoter_txn','final_score']]

html_table = top_display.to_html(index=False, float_format="{:,.2f}".format)

# -------------------------------
# 10. EMAIL HTML (CLEAN UI)
# -------------------------------

html_content = f"""
<html>
<head>
<style>
body {{
    font-family: Arial;
    color: #222;
}}
h2 {{
    background-color: #0b3d91;
    color: white;
    padding: 10px;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin-top: 10px;
}}
th, td {{
    border: 1px solid #ddd;
    padding: 8px;
    text-align: center;
}}
th {{
    background-color: #f2f2f2;
}}
</style>
</head>

<body>

<h2>NSE Insider Trading Report</h2>

<p><b>Period:</b> {last_month_start.date()} to {last_month_end.date()}</p>

<h3>Top Insider Activity</h3>
{html_table}

<h3>Analysis</h3>
<p>{analysis.replace(chr(10), "<br>")}</p>

<br>
<p style="color: gray; font-size: 12px;">
Automated monthly research digest
</p>

</body>
</html>
"""

# -------------------------------
# 11. SEND EMAIL
# -------------------------------

sender = os.environ.get("EMAIL")
password = os.environ.get("GMAIL_APP_PASSWORD")

if not sender or not password:
    raise ValueError("Missing email credentials")

msg = MIMEMultipart("alternative")
msg["Subject"] = "NSE Insider Trading Report"
msg["From"] = sender
msg["To"] = sender

msg.attach(MIMEText(html_content, "html"))

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(sender, password)
server.sendmail(sender, sender, msg.as_string())
server.quit()

print("Report sent successfully")
