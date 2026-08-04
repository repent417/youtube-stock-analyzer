from pathlib import Path
from config import INDEX_DIR, sanitize_filename
from stock_market import normalize_ticker

def update_stock_index(ticker: str, video_info: dict, note_rel_path: str):
    """
    更新或建立個股交叉索引 Markdown 檔案：
    個股索引/<股票代號>.md
    """
    norm_ticker = normalize_ticker(ticker)
    clean_ticker = sanitize_filename(norm_ticker)
    index_file = INDEX_DIR / f"{clean_ticker}.md"
    
    date_str = video_info['upload_date']
    title = video_info['title']
    channel = video_info['channel']
    
    # 相對路徑點回 影片筆記
    # 例如：../影片筆記/【曲博科技教室】/2026-08-04_標題.md
    entry = f"- **[{date_str}]** [{title}]({note_rel_path}) （頻道：`{channel}`）\n"
    
    if not index_file.exists():
        header = f"""# 個股歷史分析索引：{norm_ticker}

本檔案由自動化系統維護，彙整所有提及 {norm_ticker} 的 YouTube 股票分析影片筆記。

---

## 📅 分析紀錄 (Timeline)
"""
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(header + entry)
    else:
        with open(index_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        # 防止重複寫入相同影片
        if note_rel_path not in content:
            with open(index_file, "a", encoding="utf-8") as f:
                f.write(entry)
