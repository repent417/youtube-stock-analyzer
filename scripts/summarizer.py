import json
import re
import requests
import time
from pathlib import Path

from config import NOTES_DIR, OLLAMA_HOST, OLLAMA_MODEL, sanitize_filename
from stock_market import get_stock_data, generate_market_table_md, STOCK_NAME_MAP, normalize_ticker

def build_stock_prefix(tickers: list) -> str:
    """從 tickers 建立代號與股名前綴，例如 【2330台積電_NVDA輝達】"""
    if not tickers:
        return ""
    parts = []
    for t in tickers:
        raw_code = str(t).split('.')[0]
        norm = normalize_ticker(str(t))
        name = STOCK_NAME_MAP.get(norm, STOCK_NAME_MAP.get(raw_code, ""))
        if name and name != raw_code:
            parts.append(f"{raw_code}{name}")
        else:
            parts.append(raw_code)
    return f"【{'_'.join(parts)}】"

SYSTEM_PROMPT = """你是一位專業的台股與美股資深證券分析師、法人級投資研究員。
請閱讀傳入的 YouTube 影片資訊與字幕逐字稿內容，進行結構化提煉，並嚴格回傳包含以下欄位的 JSON 格式物件：

{
  "tickers": ["2330.TW", "NVDA"],
  "stock_name_zh": "核心股票中文名稱",
  "summary_title": "簡短專業的投資主題",
  "key_takeaways": [
    "核心重點第一點...",
    "核心重點第二點..."
  ],
  "bullish_reasons": [
    "看多理由與成長動能第一點...",
    "看多理由第二點..."
  ],
  "bearish_reasons": [
    "風險隱憂與疑慮第一點..."
  ],
  "timeline_notes": [
    "[01:23] 時間點關鍵內容摘要...",
    "[05:10] 時間點關鍵內容摘要..."
  ],
  "author_stance": "看多"
}

請確保所有輸出內容均為專業精準的【繁體中文】，欄位值必須確實填寫，不可留空。
僅回傳合法的 JSON 字串。
"""

def generate_summary_with_ollama(info: dict, transcript: str, transcript_source: str = "📜 YouTube CC 字幕") -> dict:
    """使用地端 Ollama (qwen2.5:7b) 進行 100% 離線結構化總結"""
    user_content = f"""
【影片頻道】：{info['channel']}
【影片標題】：{info['title']}
【發布日期】：{info['upload_date']}
【字幕來源】：{transcript_source}

【字幕逐字稿內容】：
{transcript[:3000]}
"""
    url = f"{OLLAMA_HOST}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_ctx": 4096,
            "num_thread": 16
        }
    }
    
    # 設置 600 秒超時，確保 CPU 在高負載下也能穩定產出
    res = requests.post(url, json=payload, timeout=600)
    res.raise_for_status()
    data = res.json()
    content = data["message"]["content"]
    
    json_data = json.loads(content)
    return parse_json_to_markdown(info, json_data, transcript_source)


def format_field(val) -> str:
    if isinstance(val, list):
        return "\n".join([f"- {item}" for item in val])
    return str(val) if val else "無"

def parse_json_to_markdown(info: dict, data: dict, transcript_source: str) -> dict:
    raw_tickers = data.get("tickers", [])
    clean_tickers = []
    if isinstance(raw_tickers, list):
        for item in raw_tickers:
            if isinstance(item, list):
                clean_tickers.extend([str(x).strip() for x in item if str(x).strip()])
            elif item:
                clean_tickers.append(str(item).strip())
    tickers = clean_tickers
    
    # 抓取即時市場數據與股價表格
    stock_market_table = ""
    if tickers:
        stock_data = get_stock_data(tickers)
        stock_market_table = generate_market_table_md(stock_data)
        
    stock_prefix = build_stock_prefix(tickers)
    
    key_takeaways = format_field(data.get('key_takeaways'))
    bullish_reasons = format_field(data.get('bullish_reasons'))
    bearish_reasons = format_field(data.get('bearish_reasons'))
    timeline_notes = format_field(data.get('timeline_notes'))
    
    # 建立 Markdown 筆記內文
    final_md = f"""# {info['title']}

- **頻道名稱**：{info['channel']}
- **發布日期**：{info['upload_date']}
- **影片連結**：[{info['title']}]({info['url']})
- **逐字稿來源**：{transcript_source}
- **分析標的**：{', '.join(tickers) if tickers else '無特別標的'}
- **創作者立場**：`{data.get('author_stance', '中立')}`

---

## 📊 即時行情與估值數據
{stock_market_table if stock_market_table else '*(未包含特定個股數據)*'}

---

## 🎯 核心投資精華
{key_takeaways}

---

## ⚖️ 多空論點對比分析

### 🟢 看多動能與利多因素
{bullish_reasons}

### 🔴 風險隱憂與看空疑慮
{bearish_reasons}

---

## ⏱️ 時間軸與重點摘要
{timeline_notes}

---
*註：本筆記由地端 AI (Qwen2.5) 自動提煉分析，僅供研究參考，不構成任何投資建議。*
"""
    return {
        'tickers': tickers,
        'stock_prefix': stock_prefix,
        'final_md': final_md
    }

def generate_summary(info: dict, transcript: str, transcript_source: str = "📜 YouTube CC 字幕") -> dict:
    """純地端模式：由地端 Ollama (qwen2.5:7b) 完全離線處理"""
    print(f"🤖 [純地端 AI] 正在由 Ollama ({OLLAMA_MODEL}) 進行 16 執行緒 CPU 重點提煉...")
    return generate_summary_with_ollama(info, transcript, transcript_source)

def save_note(channel: str, date: str, title: str, content: str, tickers: list = None) -> Path:
    """寫入 影片筆記/<頻道名稱>/<日期>_【<股票代號股名>】_<標題>.md"""
    clean_channel = sanitize_filename(channel)
    clean_title = sanitize_filename(title)
    
    channel_dir = NOTES_DIR / clean_channel
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    stock_prefix = build_stock_prefix(tickers)
    
    if stock_prefix:
        filename = f"{date}_{stock_prefix}_{clean_title}.md"
    else:
        filename = f"{date}_{clean_title}.md"
        
    file_path = channel_dir / filename
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return file_path
