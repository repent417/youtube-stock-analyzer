import yfinance as yf
import re

def normalize_ticker(symbol: str) -> str:
    """清理並標準化股票代號 (支援台股與美股)"""
    symbol = symbol.strip().upper()
    # 移除常規字首字尾，例如 # 或 $
    symbol = re.sub(r'[#\$]', '', symbol)
    
    # 判斷是否為台股 (4位或5位純數字，如 2330, 0050, 2454)
    if re.match(r'^\d{4,5}$', symbol):
        return f"{symbol}.TW"
    return symbol

def get_stock_data(symbols: list[str]) -> list[dict]:
    """獲取提及股票的即時市場數據"""
    results = []
    seen = set()
    
    for raw in symbols:
        ticker_str = normalize_ticker(raw)
        if ticker_str in seen:
            continue
        seen.add(ticker_str)
        
        try:
            stock = yf.Ticker(ticker_str)
            info = stock.info
            
            # 若取得無效 info 則跳過
            if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info and 'previousClose' not in info):
                continue
                
            name = info.get('shortName', info.get('longName', ticker_str))
            price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
            change_pct = info.get('regularMarketChangePercent', 0.0)
            high_52 = info.get('fiftyTwoWeekHigh', 'N/A')
            low_52 = info.get('fiftyTwoWeekLow', 'N/A')
            pe_ratio = info.get('trailingPE', info.get('forwardPE', 'N/A'))
            currency = info.get('currency', '')
            
            # 格式化數字
            currency_prefix = "NT$" if currency == "TWD" else ("US$" if currency == "USD" else currency)
            price_str = f"{currency_prefix} {price:,.2f}" if isinstance(price, (int, float)) and price > 0 else "N/A"
            change_str = f"{change_pct:+.2f}%" if isinstance(change_pct, (int, float)) else "N/A"
            high_low_str = f"{currency_prefix} {high_52} / {low_52}" if high_52 != 'N/A' else "N/A"
            pe_str = f"{pe_ratio:.1f}" if isinstance(pe_ratio, (int, float)) else "N/A"
            
            results.append({
                'raw': raw,
                'ticker': ticker_str,
                'name': name,
                'price': price_str,
                'change': change_str,
                'high_low': high_low_str,
                'pe': pe_str
            })
        except Exception as e:
            print(f"ℹ️ 無法抓取 {ticker_str} 股票數據: {e}")
            
    return results

def generate_market_table_md(stock_data: list[dict]) -> str:
    """將即時股價資料轉換為 Markdown 表格"""
    if not stock_data:
        return "（未抓取到即時市場數據或無指定標的）"
        
    lines = [
        "| 股票代號/名稱 | 即時股價 | 今日漲跌幅 | 52週最高 / 最低 | 本益比 P/E |",
        "| :--- | :--- | :--- | :--- | :--- |"
    ]
    for d in stock_data:
        lines.append(f"| **{d['name']} ({d['ticker']})** | {d['price']} | {d['change']} | {d['high_low']} | {d['pe']} |")
        
    return "\n".join(lines)
