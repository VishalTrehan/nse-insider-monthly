import requests
import pandas as pd
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

BASE_URL = "https://www.nseindia.com"
API_URL = BASE_URL + "/api/corporates-pit"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading",
}

def get_month_range(target_year=None, target_month=None):
    """
    Returns (start_date, end_date) for a given month.
    If nothing passed, returns previous calendar month.
    """
    today = date.today()
    if target_year is None or target_month is None:
        first_day_this_month = date(today.year, today.month, 1)
        last_day_prev_month = first_day_this_month - timedelta(days=1)
        first_day_prev_month = date(last_day_prev_month.year, last_day_prev_month.month, 1)
        start, end = first_day_prev_month, last_day_prev_month
    else:
        start = date(target_year, target_month, 1)
        end = (start + relativedelta(months=1)) - timedelta(days=1)
    return start, end

def fetch_insider_data(start_date, end_date):
    """
    Fetches all insider trading rows between start_date and end_date
    from NSE insider trading API, handling pagination.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    # Initial call to set cookies
    session.get(BASE_URL, timeout=20)

    all_rows = []
    page_no = 1

    while True:
        params = {
            "index": "equities",
            "from_date": start_date.strftime("%d-%m-%Y"),
            "to_date": end_date.strftime("%d-%m-%Y"),
            "page": page_no,
        }
        print(f"Requesting page {page_no} ...")
        r = session.get(API_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        rows = data.get("data", [])
        if not rows:
            break
        all_rows.extend(rows)
        page_no += 1

    return all_rows

def preprocess_df(rows):
    """
    Normalizes raw JSON rows into a clean DataFrame with
    SYMBOL, COMPANY_NAME, NO_OF_SECURITIES, TRANSACTION_TYPE and dates.
    """
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Look at typical keys used in NSE insider JSON. Adjust if needed. [web:11]
    col_map = {
        "symbol": "SYMBOL",
        "symbolName": "SYMBOL",
        "company": "COMPANY_NAME",
        "companyName": "COMPANY_NAME",
        "secAcq": "NO_OF_SECURITIES",
        "securitiesAcquired": "NO_OF_SECURITIES",
        "secType": "SECURITY_TYPE",
        "acqMode": "ACQ_MODE",
        "remarks": "REMARKS",
        "acqFromDt": "ACQ_FROM_DATE",
        "acqToDt": "ACQ_TO_DATE",
        "intimDt": "INTIMATION_DATE",
        "acqDisposal": "TRANSACTION_TYPE",   # Buy / Sell etc.
    }

    rename_dict = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    # Quantity cleaning
    if "NO_OF_SECURITIES" in df.columns:
        df["NO_OF_SECURITIES"] = (
            df["NO_OF_SECURITIES"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace(" ", "", regex=False)
            .replace("", "0")
        )
        df["NO_OF_SECURITIES"] = pd.to_numeric(df["NO_OF_SECURITIES"], errors="coerce").fillna(0)
    else:
        df["NO_OF_SECURITIES"] = 0.0

    # Normalise transaction type
    if "TRANSACTION_TYPE" in df.columns:
        df["TRANSACTION_TYPE"] = df["TRANSACTION_TYPE"].astype(str).str.upper()
    else:
        df["TRANSACTION_TYPE"] = ""

    # Fallback for symbol & company
    if "SYMBOL" not in df.columns:
        df["SYMBOL"] = df.get("symbol", "")
    if "COMPANY_NAME" not in df.columns:
        df["COMPANY_NAME"] = df.get("company", "")

    return df

def build_summaries(df):
    """
    Splits into buy and sell buckets and aggregates quantity per SYMBOL+COMPANY.
    """
    if df.empty:
        return df, df

    # Simple rule: anything containing 'BUY' vs 'SELL'
    buy_df = df[df["TRANSACTION_TYPE"].str.contains("BUY", na=False)]
    sell_df = df[df["TRANSACTION_TYPE"].str.contains("SELL", na=False)]

    group_cols = ["SYMBOL", "COMPANY_NAME"]

    buy_summary = (
        buy_df.groupby(group_cols, as_index=False)["NO_OF_SECURITIES"]
        .sum()
        .rename(columns={"NO_OF_SECURITIES": "TOTAL_BUY_QTY"})
        .sort_values("TOTAL_BUY_QTY", ascending=False)
    )

    sell_summary = (
        sell_df.groupby(group_cols, as_index=False)["NO_OF_SECURITIES"]
        .sum()
        .rename(columns={"NO_OF_SECURITIES": "TOTAL_SELL_QTY"})
        .sort_values("TOTAL_SELL_QTY", ascending=False)
    )

    return buy_summary, sell_summary

def main(target_year=None, target_month=None, output_prefix="output"):
    start, end = get_month_range(target_year, target_month)
    print(f"Fetching insider data from {start} to {end}")

    rows = fetch_insider_data(start, end)
    print(f"Total raw rows fetched: {len(rows)}")

    df = preprocess_df(rows)
    print(f"Dataframe shape after preprocess: {df.shape}")

    buy_summary, sell_summary = build_summaries(df)

    # Filenames
    raw_path = f"{output_prefix}_raw_{start}_{end}.csv"
    buy_path = f"{output_prefix}_buy_summary_{start}_{end}.csv"
    sell_path = f"{output_prefix}_sell_summary_{start}_{end}.csv"

    df.to_csv(raw_path, index=False)
    buy_summary.to_csv(buy_path, index=False)
    sell_summary.to_csv(sell_path, index=False)

    print("Saved CSV files:")
    print(raw_path)
    print(buy_path)
    print(sell_path)

if __name__ == "__main__":
    # Default behaviour: previous month (good for running on 2nd of each month).
    main()
