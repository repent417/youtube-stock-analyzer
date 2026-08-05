import yfinance as yf
import re

# 常見股票代號對照表 (台股與熱門美股)
STOCK_NAME_MAP = {
    # 台股上市 / 上櫃熱門個股
    "1537": "廣隆",
    "2303": "聯電",
    "2330": "台積電",
    "2337": "旺宏",
    "2360": "致茂",
    "2409": "友達",
    "2441": "超豐",
    "2454": "聯發科",
    "2317": "鴻海",
    "2308": "台達電",
    "2382": "廣達",
    "3035": "智原",
    "3105": "穩懋",
    "3211": "順達",
    "3231": "緯創",
    "3264": "欣銓",
    "3443": "創意",
    "3526": "凡甲",
    "3661": "世芯KY",
    "3711": "日月光投控",
    "4919": "新唐",
    "6139": "亞翔",
    "6202": "盛群",
    "6239": "力成",
    "6510": "精測",
    "6669": "緯穎",
    "7769": "鴻勁",
    "8039": "台虹",
    "2404": "漢唐",
    "6725": "矽科宏晟",
    "6414": "樺漢",
    "6770": "力積電",
    "3034": "聯詠",
    "2379": "瑞昱",
    "2357": "華碩",
    "2356": "英業達",
    "2383": "台光電",
    "6213": "聯茂",
    "2368": "金像電",
    "3533": "嘉澤",
    "3017": "奇鋐",
    "3324": "雙鴻",
    "2345": "智邦",
    "2451": "創見",
    "3413": "京鼎",
    "3583": "辛耘",
    "6187": "萬潤",
    "3131": "弘塑",

    "0050": "元大台灣50",
    "0056": "元大高股息",
    "00878": "國泰永續高股息",
    "00919": "群益台灣精選高息",
    "00929": "復華台灣科技優息",


    # 美股與半導體巨頭
    "NVDA": "輝達",
    "TSLA": "特斯拉",
    "AAPL": "蘋果",
    "MSFT": "微軟",
    "GOOGL": "谷歌",
    "AMD": "超微",
    "AMZN": "亞馬遜",
    "MU": "美光",
    "INTC": "英特爾",
    "AVGO": "博通",
    "FN": "Fabrinet",
    "TSM": "台積電ADR"
}

def normalize_ticker(symbol: str) -> str:
    """清理並標準化股票代號 (支援台股與美股)"""
    symbol = symbol.strip().upper()
    symbol = re.sub(r'[#\$]', '', symbol)
    
    # 判斷是否為台股 (4位或5位純數字)
    if re.match(r'^\d{4,5}$', symbol):
        return f"{symbol}.TW"
    return symbol

def fetch_yfinance_info(ticker_str: str) -> tuple[dict, str]:
    """獲取 yfinance info，包含台股上市 (.TW) 與上櫃 (.TWO) 的自動備援處理"""
    try:
        stock = yf.Ticker(ticker_str)
        info = stock.info
        if info and ('regularMarketPrice' in info or 'currentPrice' in info or 'previousClose' in info):
            return info, ticker_str
    except Exception:
        pass

    # 若為台股 .TW 但失敗，嘗試上櫃 (.TWO)
    if ticker_str.endswith(".TW"):
        otc_ticker = ticker_str.replace(".TW", ".TWO")
        try:
            stock = yf.Ticker(otc_ticker)
            info = stock.info
            if info and ('regularMarketPrice' in info or 'currentPrice' in info or 'previousClose' in info):
                return info, otc_ticker
        except Exception:
            pass

    return {}, ticker_str

def get_clean_stock_info(symbol: str) -> tuple[str, str]:
    """
    傳回 (代號簡稱, 股票中文/簡稱)
    例如: "2337.TW" -> ("2337", "旺宏")
          "NVDA" -> ("NVDA", "輝達")
    """
    raw_symbol = re.sub(r'[#\$]', '', symbol.strip().upper())
    clean_code = raw_symbol.replace('.TW', '').replace('.TWO', '')
    
    # 1. 優先查常規字典
    if clean_code in STOCK_NAME_MAP:
        return clean_code, STOCK_NAME_MAP[clean_code]
        
    # 2. 次之透過 yfinance 獲取 shortName
    try:
        norm_ticker = normalize_ticker(symbol)
        info, _ = fetch_yfinance_info(norm_ticker)
        short_name = info.get('shortName', clean_code)
        # 清理多餘字樣
        short_name = re.sub(r'INC|CORP|LTD|CO|COMPANY|\.|\,', '', short_name, flags=re.IGNORECASE).strip()
        return clean_code, short_name if short_name else clean_code
    except Exception:
        return clean_code, clean_code

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
            info, actual_ticker = fetch_yfinance_info(ticker_str)
            
            if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info and 'previousClose' not in info):
                continue
                
            code, clean_name = get_clean_stock_info(raw)
            display_name = f"{clean_name} ({code})" if clean_name != code else info.get('shortName', code)
            
            price = info.get('currentPrice', info.get('regularMarketPrice', 0.0))
            change_pct = info.get('regularMarketChangePercent', 0.0)
            high_52 = info.get('fiftyTwoWeekHigh', 'N/A')
            low_52 = info.get('fiftyTwoWeekLow', 'N/A')
            pe_ratio = info.get('trailingPE', info.get('forwardPE', 'N/A'))
            currency = info.get('currency', '')
            
            currency_prefix = "NT$" if currency == "TWD" else ("US$" if currency == "USD" else currency)
            price_str = f"{currency_prefix} {price:,.2f}" if isinstance(price, (int, float)) and price > 0 else "N/A"
            change_str = f"{change_pct:+.2f}%" if isinstance(change_pct, (int, float)) else "N/A"
            high_low_str = f"{currency_prefix} {high_52} / {low_52}" if high_52 != 'N/A' else "N/A"
            pe_str = f"{pe_ratio:.1f}" if isinstance(pe_ratio, (int, float)) else "N/A"
            
            results.append({
                'raw': raw,
                'ticker': actual_ticker,
                'code': code,
                'clean_name': clean_name,
                'name': display_name,
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
        lines.append(f"| **{d['name']}** | {d['price']} | {d['change']} | {d['high_low']} | {d['pe']} |")
        
    return "\n".join(lines)
