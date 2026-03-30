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
# 1. FETCH DATA FROM NSE
# -------------------------------

url = "https://www.nseindia.com/api/corporates-pit"
headers = {"User-Agent": "Mozilla/5.0"}

response = requests.get(url, headers=headers)
data = response.json()
df = pd.json_normalize(data['data'])

# -------------------------------
# 2. STANDARDIZE COLUMNS (ROBUST)
# -------------------------------

df.columns = df.columns.str.strip()

column_map = {
    'symbol': 'symbol',
    'acqName': 'person',
    'secVal': 'secVal',
    'secAcq': 'stake_change',
    'stake_change': 'stake_change',
    'modeOfAcquisition': 'mode',
    'mode': 'mode',
    'acqType': 'txn_type',
    'txn_type': 'txn_type',
    'dt': 'date',
    'date': 'date'
}

df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})

required_cols = ['symbol', 'person', 'secVal', 'stake_change', 'date']
df = df[[c for c in required_cols if c in df.columns]]

# Fill missing columns safely
if 'stake_change' not in df.columns:
    df['stake_change'] = 0

# -------------------------------
# 3. DATE FILTER (LAST MONTH)
# -------------------------------

df['date'] = pd.to_datetime(df['date'], errors='coerce')
df = df.dropna(subset=['date'])

today = datetime.today()
first_day_this_month = today.replace(day=1)
last_month_end = first_day_this_month - timedelta(days=1)
last_month_start = last_month_end.replace(day=1)

df = df[(df['date'] >= last_month_start) & (df['date'] <= last_month_end)]

# -------------------------------
# 4. PROMOTER IDENTIFICATION (SAFE)
# -------------------------------

df['person'] = df['person'].astype(str)

df['is_promoter'] = df['person'].str.contains(
    'promoter', case=False, na=False
).astype(int)

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
# 6. SCORING SYSTEM
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
# 7. AI ANALYSIS
# -------------------------------

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

prompt = f"""
You are a professional equity research analyst.

Analyze this insider trading dataset and provide:

1. Key bullish signals
2. Any red flags
3. Top 3 stock ideas with reasoning
4. Final takeaway for investors

Keep it crisp and structured.

DATA:
{top.to_string(index=False)}
"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

analysis = response.choices[0].message.content

# -------------------------------
# 8. FORMAT HTML EMAIL
# -------------------------------

def highlight_top(df):
    df = df.copy()
    df['Rank'] = range(1, len(df) + 1)
    return df[['Rank','symbol','secVal','stake_change','txn_count','promoter_txn','final_score']]

styled_df = highlight_top(top)

html_table = styled_df.to_html(index=False, float_format="{:,.2f}".format)

html_content = f"""
<html>
<body style="font-family: Arial;">

<h2>📊 NSE Insider Trading Report (Monthly)</h2>

<p><b>Period:</b> {last_month_start.date()} to {last_month_end.date()}</p>

<h3>🏆 Top Insider Signals</h3>
{html_table}

<h3>🧠 AI Insights</h3>
<div style="white-space: pre-wrap; font-size:14px;">
{analysis}
</div>

<hr>
<p style="color:gray;">Generated automatically via GitHub Actions</p>

</body>
</html>
"""

# -------------------------------
# 9. SEND EMAIL
# -------------------------------

sender = os.environ.get("EMAIL")
password = os.environ.get("GMAIL_APP_PASSWORD")

msg = MIMEMultipart("alternative")
msg["Subject"] = "📊 Monthly Insider Trading Report"
msg["From"] = sender
msg["To"] = sender

msg.attach(MIMEText(html_content, "html"))

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(sender, password)
server.sendmail(sender, sender, msg.as_string())
server.quit()

print("✅ Email sent successfully")
