import pandas as pd
import yfinance as yf

# Initialize ticker for Tata Consultancy Services
ticker_symbol = "TCS.NS"
ticker = yf.Ticker(ticker_symbol)

# ---------------------------------------------------------
# 1. Historical Prices for a Date :105Range
# ---------------------------------------------------------
start_date = "2016-10-22"
end_date = "2026-10-22"

# auto_adjust=False keeps both raw Close and dividend/split Adjusted Close
history_df = ticker.history(start=start_date, end=end_date, auto_adjust=False)
print("=== 1. Historical OHLCV Sample ===")
print(history_df[["Open", "High", "Low", "Close", "Adj Close", "Volume"]].head())

# ---------------------------------------------------------
# 2. Dividends Paid: Per Share & Absolute Amounts
# ---------------------------------------------------------
# ticker.dividends gives per-share dividend on ex-date
dividends = ticker.dividends
dividends_filtered = dividends.loc[
    (dividends.index >= pd.to_datetime(start_date).tz_localize(dividends.index.tz))
    & (dividends.index <= pd.to_datetime(end_date).tz_localize(dividends.index.tz))
]

# Fetch share count to compute absolute dividend outflow
shares_out = ticker.info.get("sharesOutstanding")

div_summary = pd.DataFrame({
    "Dividend_Per_Share_INR": dividends_filtered,
    "Estimated_Total_Payout_INR": dividends_filtered * shares_out
})

print("\n=== 2. Dividends Paid (Per Share & Absolute) ===")
print(div_summary)

# ---------------------------------------------------------
# 3. Earnings Per Share (TTM & Historical Quarterly/Annual)
# ---------------------------------------------------------
# Current trailing 12-month EPS snapshot
current_trailing_eps = ticker.info.get("trailingEps")
print(f"\n=== 3. Current TTM EPS: INR {current_trailing_eps} ===")

# Rolling TTM calculation from quarterly statements
q_income = ticker.quarterly_income_stmt
if "Diluted EPS" in q_income.index:
    q_eps = q_income.loc["Diluted EPS"].dropna()
    # Sort chronologically ascending
    q_eps = q_eps.sort_index(ascending=True)
    # Rolling 4-quarter sum to derive exact historical TTM EPS progression
    rolling_ttm_eps = q_eps.rolling(window=4).sum().dropna()
    print("Quarterly Diluted EPS:")
    print(q_eps)
    print("\nHistorical Rolling TTM EPS (4-Quarter Sum):")
    print(rolling_ttm_eps)

# ---------------------------------------------------------
# 4. Forward EPS Estimates (Current & Historical Revisions)
# ---------------------------------------------------------
current_forward_eps = ticker.info.get("forwardEps")
print(f"\n=== 4. Forward EPS Estimates ===")
print(f"Current Forward EPS: INR {current_forward_eps}")

# Consensus estimates for upcoming quarters and years
print("\nConsensus Earnings Estimates (0q = current qtr, +1y = next year):")
try:
    earnings_est = ticker.get_earnings_estimate()
    print(earnings_est)
except Exception as e:
    print("Earnings estimates table not available:", e)

# Historical trend of consensus revisions (current vs 7d, 30d, 90d ago)
print("\nHistorical Trend of EPS Revisions:")
try:
    eps_trend = ticker.get_eps_trend()
    print(eps_trend)
except Exception as e:
    print("EPS trend table not available:", e)

# ---------------------------------------------------------
# 5. Shareholding Distribution
# ---------------------------------------------------------
print("\n=== 5. Shareholding Distribution ===")
# Insider vs Institutional breakdown
print("Major Holders Breakdown:")
print(ticker.major_holders)

# Institutional funds/holdings
print("\nTop Institutional Holders:")
print(ticker.institutional_holders)

# ---------------------------------------------------------
# 6. Analyst Projections: Recommendations & Target Prices
# ---------------------------------------------------------
print("\n=== 6. Analyst Recommendations & Target Prices ===")
# Price targets (Mean, Median, High, Low)
try:
    targets = ticker.analyst_price_targets
    print("Price Targets:")
    for key, val in targets.items():
        print(f"  {key}: {val}")
except Exception as e:
    # Fallback to ticker.info keys
    print("Price Targets (from info):")
    print("  Target Mean:", ticker.info.get("targetMeanPrice"))
    print("  Target High:", ticker.info.get("targetHighPrice"))
    print("  Target Low:", ticker.info.get("targetLowPrice"))

# Recommendation distribution (Strong Buy, Buy, Hold, Sell, Strong Sell)
print("\nRecommendations Summary:")
try:
    print(ticker.recommendations_summary)
except Exception as e:
    print("Recommendations summary not available:", e)