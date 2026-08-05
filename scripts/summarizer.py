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

SYSTEM_PROMPT = """你是一位法人級台股與美股證券分析師、頂尖投資研究員。
請深度閱讀傳入的 YouTube 影片資訊與全量逐字稿內容，進行結構化提煉，並嚴格回傳包含以下欄位的 JSON 格式物件：

{
  "tickers": ["3211.TW"],
  "stock_name_zh": "順達",
  "summary_title": "順達(3211) ：AI備援電力轉型與資產重估報告",
  "tags": ["#順達3211", "#AI備援電力", "#BBU電池模組", "#資產重估", "#AI伺服器"],
  "author_stance": "🟢 看多 (Bullish)",
  "core_summary": "順達 (3211) 正從傳統筆記型電腦 (NB) 鋰電池模組廠，加速轉型為高毛利的 AI 伺服器 BBU (備援電池系統) 供應商。",
  "catalysts": [
    "**AI 伺服器 BBU 滲透率爆發**：AI 伺服器功耗顯著增加，傳統 UPS 響應時間無法滿足需求，BBU 成為必備備援方案，大幅提升產品平均售價 (ASP) 與毛利率。",
    "**資產重估與開發價值**：持有精華區土地資產 (如龜山廠區等)，隨著資產活化與重估，將帶來一次性收益及公司每股淨值 (NAV) 的顯著提升。",
    "**高股利政策**：傳統業務現金流穩定，高配息特性提供下檔防禦價值。"
  ],
  "key_levels": "* **關鍵支撐位**：實體 K 線底部與均線支撐區間\\n* **關鍵壓力位**：波段前高與整數字數關卡\\n* **風控停損點**：跌破關鍵支撐區間或 AI BBU 出貨進度不如預期",
  "bullish_reasons": [
    "AI 伺服器 BBU 需求強勁，產品組合優化大幅拉升毛利率。",
    "精華區土地資產重估價值極高，為 NAV 帶來大幅跳升空間。",
    "入侵門檻高，且已打入核心伺服器供應鏈。"
  ],
  "bearish_reasons": [
    "傳統 NB/消費性電子需求疲弱，傳統電池模組成長趨緩。",
    "資產處分時間點具不確定性，一次性獲利難以維持常態本益比。",
    "電池模組同業競爭加劇，可能引發價格戰拉低毛利。"
  ],
  "timeline_notes": [
    "[00:00] 報告背景介紹與順達 (3211) 轉型契機",
    "[01:30] AI 伺服器電力痛點與 BBU (備援電池) 趨勢解析",
    "[03:45] 資產重估價值與土地活化潛在效益評估",
    "[05:20] 財務結構、配息能力與投資結論"
  ]
}

請確保所有欄位均為專業精準的【繁體中文】JSON。內容必須深入且具體（包含財務數字、展望、產業邏輯），不可粗略敷衍。
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
    
    # 1. 抓取即時市場數據與股價表格
    stock_market_table = ""
    if tickers:
        stock_data = get_stock_data(tickers)
        stock_market_table = generate_market_table_md(stock_data)
        
    stock_prefix = build_stock_prefix(tickers, stock_name_zh=stock_name_zh)
    
    # 2. 處理提及標的與主題標籤 (Obsidian Hashtags)
    raw_tags = data.get("tags", [])
    formatted_tags_list = []
    if isinstance(raw_tags, list) and raw_tags:
        for tag in raw_tags:
            tag_str = str(tag).strip()
            if not tag_str.startswith("#"):
                tag_str = f"#{tag_str}"
            formatted_tags_list.append(f"`{tag_str}`")
    elif tickers:
        for t in tickers:
            raw_code = str(t).split('.')[0]
            name = STOCK_NAME_MAP.get(normalize_ticker(str(t)), STOCK_NAME_MAP.get(raw_code, stock_name_zh))
            tag_name = f"{name}{raw_code}" if name and name != raw_code else raw_code
            formatted_tags_list.append(f"`#{tag_name}`")
            
    tags_str = " ".join(formatted_tags_list) if formatted_tags_list else "`#股票分析`"
    
    # 3. 格式化催化劑 (Catalysts) 列表
    raw_catalysts = data.get("catalysts", [])
    catalysts_formatted = ""
    if isinstance(raw_catalysts, list) and raw_catalysts:
        catalysts_formatted = "\n".join([f"1. {item}" for item in raw_catalysts])
    else:
        catalysts_formatted = str(data.get("catalysts", "暫無明顯催化劑"))

    # 4. 格式化多空對比表格
    bullish_list = data.get('bullish_reasons', [])
    bearish_list = data.get('bearish_reasons', [])
    if isinstance(bullish_list, str): bullish_list = [bullish_list]
    if isinstance(bearish_list, str): bearish_list = [bearish_list]
    
    comparison_rows = []
    max_len = max(len(bullish_list), len(bearish_list), 1)
    dimensions = ["**業務轉型/成長動能**", "**資產價值/財務結構**", "**產業競爭/大環境風險**", "**營運發展與展望**"]
    
    for i in range(max_len):
        dim = dimensions[i] if i < len(dimensions) else f"**指標觀點 {i+1}**"
        b_val = bullish_list[i] if i < len(bullish_list) else "無特別說明"
        r_val = bearish_list[i] if i < len(bearish_list) else "無特別說明"
        comparison_rows.append(f"| {dim} | {b_val} | {r_val} |")
        
    comparison_table = "\n".join(comparison_rows)

    # 5. 格式化時間軸標記
    raw_timeline = data.get('timeline_notes', [])
    timeline_formatted = ""
    if isinstance(raw_timeline, list) and raw_timeline:
        timeline_formatted = "\n".join([f"* `{item.strip()}`" if not item.strip().startswith("*") else item.strip() for item in raw_timeline])
    else:
        timeline_formatted = "* `[00:00]` 報告開始"

    summary_title = data.get('summary_title', info['title'])
    core_summary = data.get('core_summary', '無重點摘要')
    key_levels = data.get('key_levels', '* **關鍵支撐位**：均線支撐區間\n* **關鍵壓力位**：整數字數關卡\n* **風控停損點**：跌破關鍵支撐區間')
    author_stance = data.get('author_stance', '🟢 看多 (Bullish)')

    # 建立完美的 Obsidian 精美研報 Markdown 筆記
    final_md = f"""# 【股票分析】{summary_title}
- **頻道/創作者**：{info['channel']}
- **發布日期**：{info['upload_date']}
- **影片連結**：[{info['title']}]({info['url']})
- **提及標的**：{tags_str}
- **逐字稿來源**：{transcript_source}

---

## 📊 提及標的即時數據 (Real-time Market Data)
{stock_market_table if stock_market_table else '*(未包含特定個股數據)*'}

---

# {summary_title}

## 📌 核心投資摘要
{core_summary}

---

## 🔍 個股深度分析

* **投資立場**：{author_stance}
* **核心催化劑 (Catalysts)**：
{catalysts_formatted}

### 🎯 關鍵價位與操作策略 (技術與籌碼面)
{key_levels}

---

## ⚖️ 看多 vs 看空 論點對比表

| 觀點維度 | 🟢 看多陣營 (Bullish) | 🔴 看空/風險陣營 (Bearish) |
| :--- | :--- | :--- |
{comparison_table}

---

## ⏱️ Key Timestamps 時間標記
{timeline_formatted}

---
*> **警語**：本報告僅供參考，無任何投資勸誘行為。投資人應獨立思考，審慎評估並自負投資風險。*
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
    clean_channel = sanitize_filename(channel, max_length=50)
    clean_title = sanitize_filename(title)
    
    channel_dir = NOTES_DIR / clean_channel
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    stock_prefix = build_stock_prefix(tickers, stock_name_zh=stock_name_zh)
    
    if stock_prefix:
        raw_filename = f"{date}_{stock_prefix}_{clean_title}.md"
    else:
        raw_filename = f"{date}_{clean_title}.md"
        
    filename = sanitize_filename(raw_filename, max_length=70)
    file_path = channel_dir / filename
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return file_path
