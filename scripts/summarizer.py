import json
import re
import requests
import time
from pathlib import Path

from config import (
    NOTES_DIR, 
    DEEPSEEK_API_KEY, 
    DEEPSEEK_BASE_URL, 
    DEEPSEEK_MODEL, 
    OLLAMA_HOST, 
    OLLAMA_MODEL, 
    sanitize_filename
)
from stock_market import get_stock_data, generate_market_table_md, STOCK_NAME_MAP, normalize_ticker

def build_stock_prefix(tickers: list, stock_name_zh: str = "") -> str:
    """從 tickers 建立代號與股名前綴，例如 【2330台積電_NVDA輝達】 或 【8039台虹】"""
    if not tickers:
        return ""
    parts = []
    for t in tickers:
        raw_code = str(t).split('.')[0]
        norm = normalize_ticker(str(t))
        name = STOCK_NAME_MAP.get(norm, STOCK_NAME_MAP.get(raw_code, ""))
        if not name and stock_name_zh:
            clean_zh = re.sub(r'\(.*?\)|（.*?）|\d+', '', stock_name_zh).strip()
            if clean_zh:
                name = clean_zh
        if name and name != raw_code:
            parts.append(f"{raw_code}{name}")
        else:
            parts.append(raw_code)
    return f"【{'_'.join(parts)}】"


SYSTEM_PROMPT = """你是一位專業的台股與美股資深證券分析師、法人級投資研究員。
請深度閱讀傳入的 YouTube 影片資訊與全量逐字稿內容，進行結構化提煉，並嚴格回傳包含以下欄位的 JSON 格式物件：

{
  "tickers": ["2330.TW", "NVDA"],
  "stock_name_zh": "核心股票中文名稱",
  "summary_title": "簡短專業的投資主題",
  "key_takeaways": [
    "核心投資重點第一點...",
    "核心投資重點第二點...",
    "核心投資重點第三點..."
  ],
  "bullish_reasons": [
    "看多動能與利多因素第一點...",
    "看多動能第二點..."
  ],
  "bearish_reasons": [
    "風險隱憂與疑慮第一點...",
    "風險隱憂第二點..."
  ],
  "timeline_notes": [
    "[01:23] 時間點關鍵內容摘要...",
    "[05:10] 時間點關鍵內容摘要..."
  ],
  "author_stance": "看多"
}

請確保所有輸出內容均為專業精準的【繁體中文】，內容必須深入且具體（包含財務數字、展望、產業邏輯），不可粗略敷衍。
僅回傳合法的 JSON 物件。
"""

def generate_summary_with_deepseek(info: dict, transcript: str, transcript_source: str = "📜 YouTube CC 字幕") -> dict:
    """使用極速且強大的 DeepSeek API (deepseek-chat V3) 進行法人級結構化總結"""
    user_content = f"""
【影片頻道】：{info['channel']}
【影片標題】：{info['title']}
【發布日期】：{info['upload_date']}
【字幕來源】：{transcript_source}

【全量字幕逐字稿內容】：
{transcript[:60000]}
"""
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 4096
    }
    
    res = requests.post(url, headers=headers, json=payload, timeout=60)
    res.raise_for_status()
    data = res.json()
    content = data["choices"][0]["message"]["content"]
    
    json_data = json.loads(content)
    return parse_json_to_markdown(info, json_data, transcript_source, engine_label="🚀 DeepSeek AI (V3)")

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
    
    res = requests.post(url, json=payload, timeout=600)
    res.raise_for_status()
    data = res.json()
    content = data["message"]["content"]
    
    json_data = json.loads(content)
    return parse_json_to_markdown(info, json_data, transcript_source, engine_label="🤖 地端 Qwen2.5 7B")

def format_field(val) -> str:
    if isinstance(val, list):
        return "\n".join([f"- {item}" for item in val])
    return str(val) if val else "無"

def parse_json_to_markdown(info: dict, data: dict, transcript_source: str, engine_label: str = "🚀 DeepSeek AI") -> dict:
    raw_tickers = data.get("tickers", [])
    clean_tickers = []
    if isinstance(raw_tickers, list):
        for item in raw_tickers:
            if isinstance(item, list):
                clean_tickers.extend([str(x).strip() for x in item if str(x).strip()])
            elif item:
                clean_tickers.append(str(item).strip())
    tickers = clean_tickers
    
    stock_name_zh = data.get("stock_name_zh", "")
    
    # 抓取即時市場數據與股價表格
    stock_market_table = ""
    if tickers:
        stock_data = get_stock_data(tickers)
        stock_market_table = generate_market_table_md(stock_data)
        
    stock_prefix = build_stock_prefix(tickers, stock_name_zh=stock_name_zh)
    
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

### 🔴 風險隱誘與看空疑慮
{bearish_reasons}

---

## ⏱️ 時間軸與重點摘要
{timeline_notes}

---
*註：本筆記由 {engine_label} 自動提煉分析，僅供研究參考，不構成任何投資建議。*
"""
    return {
        'tickers': tickers,
        'stock_name_zh': stock_name_zh,
        'stock_prefix': stock_prefix,
        'final_md': final_md
    }

def generate_summary(info: dict, transcript: str, transcript_source: str = "📜 YouTube CC 字幕") -> dict:
    """優先使用 DeepSeek API (極速/高品質)，若未設定 Key 或網路失敗則備援至地端 Ollama"""
    if DEEPSEEK_API_KEY:
        try:
            print(f"🚀 [DeepSeek AI] 正在發送全量逐字稿至 DeepSeek API ({DEEPSEEK_MODEL}) 進行法人級提煉...")
            return generate_summary_with_deepseek(info, transcript, transcript_source)
        except Exception as e:
            print(f"⚠️ DeepSeek API 呼叫失敗 ({e})，切換至地端 Ollama 備援...")
            
    print(f"🤖 [地端 AI] 正在由 Ollama ({OLLAMA_MODEL}) 進行重點提煉...")
    return generate_summary_with_ollama(info, transcript, transcript_source)

def save_note(channel: str, date: str, title: str, content: str, tickers: list = None, stock_name_zh: str = "") -> Path:
    """寫入 影片筆記/<頻道名稱>/<日期>_【<股票代號股名>】_<標題>.md"""
    clean_channel = sanitize_filename(channel)
    clean_title = sanitize_filename(title)
    
    channel_dir = NOTES_DIR / clean_channel
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    stock_prefix = build_stock_prefix(tickers, stock_name_zh=stock_name_zh)
    
    if stock_prefix:
        filename = f"{date}_{stock_prefix}_{clean_title}.md"
    else:
        filename = f"{date}_{clean_title}.md"
        
    file_path = channel_dir / filename
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return file_path

