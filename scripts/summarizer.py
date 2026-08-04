import json
from pathlib import Path
from google import genai
from google.genai import types
from config import NOTES_DIR, GEMINI_API_KEY, sanitize_filename
from stock_market import get_stock_data, generate_market_table_md, get_clean_stock_info

SYSTEM_PROMPT = """
你是一位資深的量化交易員與股票分析師。請將輸入的 YouTube 股票分析影片逐字稿與元資料，整理成極具投資決策價值、結構嚴密的 Markdown 筆記。

請遵守以下規則：
1. 使用繁體中文。
2. 精確提取影片中提及的所有個股與 ETF（包含台股如 2330, 2454, 0050 與美股如 NVDA, TSLA, AAPL）。
3. 嚴格分析創作者對每檔個股的立場（🟢 看多 / 🔴 看空 / 🟡 觀望），並整理出關鍵技術面支撐/壓力位、目標價、停損點與基本面催化劑。
4. 提供「看多 vs 看空」對比表格。
5. 附帶 key timestamp 時間標記（如 [02:15]）。

請嚴格輸出 JSON 格式，結構如下：
{
  "tickers": ["2337.TW", "NVDA"],
  "tags": ["#2337旺宏", "#NVDA輝達", "#NORFlash", "#AI伺服器"],
  "summary_markdown": "...完整的 Markdown 內容 (不用包含市場數據表格，系統會自動插入)..."
}
"""

def generate_summary(video_info: dict, transcript: str) -> dict:
    """使用 Gemini API 生成股票分析 Markdown 總結"""
    if not GEMINI_API_KEY:
        raise ValueError("未設定 GEMINI_API_KEY！請在 .env 檔案中設定 GEMINI_API_KEY=")

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    user_content = f"""
【影片元資料】
- 標題：{video_info['title']}
- 頻道：{video_info['channel']}
- 發布日期：{video_info['upload_date']}
- 連結：{video_info['url']}

【影片字幕逐字稿】
{transcript[:30000]}
"""

    models_to_try = ['gemini-flash-latest', 'gemini-2.0-flash', 'gemini-2.0-flash-lite']
    response = None
    last_error = None
    
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[SYSTEM_PROMPT, user_content],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            if response:
                break
        except Exception as e:
            last_error = e
            continue
            
    if not response:
        raise RuntimeError(f"Gemini API 呼叫失敗: {last_error}")
        
    try:
        data = json.loads(response.text)
    except Exception as e:
        print(f"⚠️ AI 輸出 Parsing 失敗，使用標準格式: {e}")
        data = {
            "tickers": [],
            "tags": [],
            "summary_markdown": response.text
        }
        
    # 抓取市場即時數據
    tickers = data.get("tickers", [])
    market_data = get_stock_data(tickers)
    market_table_md = generate_market_table_md(market_data)
    
    # 組合最終 MD 檔案內容
    tags_str = " ".join([f"`{tag}`" for tag in data.get("tags", [])])
    
    final_md = f"""# 【股票分析】{video_info['title']}
- **頻道／創作者**：{video_info['channel']}
- **發布日期**：{video_info['upload_date']}
- **影片連結**：[{video_info['title']}]({video_info['url']})
- **提及標的**：{tags_str if tags_str else '無特定標的'}

---

## 📊 提及標的即時數據 (Real-time Market Data)
{market_table_md}

---

{data.get('summary_markdown', '')}
"""

    return {
        "final_md": final_md,
        "tickers": tickers,
        "market_data": market_data,
        "tags": data.get("tags", [])
    }

def build_stock_prefix(tickers: list[str]) -> str:
    """根據提及股票產生標頭前綴，如 【2337旺宏】 或 【2330台積電_NVDA輝達】"""
    if not tickers:
        return ""
        
    prefix_parts = []
    # 最多取前 2~3 個主要標的
    for t in tickers[:3]:
        code, clean_name = get_clean_stock_info(t)
        if clean_name and clean_name != code:
            prefix_parts.append(f"{code}{clean_name}")
        else:
            prefix_parts.append(code)
            
    if prefix_parts:
        return f"【{'_'.join(prefix_parts)}】"
    return ""

def save_note(channel: str, date: str, title: str, note_content: str, tickers: list[str] = None) -> Path:
    """
    將總結寫入 影片筆記/<頻道名稱>/【股票代號名稱】<日期>_<標題>.md
    """
    clean_channel = sanitize_filename(channel)
    clean_title = sanitize_filename(title)
    
    stock_prefix = build_stock_prefix(tickers) if tickers else ""
    
    channel_dir = NOTES_DIR / clean_channel
    channel_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{stock_prefix}{date}_{clean_title}.md"
    file_path = channel_dir / filename
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(note_content)
        
    return file_path
