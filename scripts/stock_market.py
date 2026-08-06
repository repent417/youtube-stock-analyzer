import yfinance as yf
import re

# 常見股票代號對照表 (台股與熱門美股)
STOCK_NAME_MAP = {
    "6863": "永道-KY",
    "6781": "AES-KY",
    "6456": "GIS-KY",
    "5871": "中租-KY",
    "5243": "乙盛-KY",
    "4991": "環宇-KY",
    "4966": "譜瑞",
    "4958": "臻鼎",
    "3665": "貿聯",
    "2450": "神腦",
    "0050": "元大台灣50",
    "0056": "元大高股息",
    "00679": "元大美債年",
    "00878": "國泰永續高股息",
    "00919": "群益台灣精選高息",
    "00929": "復華台灣科技優息",
    "1215": "卜蜂",
    "1229": "聯華",
    "1308": "亞聚",
    "1326": "台化",
    "1504": "東元",
    "1519": "華城",
    "1537": "廣隆",
    "1582": "信錦",
    "1605": "華新",
    "1711": "永光化學",
    "1717": "長興材料",
    "1773": "勝一",
    "1785": "光洋科",
    "1815": "富喬",
    "2049": "上銀",
    "2059": "川湖",
    "2233": "宇隆",
    "2258": "鴻華先進",
    "2301": "光寶科",
    "2303": "聯電",
    "2308": "台達電",
    "2312": "金寶",
    "2313": "華通",
    "2316": "楠梓電",
    "2317": "鴻海",
    "2327": "國巨",
    "2328": "廣宇科技",
    "2330": "台積電",
    "2331": "精英",
    "2337": "旺宏",
    "2344": "華邦電",
    "2345": "智邦",
    "2351": "順德",
    "2354": "鴻準",
    "2355": "敬鵬",
    "2357": "華碩",
    "2359": "所羅門",
    "2360": "致茂",
    "2367": "燿華電子",
    "2368": "金像電",
    "2374": "佳能",
    "2379": "瑞昱",
    "2382": "廣達",
    "2383": "台光電",
    "2385": "群光電子",
    "2395": "研華",
    "2404": "漢唐",
    "2408": "南亞科",
    "2409": "友達",
    "2417": "圓剛",
    "2421": "建準",
    "2428": "興勤",
    "2436": "偉詮電",
    "2441": "超豐",
    "2449": "京元電子",
    "2454": "聯發科",
    "2472": "立隆電",
    "2481": "強茂",
    "2484": "希華",
    "2485": "兆赫",
    "2489": "瑞軒",
    "2492": "華新科",
    "2520": "冠德",
    "2546": "根基營造",
    "2597": "潤弘",
    "2606": "裕民",
    "2609": "陽明",
    "2645": "長榮航太",
    "2646": "星宇航空",
    "2881": "富邦金",
    "2891": "中信金",
    "2942": "華新科",
    "3004": "豐達科",
    "3006": "晶豪科",
    "3008": "大立光",
    "3013": "晟銘電",
    "3016": "嘉晶",
    "3017": "奇鋐",
    "3019": "亞光",
    "3022": "威強電",
    "3030": "德律",
    "3035": "智原",
    "3037": "欣興電子",
    "3044": "健鼎科技",
    "3060": "銘異",
    "3081": "聯亞",
    "3090": "日貿電",
    "3105": "穩懋",
    "3131": "弘塑",
    "3135": "凌航",
    "3138": "耀登科技",
    "3163": "波若威",
    "3167": "大量科技",
    "3189": "景碩科技",
    "3211": "順達",
    "3217": "優群",
    "3227": "原相科技",
    "3260": "威剛",
    "3264": "欣銓",
    "3265": "台星科",
    "3293": "鈊象電子",
    "3324": "雙鴻",
    "3338": "泰碩",
    "3357": "臺慶科",
    "3363": "上詮",
    "3374": "精材",
    "3376": "新日興",
    "3388": "崇越電",
    "3416": "融程電",
    "3443": "創意",
    "3450": "聯鈞",
    "3455": "由田",
    "3481": "群創",
    "3491": "昇達科",
    "3515": "華擎",
    "3518": "柏騰",
    "3526": "凡甲",
    "3529": "力旺",
    "3533": "嘉澤",
    "3537": "堡達",
    "3563": "牧德",
    "3580": "友威科",
    "3583": "辛耘",
    "3587": "閎康",
    "3653": "健策",
    "3661": "世芯",
    "3663": "鑫科",
    "3673": "力成",
    "3675": "德微",
    "3680": "家登",
    "3701": "大眾控",
    "3702": "大聯大",
    "3706": "神達",
    "3711": "日月光投控",
    "3714": "富采",
    "3715": "定穎投控",
    "4576": "大銀微系統",
    "4577": "達航科技",
    "4585": "達明機器人",
    "4743": "合一",
    "4749": "新應材",
    "4755": "三福化",
    "4763": "材料",
    "4904": "遠傳",
    "4916": "事欣科",
    "4919": "新唐",
    "4931": "新盛力",
    "4971": "英特磊",
    "4979": "華星光",
    "5016": "JX金屬",
    "5269": "祥碩",
    "5274": "信驊",
    "5284": "經寶精密",
    "5289": "宜鼎",
    "5309": "系統電",
    "5314": "世紀",
    "5351": "鈺創科技",
    "5425": "台半",
    "5434": "崇越",
    "5483": "中美晶",
    "5536": "聖暉",
    "5904": "寶雅",
    "6005": "群益證券",
    "6127": "九豪精密陶瓷",
    "6138": "茂達",
    "6139": "亞翔",
    "6147": "頎邦科技",
    "6163": "華電網",
    "6173": "信昌電",
    "6176": "瑞儀光電",
    "6190": "萬泰科",
    "6196": "帆宣",
    "6197": "佳必琪",
    "6202": "盛群",
    "6205": "詮欣",
    "6206": "飛捷",
    "6215": "和椿",
    "6217": "中探針",
    "6218": "豪勉",
    "6223": "旺矽",
    "6231": "系微",
    "6235": "華孚",
    "6239": "力成",
    "6257": "矽格",
    "6274": "台燿",
    "6282": "康舒",
    "6285": "啟碁",
    "6290": "良維",
    "6411": "晶焱科技",
    "6414": "樺漢",
    "6415": "矽力",
    "6426": "統新",
    "6442": "光聖",
    "6488": "環球晶",
    "6510": "精測",
    "6515": "穎崴",
    "6526": "達發科技",
    "6531": "愛普",
    "6533": "晶心科",
    "6548": "長科",
    "6579": "研揚",
    "6584": "南俊國際",
    "6613": "朋億",
    "6640": "均華",
    "6664": "群翊",
    "6667": "信紘科",
    "6672": "騰輝電子",
    "6693": "廣閎科",
    "6719": "力智",
    "6725": "矽科宏晟",
    "6735": "美達科技",
    "6753": "龍德造船",
    "6770": "力積電",
    "6789": "采鈺",
    "6811": "宏碁資訊",
    "6818": "連騰科技",
    "6830": "汎銓",
    "6894": "衛司特",
    "6899": "創為精密",
    "6903": "巨漢",
    "6906": "現觀科",
    "6921": "嘉雨思",
    "6937": "天虹",
    "6944": "兆聯實業",
    "6994": "兆聯實業",
    "7610": "聯友金屬",
    "7703": "銳澤",
    "7711": "永擎",
    "7728": "光焱科技",
    "7734": "印能科技",
    "7750": "新代科技",
    "7769": "鴻勁",
    "7788": "松川精密",
    "7822": "倍利科",
    "7856": "漢測",
    "8021": "尖點",
    "8027": "鈦昇",
    "8033": "雷虎",
    "8039": "台虹",
    "8043": "蜜望實",
    "8046": "南電",
    "8064": "東捷",
    "8069": "元太",
    "8070": "長華",
    "8081": "致新",
    "8098": "慶康科技",
    "8114": "振樺電",
    "8255": "朋程",
    "8261": "富鼎",
    "8271": "宇瞻",
    "8279": "生展",
    "8299": "群聯",
    "8358": "金居",
    "8367": "建新國際",
    "8374": "羅昇",
    "8422": "可寧衛",
    "8463": "潤泰材",
    "8996": "高力",
    "9904": "寶成",
    "9945": "潤泰新",
    "AAPL": "蘋果",
    "AMD": "超微",
    "AMZN": "亞馬遜",
    "AVGO": "博通",
    "FN": "Fabrinet",
    "GOOGL": "谷歌",
    "INTC": "英特爾",
    "MSFT": "微軟",
    "MU": "美光",
    "NVDA": "輝達",
    "TSLA": "特斯拉",
    "TSM": "台積電ADR",
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
