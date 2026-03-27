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
