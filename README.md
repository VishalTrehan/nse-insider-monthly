# NSE Insider Monthly

This project collects insider trading disclosures from the NSE India **Corporate Filings – Insider Trading** page and builds a monthly summary of insider **buys** and **sells** for each listed company. [page:1]

## What it does

- Downloads insider trading data for a selected month from the NSE insider trading API. [page:1]  
- Categorizes each disclosure into Buy or Sell based on transaction type. [web:11]  
- Aggregates total quantities per company/symbol so each stock appears once per bucket. [web:11]  
- Exports CSV files:
  - Full raw insider data for the month.
  - Buy summary (total buy quantity per stock).
  - Sell summary (total sell quantity per stock). [web:11]

Future steps (planned):

- Automatically run on the 2nd of every month.
- Post top 5 insider buys/sells to Telegram, Twitter, and LinkedIn.
- Email full detailed report to newsletter subscribers.

## How to run (Colab)

1. Open Google Colab and clone this repository:
   ```bash
   !git clone https://github.com/VishalTrehan/nse-insider-monthly.git
   %cd nse-insider-monthly
   ```
2. Install Python dependencies:
   ```bash
   !pip install -r requirements.txt
   ```
3. Run the scraper (default is previous month):
   ```bash
   !python insider_scraper.py
   ```

The generated CSV files will appear in the current directory.

## Subscriber System Configuration

The bot automatically reads subscriber email addresses from a Google Sheet and sends newsletters.

### Required Secrets (GitHub Actions)

Add these to `Settings > Secrets and variables > Actions`:

- **SUBSCRIBERS_SHEET_ID**: `1vYZfGm16g-rB8msPuLm2iluQCB3-CXsWEmciNtop2WQ`
  - Stores subscriber email addresses and signup source
  - Connected to subscription form at: https://docs.google.com/forms/d/1BtlBVG0ULykK1swjHwOQVDHmUD26yG_K3HqCoG41GBQ/
  - Responses sheet: NSE Insider Trades - Subscribe for Full Reports (Responses)

- **GMAIL_APP_PASSWORD**: Your Gmail app-specific password (for sending newsletters)

### Subscriber Form

- **Form**: NSE Insider Trades - Subscribe for Full Reports
- **URL**: https://docs.google.com/forms/d/1BtlBVG0ULykK1swjHwOQVDHmUD26yG_K3HqCoG41GBQ/
- **Responses Sheet ID**: 1vYZfGm16g-rB8msPuLm2iluQCB3-CXsWEmciNtop2WQ
- **Columns**:
  - Timestamp: Auto-populated by form
  - Your Email Address: Required field for newsletter signup
  - How did you hear about us?: Tracks signup source (Twitter/X, LinkedIn, Email Newsletter, Other)
  - Name: Optional field for personalization

### Monthly Newsletter Workflow

1. **Data Collection**: Form automatically collects subscriber emails when someone signs up
2. **Email Extraction**: Bot reads SUBSCRIBERS_SHEET_ID to extract all subscriber emails
3. **Report Generation**: Python script generates insider trading report
4. **Newsletter Distribution**: Bot sends personalized emails with PDF report attached
5. **Analytics**: Track which channel (Twitter/X, LinkedIn, Email) drives most signups

### Templates

Email and social media templates available in: NSE Insider Trades - Email & Social Templates
- Email template for full report distribution
- Twitter/X teaser template
- LinkedIn teaser template
