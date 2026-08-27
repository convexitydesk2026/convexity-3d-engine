import yfinance as yf
from datetime import date, timedelta

today = date.today()
dates = {
    'd_250': today - timedelta(days=250),
    'd_200': today - timedelta(days=200),
    'd_150': today - timedelta(days=150),
    'd_100': today - timedelta(days=100),
    'd_50': today - timedelta(days=50),
    'now': today
}

tickers = ['SPY', 'AMZN', 'NVDA', 'GLD', 'QQQ', 'GOOGL', 'AMD', 'TLT', 'AAPL', 'META', 'TSLA', 'XLU', 'MSFT', 'NFLX', 'PLTR', 'SH', 'V', 'DIS', 'IWM']
hist = yf.download(tickers, start=dates['d_250'] - timedelta(days=5), end=today + timedelta(days=5), progress=False)['Close']

def get_price(t, d):
    # Find nearest date
    idx = hist.index.get_indexer([pd.to_datetime(d)], method='nearest')[0]
    return round(float(hist[t].iloc[idx]), 2)

import pandas as pd

print("d_250 to d_200")
print(f"SPY entry {get_price('SPY', dates['d_250'])}, exit {get_price('SPY', dates['d_200'])}")
print(f"AMZN entry {get_price('AMZN', dates['d_250'])}, exit {get_price('AMZN', dates['d_200'])}")
print(f"NVDA entry {get_price('NVDA', dates['d_250'])}, exit {get_price('NVDA', dates['d_200'])}")
print(f"GLD entry {get_price('GLD', dates['d_250'])}, exit {get_price('GLD', dates['d_200'])}")

print("\nd_200 to d_150")
print(f"QQQ entry {get_price('QQQ', dates['d_200'])}, exit {get_price('QQQ', dates['d_150'])}")
print(f"GOOGL entry {get_price('GOOGL', dates['d_200'])}, exit {get_price('GOOGL', dates['d_150'])}")
print(f"AMD entry {get_price('AMD', dates['d_200'])}, exit {get_price('AMD', dates['d_150'])}")
print(f"TLT entry {get_price('TLT', dates['d_200'])}, exit {get_price('TLT', dates['d_150'])}")

print("\nd_150 to d_100")
print(f"AAPL entry {get_price('AAPL', dates['d_150'])}, exit {get_price('AAPL', dates['d_100'])}")
print(f"META entry {get_price('META', dates['d_150'])}, exit {get_price('META', dates['d_100'])}")
print(f"TSLA entry {get_price('TSLA', dates['d_150'])}, exit {get_price('TSLA', dates['d_100'])}")
print(f"XLU entry {get_price('XLU', dates['d_150'])}, exit {get_price('XLU', dates['d_100'])}")

print("\nd_100 to d_50")
print(f"MSFT entry {get_price('MSFT', dates['d_100'])}, exit {get_price('MSFT', dates['d_50'])}")
print(f"NFLX entry {get_price('NFLX', dates['d_100'])}, exit {get_price('NFLX', dates['d_50'])}")
print(f"PLTR entry {get_price('PLTR', dates['d_100'])}, exit {get_price('PLTR', dates['d_50'])}")
print(f"SH entry {get_price('SH', dates['d_100'])}, exit {get_price('SH', dates['d_50'])}")

print("\nd_50 to now")
print(f"V entry {get_price('V', dates['d_50'])}")
print(f"DIS entry {get_price('DIS', dates['d_50'])}")
print(f"IWM entry {get_price('IWM', dates['d_50'])}")
print(f"QQQ entry {get_price('QQQ', dates['d_50'])}")

