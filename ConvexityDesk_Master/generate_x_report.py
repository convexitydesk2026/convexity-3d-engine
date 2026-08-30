import yfinance as yf
from datetime import datetime
import os

def generate_morning_report():
    print("Fetching market data...")
    tickers = ["SPY", "QQQ", "^VIX"]
    
    # Fetch last 5 days to ensure we get the last two trading days (avoids weekend NaNs)
    data = yf.download(tickers, period="5d", interval="1d", progress=False)
    
    # yfinance returns multi-index columns for multiple tickers: data['Close']['SPY']
    close_data = data['Close'].dropna(how='all')
    
    report_lines = [
        "🌅 **Convexity Desk | Morning Market Flow** 🌅\n",
        f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}\n",
        "---",
        "📊 **Macro Levels (Overnight):**"
    ]
    
    try:
        spy_close = float(close_data['SPY'].iloc[-1])
        spy_prev = float(close_data['SPY'].iloc[-2])
        spy_pct = ((spy_close - spy_prev) / spy_prev) * 100
        spy_emoji = "🟢" if spy_pct >= 0 else "🔴"
        report_lines.append(f"• $SPY: ${spy_close:.2f} ({spy_emoji} {spy_pct:+.2f}%)")
        
        qqq_close = float(close_data['QQQ'].iloc[-1])
        qqq_prev = float(close_data['QQQ'].iloc[-2])
        qqq_pct = ((qqq_close - qqq_prev) / qqq_prev) * 100
        qqq_emoji = "🟢" if qqq_pct >= 0 else "🔴"
        report_lines.append(f"• $QQQ: ${qqq_close:.2f} ({qqq_emoji} {qqq_pct:+.2f}%)")
        
        vix_close = float(close_data['^VIX'].iloc[-1])
        vix_prev = float(close_data['^VIX'].iloc[-2])
        vix_pct = ((vix_close - vix_prev) / vix_prev) * 100
        vix_emoji = "🌋" if vix_pct > 5 else ("📉" if vix_pct < -5 else "〰️")
        report_lines.append(f"• $VIX: {vix_close:.2f} ({vix_emoji} {vix_pct:+.2f}%)")
        
    except Exception as e:
        print(f"Error parsing yfinance data: {e}")
        report_lines.append("• Market Data: Unavailable (Check API connection)")

    report_lines.extend([
        "",
        "🎯 **Today's Focus:**",
        "1️⃣ **Episodic Pivots:** Monitoring the EP Waiting Room for RVol > 300%.",
        "2️⃣ **AVWAP Traps:** Waiting for flushes on High-Momentum pullbacks.",
        "3️⃣ **Options Flow:** (Add any anomalous flow seen on the dashboard here).",
        "",
        "Let the market come to you. Never chase. 🛡️",
        "",
        "#Trading #Options #ConvexityDesk #StockMarket"
    ])
    
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "morning_report.md")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    print(f"\nSuccess! X.com Morning Report generated at:\n{output_path}")
    print("\nCopy and paste the contents into X.com.")

if __name__ == "__main__":
    generate_morning_report()
